# fb_manager.py: Orchestration layer for Football.com odds + booking.
# Part of LeoBook Modules — Football.com
#
# Functions: run_odds_harvesting(), run_automated_booking()
# Called by: Leo.py (Chapter 1 Page 1, Chapter 2 Page 1)
#
# Worker functions have been split into focused sub-modules:
#   fb_workers.py  — _odds_worker, _league_worker  (semaphore-bounded page workers)
#   fb_phase0.py   — run_league_calendar_fixtures_sync  (Phase 0 fixture discovery)

"""
Football.com Orchestrator — v4.2 (Sequential extraction, Phase 0 empty-league filter)
"""

import asyncio
import json
import os
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import Playwright, Page

from Core.Utils.constants import (
    MAX_CONCURRENCY, now_ng, WAIT_FOR_LOAD_STATE_TIMEOUT,
    FB_MOBILE_USER_AGENT, FB_MOBILE_VIEWPORT,
    ODDS_HARVEST_BATCH_SIZE, IMMINENT_MATCH_CUTOFF_HOURS,
)
from Core.Utils.utils import log_error_state
from Core.System.lifecycle import log_state
from Core.Intelligence.aigo_suite import AIGOSuite
from .odds_extractor import OddsResult
from .fb_session import launch_browser_with_retry
from .navigator import load_or_create_session, extract_balance, hide_overlays
from .fb_workers import _odds_worker, _league_worker
from .fb_phase0 import run_league_calendar_fixtures_sync, _load_fb_league_lookup
from Data.Access.db_helpers import (
    get_site_match_id, save_site_matches, save_match_odds,
    update_site_match_status, get_connection,
)
from Data.Access.league_db import LEAGUES_JSON_PATH


# ── Batch resume checkpoint ─────────────────────────────────────────────────
_CHECKPOINT_PATH = Path("Data/Logs/batch_checkpoint.json")


def _load_checkpoint() -> int:
    """Return last completed batch index for today (0 = start fresh)."""
    if _CHECKPOINT_PATH.exists():
        try:
            c = json.loads(_CHECKPOINT_PATH.read_text(encoding='utf-8'))
            if c.get("date") == now_ng().strftime("%Y-%m-%d"):
                return int(c.get("last_batch", 0))
        except Exception:
            pass
    return 0


def _save_checkpoint(batch_idx: int) -> None:
    """Persist last completed batch index for today."""
    _CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CHECKPOINT_PATH.write_text(
        json.dumps({"date": now_ng().strftime("%Y-%m-%d"), "last_batch": batch_idx}),
        encoding='utf-8',
    )


# ── Shared session helpers ──────────────────────────────────────────────────

async def _create_session(playwright: Playwright):
    """Full session setup: launch browser, login, extract balance. For bet placement."""
    user_data_dir = Path("Data/Auth/ChromeData_v3").absolute()
    user_data_dir.mkdir(parents=True, exist_ok=True)

    context = await launch_browser_with_retry(playwright, user_data_dir)
    _, page = await load_or_create_session(context)

    current_balance = await extract_balance(page)
    from Core.Utils.constants import CURRENCY_SYMBOL
    print(f"  [Balance] Current: {CURRENCY_SYMBOL}{current_balance:.2f}")

    return context, page, current_balance


async def _create_session_no_login(playwright: Playwright):
    """Lightweight session: fresh browser, NO login, NO saved state."""
    is_headless = os.getenv("CODESPACES") == "true" or (os.name != "nt" and not os.environ.get("DISPLAY"))

    browser = await playwright.chromium.launch(
        headless=is_headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage"
        ]
    )
    context = await browser.new_context(
        viewport=FB_MOBILE_VIEWPORT,
        user_agent=FB_MOBILE_USER_AGENT
    )
    page = await context.new_page()

    context._browser_ref = browser
    return context, page


# ── Time filter ─────────────────────────────────────────────────────────────

