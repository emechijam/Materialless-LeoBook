import asyncio
import os
import json
import time
import requests
import re
import unicodedata
import uuid
from collections import defaultdict
from Core.Intelligence.aigo_suite import AIGOSuite
from Core.Intelligence.llm_health_manager import health_manager
from supabase import create_client
from dotenv import load_dotenv
from Data.Access.db_helpers import _get_conn, save_team_entry, save_country_league_entry
from Data.Access.league_db import query_all

# FIX: CSV_LOCK is never referenced anywhere — removed dead code
# CSV_LOCK = asyncio.Lock()

# Load environment variables
load_dotenv()

# ================================================
# Configuration
# ================================================
# Legacy CSV paths removed — all reads from SQLite now
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# LLM Provider Configuration
# Model chain is dynamic via LLMHealthManager.MODELS_ASCENDING
# (cheapest first for search-dict bulk enrichment)
# FIX: LLM_PROVIDERS block was dead config — never iterated, all routing
#      goes through health_manager. Removed to avoid confusion.
BATCH_SIZE = 10
SLEEP_BETWEEN_BATCHES = 4

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

# Initialize Supabase
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def normalize_for_search(name: str) -> str:
    """Standard normalization for search term generation (NFKD for accents)."""
    if not name: return ""
    # Normalize unicode characters to decompose accents
    nfkd_form = unicodedata.normalize('NFKD', name)
    # Filter out non-ASCII characters (accents)
    only_ascii = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Remove non-alphanumeric and lower
    return re.sub(r'[^a-z0-9\s]', '', only_ascii.lower().strip())

def generate_deterministic_id(name: str, context: str = "") -> str:
    """Generates a deterministic ID using UUIDv5 as a fallback for slugs."""
    namespace = uuid.NAMESPACE_DNS
    unique_string = f"leobook-{context}-{normalize_for_search(name)}"
    return str(uuid.uuid5(namespace, unique_string))

def is_field_empty(value: str) -> bool:
    """True if a CSV field is effectively empty (None-string, null, unknown, etc)."""
    v = (value or '').strip().lower()
    return v in ('', 'none', 'null', 'unknown', '[]')

def clean_none_values(data: dict) -> dict:
    """Replace Python None values with empty string to avoid 'None' in CSV."""
    return {k: ('' if v is None else v) for k, v in data.items()}

from Scripts.search_dict_llm import (  # noqa: re-export
    extract_json_with_salvage,
    _build_prompt,
    _call_llm,
    query_llm_for_metadata,
    async_query_llm_for_metadata,
    query_grok_for_metadata_with_retry,
)

def batch_upsert(table_name: str, data: list, chunk_size: int = 1000):
    """Upserts data to Supabase in chunks to avoid payload limits."""
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        try:
            supabase.table(table_name).upsert(chunk).execute()
        except Exception as e:
            print(f"  [Error] Batch upsert to {table_name} failed (chunk starting at {i}): {e}")
            # Individual fallback if batch fails
            if len(chunk) > 1:
                print("  [Info] Retrying chunk items individually...")
                for item in chunk:
                    try:
                        supabase.table(table_name).upsert(item).execute()
                    except Exception as e2:
                        print(f"  [Error] Individual upsert failed: {e2}")

def update_db_under_lock(data_map, key_field, table_type="team"):
    """Upsert enrichment data into SQLite tables."""
    count = 0
    for key, data in data_map.items():
        # Serialize lists/dicts to JSON strings for SQLite TEXT columns
        serialized = {}
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                serialized[k] = json.dumps(v)
            else:
                serialized[k] = v

        if table_type == "team":
            save_team_entry(serialized)
        else:
            save_country_league_entry(serialized)
        count += 1
    print(f"Upserted {count} {table_type} rows into SQLite")

def find_best_match_league(input_name: str, country: str, existing_leagues: dict):
    """
    Match an input league name against existing league rows.
    Returns (league_id, is_new).
    """
    norm_input = normalize_for_search(input_name)
    # Strip round/stage suffixes for matching: "TURKEY - 1. LIG - ROUND 22" → "turkey 1 lig"
    norm_input_base = re.sub(r'\s*-?\s*(round|matchday|playoffs?|apertura|clausura|1/\d+-finals?|group\s*\w)\s*.*$', '', norm_input, flags=re.IGNORECASE).strip()

    best_id = None
    best_score = 0

    for league_id, row in existing_leagues.items():
        existing_name = normalize_for_search(row.get("name", "") or row.get("league", ""))
        existing_country = (row.get("country") or "").strip().lower()

        # Country must match if both are present
        if country and existing_country and country.strip().lower() != existing_country:
            continue

        # Exact match (Name-based fallback if ID is just a slug or Unknown)
        if norm_input_base == existing_name:
            return league_id, False

        # Substring containment score
        if norm_input_base and existing_name:
            if norm_input_base in existing_name or existing_name in norm_input_base:
                score = len(existing_name)
                if score > best_score:
                    best_score = score
                    best_id = league_id

    if best_id:
        return best_id, False

    # No match — generate deterministic ID
    return generate_deterministic_id(input_name, country or ""), True