def _filter_imminent_matches(fixtures: List[dict], cutoff_hours: float = IMMINENT_MATCH_CUTOFF_HOURS) -> List[dict]:
    """Remove matches whose start time is within cutoff_hours of now_ng()."""
    from datetime import datetime
    from Core.Utils.constants import TZ_NG

    now = now_ng()
    cutoff = now + timedelta(hours=cutoff_hours)
    kept = []
    skipped = 0
    for f in fixtures:
        date_str = f.get('date', '')
        time_str = f.get('time', '') or '00:00'
        try:
            match_dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            match_dt = match_dt.replace(tzinfo=TZ_NG)
            if match_dt < cutoff:
                skipped += 1
                continue
        except (ValueError, TypeError):
            pass  # Can't parse → keep it (don't drop on uncertainty)
        kept.append(f)

    if skipped:
        print(f"  [Filter] Skipped {skipped} matches starting within {cutoff_hours}h of now.")
    return kept


# ── CHAPTER 1 PAGE 1 — Odds Harvesting ─────────────────────────────────────

@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_odds_harvesting(playwright: Playwright):
    """
    Chapter 1 Page 1: Direct fb_url Odds Harvesting (V4 — single-nav, fuzzy-only).

    Flow:
    1. Load weekly fixtures from schedules table
    2. Filter out matches starting within 30 min
    3. Lookup fb_url per league from unified leagues.json
    4. ONE navigation per league, extract ALL matches from page
    5. Fuzzy-match each fixture (sync, no LLM) via resolve_fixture_to_fb_match
    6. Save resolved matches to SQLite immediately
    7. Concurrent odds extraction (semaphore-bounded, MAX_CONCURRENCY pages)
    8. Post-session Supabase sync
    """
    print("\n--- Running Football.com Direct Odds Extraction (Chapter 1 P1 v9) ---")

    from Core.Intelligence.prediction_pipeline import get_weekly_fixtures
    from Data.Access.league_db import init_db, get_connection
    from .match_resolver import FixtureResolver

    conn = init_db()
    weekly_fixtures = get_weekly_fixtures(conn)
    if not weekly_fixtures:
        print("  [Info] No scheduled fixtures found for the next 7 days.")
        return

    # 1. Time filter — drop matches starting within cutoff
    weekly_fixtures = _filter_imminent_matches(weekly_fixtures)
    if not weekly_fixtures:
        print("  [Info] All remaining fixtures are too imminent. Nothing to extract.")
        return

    # 2. Load fb_url lookup
    fb_lookup = _load_fb_league_lookup(LEAGUES_JSON_PATH)
    if not fb_lookup:
        print("  [Warning] No fb_url mappings found in leagues.json. Cannot extract odds.")
        return
    print(f"  [Leagues] {len(fb_lookup)} leagues with fb_url loaded.")

    # 3. Group fixtures by league_id (only for leagues that have fb_url)
    leagues_to_extract: Dict[str, List[dict]] = {}
    skipped_no_fb = 0
    for f in weekly_fixtures:
        lid = f.get('league_id', '')
        if lid in fb_lookup:
            leagues_to_extract.setdefault(lid, []).append(f)
        else:
            skipped_no_fb += 1

    if skipped_no_fb:
        print(f"  [Info] {skipped_no_fb} fixtures skipped (league not mapped to football.com).")

    if not leagues_to_extract:
        print("  [Info] No fixtures matched any mapped league. Nothing to extract.")
        return

    total_fixtures = sum(len(v) for v in leagues_to_extract.values())
    total_leagues = len(leagues_to_extract)
    print(f"  [Pipeline] {total_fixtures} fixtures across {total_leagues} leagues to process.")

    # ── PHASE 0: Calendar Fixture Discovery ────────────────────────────────
    # BUG 2+5 FIX: Track which leagues Phase 0 confirmed have no fixtures.
    phase0_empty_leagues: set = set()
    from Core.System.guardrails import is_dry_run
    if not is_dry_run():
        try:
            phase0_empty_leagues = await run_league_calendar_fixtures_sync(playwright, LEAGUES_JSON_PATH)
        except Exception as e:
            print(f"  [Warning] Phase 0 Calendar Sync failed: {e}")

    # 4. Launch matcher
    matcher = FixtureResolver()
    all_resolved_matches: List[Dict] = []
    total_session_odds_count = 0

    # 5. Process in batches to prevent OOM
    BATCH_SIZE = ODDS_HARVEST_BATCH_SIZE
    league_ids = list(leagues_to_extract.keys())
    batches = [league_ids[i:i + BATCH_SIZE] for i in range(0, len(league_ids), BATCH_SIZE)]

    resume_from = _load_checkpoint()
    if resume_from > 0:
        print(f"  [Resume] Checkpoint found — skipping batches 1–{resume_from}, "
              f"starting at batch {resume_from + 1}/{len(batches)}")

    # BUG 2+5 FIX: Pre-filter leagues that Phase 0 confirmed empty
    if phase0_empty_leagues:
        pre_filter_count = len(leagues_to_extract)
        leagues_to_extract = {
            lid: fixes for lid, fixes in leagues_to_extract.items()
            if fb_lookup[lid]['fb_url'] not in phase0_empty_leagues
        }
        skipped_empty = pre_filter_count - len(leagues_to_extract)
        if skipped_empty:
            print(f"  [Filter] Skipped {skipped_empty} leagues confirmed empty by Phase 0.")
        total_fixtures = sum(len(v) for v in leagues_to_extract.values())
        total_leagues = len(leagues_to_extract)
        league_ids = list(leagues_to_extract.keys())
        batches = [league_ids[i:i + BATCH_SIZE] for i in range(0, len(league_ids), BATCH_SIZE)]
        print(f"  [Pipeline] After Phase 0 filter: {total_fixtures} fixtures across {total_leagues} leagues.")

    print(f"  [System] Processing {total_leagues} leagues in {len(batches)} batches (Size: {BATCH_SIZE})...")

    session_context, _ = await _create_session_no_login(playwright)

    try:
        for batch_idx, batch_ids in enumerate(batches):
            if batch_idx < resume_from:
                continue
            batch_num = batch_idx + 1
            print(f"\n  [Batch {batch_num}/{len(batches)}] Starting extraction for {len(batch_ids)} leagues...")

            conn.execute("BEGIN")

            try:
                # BUG 3 FIX: Force semaphore=1 to prevent concurrent pages from racing.
                league_sem = asyncio.Semaphore(1)

                league_tasks = [
                    _league_worker(
                        league_sem, session_context,
                        lid,
                        fb_lookup[lid].get('fb_league_name', fb_lookup[lid].get('name', lid)),
                        leagues_to_extract[lid],
                        fb_lookup[lid]['fb_url'],
                        conn, matcher,
                    )
                    for lid in batch_ids
                ]

                batch_extraction_results = await asyncio.gather(*league_tasks, return_exceptions=True)

                batch_resolved: List[Dict] = []
                for res in batch_extraction_results:
                    if isinstance(res, list):
                        batch_resolved.extend(res)
                    elif isinstance(res, Exception):
                        print(f"    [Batch {batch_num}] League worker failed: {res}")

                if not batch_resolved:
                    print(f"    [Batch {batch_num}] No matches resolved in this batch.")
                    conn.execute("COMMIT")
                    continue

                all_resolved_matches.extend(batch_resolved)

                if batch_resolved:
                    print(f"    [Batch {batch_num}] Extracting odds for {len(batch_resolved)} matches...")
                    odds_sem = asyncio.Semaphore(MAX_CONCURRENCY)
                    results = await asyncio.gather(
                        *[_odds_worker(odds_sem, session_context, m, conn) for m in batch_resolved],
                        return_exceptions=True,
                    )

                    batch_outcomes = 0
                    for r in results:
                        if isinstance(r, OddsResult) and r.outcomes_extracted > 0:
                            batch_outcomes += r.outcomes_extracted
                        elif isinstance(r, Exception):
                            print(f"    [Batch {batch_num}] Odds task failed: {r}")

                    total_session_odds_count += batch_outcomes
                    print(f"    [Batch {batch_num}] Odds extracted: {batch_outcomes} outcomes.")

                conn.execute("COMMIT")
                print(f"    ✓ [Batch {batch_num}] Atomic commit successful.")

            except Exception as e:
                conn.execute("ROLLBACK")
                print(f"    ⚠ [Batch {batch_num}] BATCH FAILED -> ROLLED BACK. Error: {e}")

            await asyncio.sleep(2)
            _save_checkpoint(batch_idx + 1)

    finally:
        if session_context:
            await session_context.close()
            if hasattr(session_context, '_browser_ref'):
                await session_context._browser_ref.close()

    _CHECKPOINT_PATH.unlink(missing_ok=True)

    print("\n  [Post-Harvest] Starting global enrichment and sync...")

    if all_resolved_matches or total_session_odds_count > 0:
        try:
            from Data.Access.sync_manager import SyncManager, TABLE_CONFIG
            manager = SyncManager()
            await manager._sync_table('fb_matches', TABLE_CONFIG['fb_matches'])
            await manager._sync_table('match_odds', TABLE_CONFIG['match_odds'])
            print(f"  [Sync] Complete: {len(all_resolved_matches)} matches, {total_session_odds_count} odds outcomes.")
        except Exception as e:
            print(f"  [Sync] [Warning] Supabase push failed: {e}")

    method_counts = {
        "sql_v2":  sum(1 for m in all_resolved_matches if m.get("resolution_method") == "sql_v2.0"),
        "failed":  sum(1 for m in all_resolved_matches if m.get("resolution_method") == "failed"),
    }
    resolved_count = method_counts["sql_v2"]

    print(f"\n    [Ch1 P1] -- Session Summary --------------------------")
    print(f"    [Ch1 P1] Fixtures processed  : {total_fixtures}")
    print(f"    [Ch1 P1] Leagues navigated   : {total_leagues}")
    print(f"    [Ch1 P1] Resolved            : {resolved_count}")
    print(f"    [Ch1 P1]   - exact SQL       : {method_counts['sql_v2']}")
    print(f"    [Ch1 P1] Unresolved          : {method_counts['failed']}")
    print(f"    [Ch1 P1] Odds outcomes       : {total_session_odds_count}")
    print(f"    [Ch1 P1] -------------------------------------------------\n")