def _has_llm_capacity(chain_name: str = "search_dict") -> bool:
    """
    FIX: Replaces the broken circuit-breaker pattern:
        `not health_manager._gemini_active`
    which only fires when keys are permanently dead (403/401), never during
    quota exhaustion.

    This checks has_chain_capacity() which correctly accounts for daily
    exhaustion AND per-minute cooldowns. Falls back to Grok active check
    as a secondary path.
    """
    grok_ok = getattr(health_manager, '_grok_active', False)
    gemini_ok = health_manager.has_chain_capacity(chain_name)
    return grok_ok or gemini_ok


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, use_aigo=False)
async def main():
    conn = _get_conn()

    leagues_raw = set()
    teams_raw = defaultdict(lambda: {"id": None, "names": set()})

    print(f"Reading fixtures from SQLite and collecting unique teams/leagues...")
    fixtures = query_all(conn, 'schedules')
    if not fixtures:
        print("Error: No fixtures found in database.")
        return

    for row in fixtures:
        rl = (row.get("country_league") or "Unknown").strip()
        leagues_raw.add(rl)
        for prefix in ["home_team", "away_team"]:
            # fixtures table uses home_team_name/away_team_name or home_team/away_team
            tname = (row.get(prefix + "_name") or row.get(prefix) or "").strip()
            tid = (row.get(prefix.replace('team', 'team_id')) or row.get(prefix + "_id") or "").strip()
            if not tname or not tid:
                continue
            teams_raw[tid]["id"] = tid
            teams_raw[tid]["names"].add(tname)

    print(f"Found {len(leagues_raw)} unique league keys")
    print(f"Found {len(teams_raw)} unique teams (by ID)")

    fully_enriched_team_ids = set()
    incomplete_team_ids = set()
    TEAM_CRITICAL_FIELDS = ['abbreviations', 'city']

    teams_data = query_all(conn, 'teams')
    for row in teams_data:
        st = str(row.get('search_terms', '')).strip()
        tid = str(row.get('team_id', '')).strip()
        if not tid: continue
        if st and st != '[]':
            missing = [fld for fld in TEAM_CRITICAL_FIELDS if is_field_empty(str(row.get(fld, '')))]
            if missing: incomplete_team_ids.add(tid)
            else: fully_enriched_team_ids.add(tid)

    existing_leagues = {}
    fully_enriched_league_keys = set()
    incomplete_league_keys = set()
    LEAGUE_CRITICAL_FIELDS = ['abbreviations']
    leagues_data = query_all(conn, 'leagues')
    for row in leagues_data:
        league_id = str(row.get('league_id', '')).strip()
        if not league_id: continue
        existing_leagues[league_id] = dict(row)
        st = str(row.get('search_terms', '')).strip()
        if st and st != '[]':
            missing = [fld for fld in LEAGUE_CRITICAL_FIELDS if is_field_empty(str(row.get(fld, '')))]
            if missing: incomplete_league_keys.add(league_id)
            else: fully_enriched_league_keys.add(league_id)

    raw_to_rlid = {}
    for raw_name in leagues_raw:
        league_id, _ = find_best_match_league(raw_name, None, existing_leagues)
        raw_to_rlid[raw_name] = league_id

    empty_leagues = [l for l in leagues_raw if raw_to_rlid[l] not in fully_enriched_league_keys and raw_to_rlid[l] not in incomplete_league_keys]
    incomplete_leagues_list = [l for l in leagues_raw if raw_to_rlid[l] in incomplete_league_keys]

    print(f"\n--- PASS 1: Teams ---")
    print(f"  {len(teams_raw) - len(fully_enriched_team_ids) - len(incomplete_team_ids)} teams to process.")
    print(f"\n--- PASS 2: Teams ---")
    print(f"  {len(incomplete_team_ids)} teams to re-process (incomplete data).")
    print(f"\n--- PASS 1: Leagues ---")
    print(f"  {len(empty_leagues)} leagues to process.")
    print(f"\n--- PASS 2: Leagues ---")
    print(f"  {len(incomplete_leagues_list)} leagues to re-process (incomplete data).")

    # --- Ensure health manager is initialized before circuit-breaker checks ---
    await health_manager.ensure_initialized()

    # --- Process Leagues ---
    for league_list, pass_name in [(empty_leagues, "PASS 1"), (incomplete_leagues_list, "PASS 2")]:
        if not league_list: continue
        print(f"\n--- {pass_name}: Leagues ---")
        for i in range(0, len(league_list), BATCH_SIZE):
            # FIX: use has_chain_capacity() — correctly detects quota exhaustion,
            #      not just permanent key death.
            if not _has_llm_capacity("search_dict"):
                remaining = len(league_list) - i
                print(f"  [SearchDict] All LLM providers offline -- skipping {remaining} remaining leagues.")
                break
            batch = league_list[i:i + BATCH_SIZE]
            print(f"  Processing batch of {len(batch)} leagues...")
            results = await async_query_llm_for_metadata(batch, item_type="league")
            updates = {}
            for item in results:
                input_name = item.get("input_name")
                official_name = item.get("official_name") or input_name
                country = item.get("country")  # LLM might return country for a league
                lid, _ = find_best_match_league(input_name, country, existing_leagues)
                
                search_terms = {normalize_for_search(input_name), normalize_for_search(official_name)}
                for n in item.get("other_names", []): search_terms.add(normalize_for_search(n))
                for a in item.get("abbreviations", []): search_terms.add(normalize_for_search(a))
                
                upsert_data = clean_none_values({
                    "name": official_name,  # Standardized v7 column name
                    "other_names": item.get("other_names", []),
                    "abbreviations": item.get("abbreviations", []),
                    "search_terms": list(filter(None, search_terms)),
                    "league_id": lid
                })
                updates[lid] = upsert_data

            if updates:
                print(f"  [Supabase] Upserting {len(updates)} leagues to 'leagues'...")
                batch_upsert("leagues", list(updates.values()))
                update_db_under_lock(updates, "league_id", "leagues")
            await asyncio.sleep(SLEEP_BETWEEN_BATCHES)

    # --- Process Teams ---
    team_ids_all = list(teams_raw.keys())
    team_ids_pass1 = [tid for tid in team_ids_all if tid not in fully_enriched_team_ids and tid not in incomplete_team_ids]
    team_ids_pass2 = [tid for tid in team_ids_all if tid in incomplete_team_ids]
    
    for team_ids, pass_name in [(team_ids_pass1, "PASS 1"), (team_ids_pass2, "PASS 2")]:
        if not team_ids: continue
        print(f"\n── {pass_name}: Teams ──")
        for i in range(0, len(team_ids), BATCH_SIZE):
            # FIX: use has_chain_capacity() — correctly detects quota exhaustion
            if not _has_llm_capacity("search_dict"):
                remaining = len(team_ids) - i
                print(f"  [SearchDict] All LLM providers offline -- skipping {remaining} remaining teams.")
                break
            batch_ids = team_ids[i:i + BATCH_SIZE]
            batch_names = [list(teams_raw[tid]["names"])[0] for tid in batch_ids]  # Use first name as input
            print(f"  Processing batch of {len(batch_ids)} teams...")
            results = await async_query_llm_for_metadata(batch_names, item_type="team")
            updates = {}
            for idx, item in enumerate(results):
                if idx >= len(batch_ids): break  # Safety break
                tid = batch_ids[idx]
                off_name = item.get("official_name") or list(teams_raw[tid]["names"])[0]
                search_terms = {normalize_for_search(off_name)}
                for n in teams_raw[tid]["names"]: search_terms.add(normalize_for_search(n))
                for n in item.get("other_names", []): search_terms.add(normalize_for_search(n))
                for a in item.get("abbreviations", []): search_terms.add(normalize_for_search(a))
                
                upsert_data = clean_none_values({
                    "team_id": tid,
                    "name": off_name,  # Standardized v7
                    "other_names": item.get("other_names", []),
                    "abbreviations": item.get("abbreviations", []),
                    "search_terms": list(filter(None, search_terms)),
                    "country_code": item.get("country_code") or item.get("country"),  # Flex with v7
                    "city": item.get("city"),
                    "stadium": item.get("stadium"),
                })
                updates[tid] = upsert_data

            if updates:
                print(f"  [Supabase] Upserting {len(updates)} teams to 'teams'...")
                batch_upsert("teams", list(updates.values()))
                update_db_under_lock(updates, "team_id", "teams")  # SQLite table is 'teams'
            await asyncio.sleep(SLEEP_BETWEEN_BATCHES)

    print("\nSearch dictionary built and local CSVs/Supabase synced!")

# ================================================
# Per-Match Search Dict Enrichment (v3.6)
# ================================================

async def enrich_match_search_dict(
    league_name: str, league_id: str,
    home_team: str, home_id: str,
    away_team: str, away_id: str
):
    """
    Per-match enrichment: checks if the league + 2 teams need search_terms/abbreviations.
    If any are missing, calls the LLM for just those items (max 3 per call).
    Updates both CSV and Supabase immediately.
    """
    items_to_enrich_team = []
    items_to_enrich_league = []
    team_id_map = {}  # name -> id

    # --- Check what needs enrichment ---
    conn = _get_conn()
    # Check teams
    for tid, tname in [(home_id, home_team), (away_id, away_team)]:
        if not tid or not tname:
            continue
        row = conn.execute("SELECT search_terms, abbreviations FROM teams WHERE team_id = ?", (tid,)).fetchone()
        found = False
        if row:
            st = str(row['search_terms'] or '').strip()
            abbr = str(row['abbreviations'] or '').strip()
            if st and st != '[]' and abbr and abbr != '[]':
                found = True
        if not found:
            items_to_enrich_team.append(tname)
            team_id_map[tname] = tid

    # Check league
    if league_id:
        row = conn.execute("SELECT search_terms, abbreviations FROM leagues WHERE league_id = ?", (league_id,)).fetchone()
        league_enriched = False
        if row:
            st = str(row['search_terms'] or '').strip()
            abbr = str(row['abbreviations'] or '').strip()
            if st and st != '[]' and abbr and abbr != '[]':
                league_enriched = True
        if not league_enriched and league_name:
            items_to_enrich_league.append(league_name)

    if not items_to_enrich_team and not items_to_enrich_league:
        return  # Nothing to do

    total = len(items_to_enrich_team) + len(items_to_enrich_league)
    print(f"    [SearchDict] Enriching {total} items for this match ({len(items_to_enrich_team)} teams, {len(items_to_enrich_league)} leagues)...")

    # --- Enrich teams ---
    if items_to_enrich_team:
        try:
            results = await async_query_llm_for_metadata(items_to_enrich_team, item_type="team")
            updates = {}
            for idx, item in enumerate(results):
                if idx >= len(items_to_enrich_team):
                    break
                tname = items_to_enrich_team[idx]
                tid = team_id_map.get(tname)
                if not tid:
                    continue
                off_name = item.get("official_name") or tname
                search_terms = {normalize_for_search(off_name), normalize_for_search(tname)}
                for n in item.get("other_names", []):
                    search_terms.add(normalize_for_search(n))
                for a in item.get("abbreviations", []):
                    search_terms.add(normalize_for_search(a))

                upsert_data = clean_none_values({
                    "team_id": tid,
                    "name": off_name,  # Standardized v7
                    "other_names": item.get("other_names", []),
                    "abbreviations": item.get("abbreviations", []),
                    "search_terms": list(filter(None, search_terms)),
                    "country_code": item.get("country_code") or item.get("country"),
                    "city": item.get("city"),
                    "stadium": item.get("stadium"),
                })
                updates[tid] = upsert_data

            if updates:
                batch_upsert("teams", list(updates.values()))
                update_db_under_lock(updates, "team_id", "teams")
                print(f"    [SearchDict] {len(updates)} teams enriched")
        except Exception as e:
            print(f"    [SearchDict] Team enrichment error (non-fatal): {e}")

    # --- Enrich league ---
    if items_to_enrich_league:
        try:
            results = await async_query_llm_for_metadata(items_to_enrich_league, item_type="league")
            updates = {}
            for item in results:
                input_name = item.get("input_name")
                official_name = item.get("official_name") or input_name
                search_terms = {normalize_for_search(input_name), normalize_for_search(official_name)}
                for n in item.get("other_names", []):
                    search_terms.add(normalize_for_search(n))
                for a in item.get("abbreviations", []):
                    search_terms.add(normalize_for_search(a))

                upsert_data = clean_none_values({
                    "league_id": league_id,
                    "name": official_name,  # Standardized v7 column name
                    "other_names": item.get("other_names", []),
                    "abbreviations": item.get("abbreviations", []),
                    "search_terms": list(filter(None, search_terms)),
                })
                updates[league_id] = upsert_data

            if updates:
                batch_upsert("leagues", list(updates.values()))
                update_db_under_lock(updates, "league_id", "leagues")
                print(f"    [SearchDict] League '{league_name}' enriched")
        except Exception as e:
            print(f"    [SearchDict] League enrichment error (non-fatal): {e}")