# ── CHAPTER 2 PAGE 1 — Automated Booking ───────────────────────────────────

@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_automated_booking(playwright: Playwright):
    """
    Chapter 2 Page 1: Automated Booking.
    Reads harvested codes and places multi-bets. Does NOT harvest.
    """
    from Core.System.guardrails import check_kill_switch, is_dry_run
    if check_kill_switch():
        print("  [KILL SWITCH] STOP_BETTING file detected. Aborting booking.")
        return
    if is_dry_run():
        print("  [DRY-RUN] Automated booking skipped (dry-run mode).")
        return

    print("\n--- Running Automated Booking (Chapter 2A) ---")

    from .fb_setup import get_pending_predictions_by_date
    predictions_by_date = await get_pending_predictions_by_date()
    if not predictions_by_date:
        return

    booking_queue = {}
    print("  [System] Building booking queue from registry...")
    from .fb_url_resolver import get_harvested_matches_for_date

    for target_date in sorted(predictions_by_date.keys()):
        harvested = await get_harvested_matches_for_date(target_date)
        if harvested:
            booking_queue[target_date] = harvested

    if not booking_queue:
        print("  [System] No harvested matches found for any pending dates. Exiting.")
        return

    max_restarts = 3
    restarts = 0

    while restarts <= max_restarts:
        context = None
        try:
            print(f"  [System] Launching Booking Session (Restart {restarts}/{max_restarts})...")
            context, page, current_balance = await _create_session(playwright)
            log_state(chapter="Chapter 2A", action="Placing bets")

            from .booker.placement import place_stairway_accumulator

            for target_date, harvested in booking_queue.items():
                print(f"\n--- Booking Date: {target_date} ---")
                await place_stairway_accumulator(page, current_balance)
                log_state(chapter="Chapter 2A", action="Booking Complete",
                          next_step=f"Processed {target_date}")

            break

        except Exception as e:
            is_fatal = "FatalSessionError" in str(type(e)) or "dirty" in str(e).lower()
            if is_fatal and restarts < max_restarts:
                print(f"\n[!!!] FATAL SESSION ERROR: {e}")
                restarts += 1
                if context:
                    await context.close()
                await asyncio.sleep(5)
                continue
            else:
                await log_error_state(None, "booking_fatal", e)
                print(f"  [CRITICAL] Booking failed: {e}")
                break
        finally:
            if context:
                try:
                    await context.close()
                    if hasattr(context, '_browser_ref'):
                        await context._browser_ref.close()
                except Exception:
                    pass


# Backward compat
async def run_football_com_booking(playwright: Playwright):
    """Legacy wrapper: runs both harvesting and booking sequentially."""
    await run_odds_harvesting(playwright)
    await run_automated_booking(playwright)