async def enrich_batch_teams_search_dict(team_pairs: list, batch_size: int = 10):
    """
    Batch-enriches ALL discovered teams with search terms/abbreviations via LLM.
    
    Args:
        team_pairs: List of dicts with 'team_id' and 'team_name' (or 'name').
        batch_size: Number of teams per LLM call (default 10).
    """
    if not team_pairs:
        return

    # 1. Filter out already-enriched teams
    unenriched = []
    conn = _get_conn()
    teams_data = query_all(conn, 'teams')
    enriched_ids = set()
    for row in teams_data:
        st = str(row.get('search_terms', '') or '').strip()
        abbr = str(row.get('abbreviations', '') or '').strip()
        if st and st != '[]' and abbr and abbr != '[]':
            enriched_ids.add(str(row.get('team_id', '')))

    for tp in team_pairs:
        tid = tp.get('team_id') or tp.get('id', '')
        tname = tp.get('team_name') or tp.get('name', '')
        if tid and tname and tid not in enriched_ids:
            unenriched.append({'team_id': tid, 'team_name': tname})

    if not unenriched:
        return

    print(f"    [SearchDict Batch] Enriching {len(unenriched)} unenriched teams in batches of {batch_size}...")

    # 2. Process in batches
    total_enriched = 0
    consecutive_failures = 0
    
    # FIX: removed duplicate import — health_manager already imported at module level
    await health_manager.ensure_initialized()

    for i in range(0, len(unenriched), batch_size):
        # FIX: use _has_llm_capacity() — correctly detects quota exhaustion,
        #      not just permanent key death.
        if not _has_llm_capacity("search_dict"):
            remaining = len(unenriched) - i
            print(f"    [SearchDict Batch] ⚠ No LLM providers available — skipping remaining {remaining} teams.")
            break

        batch = unenriched[i:i + batch_size]
        batch_names = [t['team_name'] for t in batch]
        batch_id_map = {t['team_name']: t['team_id'] for t in batch}

        try:
            results = await async_query_llm_for_metadata(batch_names, item_type="team")

            # Circuit-breaker: track consecutive empty results
            if not results:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    remaining = len(unenriched) - i - batch_size
                    print(f"    [SearchDict Batch] ⚠ {consecutive_failures} consecutive LLM failures — aborting enrichment ({remaining} teams remaining).")
                    break
                continue
            consecutive_failures = 0

            updates = {}
            for idx, item in enumerate(results):
                # Prefer LLM's input_name for mapping; fall back to index
                input_name = item.get("input_name", "")
                tid = batch_id_map.get(input_name)
                tname = input_name or (batch_names[idx] if idx < len(batch_names) else None)
                if not tid and idx < len(batch_names):
                    tname = batch_names[idx]
                    tid = batch_id_map.get(tname)
                if not tid or not tname:
                    continue

                off_name = item.get("official_name") or tname
                search_terms = {normalize_for_search(off_name), normalize_for_search(tname)}
                for n in item.get("other_names", []):
                    search_terms.add(normalize_for_search(n))
                for a in item.get("abbreviations", []):
                    search_terms.add(normalize_for_search(a))

                upsert_data = clean_none_values({
                    "team_id": tid,
                    "name": off_name,  # Standardized v7
                    "other_names": item.get("other_names", []),
                    "abbreviations": item.get("abbreviations", []),
                    "search_terms": list(filter(None, search_terms)),
                    "country_code": item.get("country_code") or item.get("country"),
                    "city": item.get("city"),
                    "stadium": item.get("stadium"),
                })
                updates[tid] = upsert_data

            if updates:
                batch_upsert("teams", list(updates.values()))
                update_db_under_lock(updates, "team_id", "teams")
                total_enriched += len(updates)
                print(f"    [SearchDict Batch] ✓ Batch {i // batch_size + 1}: {len(updates)} teams enriched")

        except Exception as e:
            print(f"    [SearchDict Batch] Batch {i // batch_size + 1} error (non-fatal): {e}")

        # FIX: use SLEEP_BETWEEN_BATCHES constant (was hardcoded 2 — half the configured value)
        if i + batch_size < len(unenriched):
            await asyncio.sleep(SLEEP_BETWEEN_BATCHES)

    if total_enriched:
        print(f"    [SearchDict Batch] ✓ Total: {total_enriched}/{len(unenriched)} teams enriched")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Rebuild search dictionary and metadata (LLM-enriched)")
    parser.add_argument("--test-health", action="store_true", help="Only test LLM provider connectivity and exit")
    args = parser.parse_args()

    if args.test_health:
        async def test_health():
            await health_manager.ensure_initialized()
            print("\n  --- LLM Health Status ---")
            providers = health_manager.get_ordered_providers()
            for p in providers:
                active = health_manager.is_provider_active(p)
                print(f"  [{'[OK]' if active else '[X]'}] {p}")
            
            if health_manager._gemini_active:
                print(f"  Gemini Keys: {len(health_manager._gemini_active)} active")
        
        asyncio.run(test_health())
    else:
        asyncio.run(main())
