# db_helpers_audit.py: Audit query and reporting helpers for LeoBook SQLite.
# Part of LeoBook Data — Access
#
# Split from db_helpers.py (v9.6.0) — audit/query functions only.
# All callers should use league_db.py (facade).

"""
DB Helpers Audit Module
Country code resolution, Football.com registry, match odds, and legacy stubs.
All data persisted to leobook.db via league_db.py.
"""

import hashlib
import logging
from datetime import datetime as dt
from typing import Dict, Any, List, Optional
import asyncio

logger = logging.getLogger(__name__)

from Data.Access.league_db import (
    upsert_fb_match, query_all,
    upsert_match_odds_batch,
)

# Imported lazily from db_helpers to avoid circular imports
def _get_conn_ref():
    from Data.Access.db_helpers import _get_conn
    return _get_conn()


# ─── Country Code Resolution ───

def fill_national_team_country_codes(conn=None) -> int:
    """Pass 1 — Fill teams.country_code for national teams by matching team
    names against country.json + override aliases.

    Returns:
        Number of rows updated.
    """
    import json as _json
    import os as _os

    conn = conn or _get_conn_ref()

    NAME_OVERRIDES: Dict[str, str] = {
        "ENGLAND":                  "gb-eng",
        "SCOTLAND":                 "gb-sct",
        "WALES":                    "gb-wls",
        "NORTHERN IRELAND":         "gb-nir",
        "IVORY COAST":              "ci",
        "DR CONGO":                 "cd",
        "ESWATINI":                 "sz",
        "UNITED ARAB EMIRATES":     "ae",
        "SOUTH KOREA":              "kr",
        "NORTH MACEDONIA":          "mk",
        "TRINIDAD AND TOBAGO":      "tt",
        "TRINIDAD & TOBAGO":        "tt",
        "BOSNIA AND HERZEGOVINA":   "ba",
        "BOSNIA":                   "ba",
        "USA":                      "us",
        "UNITED STATES":            "us",
        "CHINESE TAIPEI":           "tw",
        "HONG KONG":                "hk",
        "MACAU":                    "mo",
        "MACAO":                    "mo",
        "CAPE VERDE":               "cv",
        "NORTH KOREA":              "kp",
        "SOUTH SUDAN":              "ss",
        "PALESTINE":                "ps",
        "KOSOVO":                   "xk",
        "CURACAO":                  "cw",
        "SINT MAARTEN":             "sx",
        "ANTIGUA AND BARBUDA":      "ag",
        "SAINT KITTS AND NEVIS":    "kn",
        "SAINT LUCIA":              "lc",
        "SAINT VINCENT":            "vc",
    }

    country_json_path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))),
        "Data", "Store", "country.json"
    )
    name_map: Dict[str, str] = dict(NAME_OVERRIDES)
    if _os.path.exists(country_json_path):
        try:
            with open(country_json_path, encoding="utf-8") as f:
                for entry in _json.load(f):
                    key = entry.get("name", "").upper()
                    if key and key not in name_map:
                        name_map[key] = entry["code"]
        except Exception:
            pass

    if not name_map:
        return 0

    rows = conn.execute("""
        SELECT id, name FROM teams
        WHERE country_code IS NULL OR country_code = ''
    """).fetchall()

    updated = 0
    for row in rows:
        row_id    = row[0] if not hasattr(row, "keys") else row["id"]
        team_name = row[1] if not hasattr(row, "keys") else row["name"]
        if not team_name:
            continue

        clean = team_name.strip()
        for suffix in (" U17", " U18", " U19", " U20", " U21", " U22", " U23",
                       " U16", " U15", " U14", " W", " Women", " Females"):
            if clean.upper().endswith(suffix.upper()):
                clean = clean[: -len(suffix)].strip()
                break

        iso = name_map.get(clean.upper())
        if iso:
            conn.execute(
                "UPDATE teams SET country_code = ? WHERE id = ?",
                (iso, row_id)
            )
            updated += 1

    if updated:
        conn.commit()
        print(f"    [CC] National team country_codes filled: {updated}")

    return updated


def fill_club_team_country_codes(conn=None) -> int:
    """Pass 2 — Fill teams.country_code for club teams via domestic league
    cross-reference. Safe to run repeatedly — only fills NULL/empty rows.

    Returns:
        Number of rows updated.
    """
    conn = conn or _get_conn_ref()

    result = conn.execute("""
        UPDATE teams
        SET country_code = (
            SELECT l.country_code
            FROM schedules s
            JOIN leagues l ON s.league_id = l.league_id
            WHERE (s.home_team_id = teams.team_id OR s.away_team_id = teams.team_id)
              AND l.country_code IS NOT NULL
              AND l.country_code != ''
            ORDER BY l.country_code
            LIMIT 1
        )
        WHERE (country_code IS NULL OR country_code = '')
          AND team_id IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM schedules s
              JOIN leagues l ON s.league_id = l.league_id
              WHERE (s.home_team_id = teams.team_id OR s.away_team_id = teams.team_id)
                AND l.country_code IS NOT NULL
                AND l.country_code != ''
          )
    """)
    updated = result.rowcount
    if updated:
        conn.commit()
        print(f"    [CC] Club team country_codes filled via domestic leagues: {updated}")

    return updated


def fill_all_country_codes(conn=None) -> int:
    """Run both country_code fill passes in order.

    Pass 1 — national teams (name lookup via country.json)
    Pass 2 — club teams (domestic league cross-reference)

    Returns total rows updated across both passes.
    """
    conn = conn or _get_conn_ref()
    total = 0
    total += fill_national_team_country_codes(conn)
    total += fill_club_team_country_codes(conn)
    return total


# ─── Football.com Registry ───

def get_site_match_id(date: str, home: str, away: str) -> str:
    """Generate a unique ID for a site match to prevent duplicates."""
    unique_str = f"{date}_{home}_{away}".lower().strip()
    return hashlib.md5(unique_str.encode()).hexdigest()


def save_site_matches(matches: List[Dict[str, Any]], commit: bool = True):
    """UPSERTs a list of matches extracted from Football.com into the registry."""
    if not matches:
        return

    conn = _get_conn_ref()
    last_extracted = dt.now().isoformat()

    for match in matches:
        site_id = get_site_match_id(match.get('date', ''), match.get('home', ''), match.get('away', ''))
        upsert_fb_match(conn, {
            'site_match_id': site_id,
            'date': match.get('date'),
            'time': match.get('time', 'N/A'),
            'home_team': match.get('home'),
            'away_team': match.get('away'),
            'league': match.get('league'),
            'url': match.get('url'),
            'last_extracted': last_extracted,
            'fixture_id': match.get('fixture_id', ''),
            'matched': match.get('matched', 'No_fs_match_found'),
            'booking_status': match.get('booking_status', 'pending'),
            'booking_details': match.get('booking_details', ''),
            'booking_code': match.get('booking_code', ''),
            'booking_url': match.get('booking_url', ''),
            'status': match.get('status', ''),
        }, commit=False)  # Always skip inner commit

    if commit:
        conn.commit()


def save_match_odds(odds_list: List[Dict[str, Any]], commit: bool = True) -> int:
    """Persist match odds to SQLite immediately. Returns rows written."""
    return upsert_match_odds_batch(_get_conn_ref(), odds_list, commit=commit)


def get_match_odds(fixture_id: str) -> List[Dict[str, Any]]:
    """Return all odds rows for a fixture ordered by rank."""
    conn = _get_conn_ref()
    rows = conn.execute(
        "SELECT * FROM match_odds WHERE fixture_id = ? "
        "ORDER BY rank_in_list ASC",
        (fixture_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def load_site_matches(target_date: str) -> List[Dict[str, Any]]:
    """Loads all extracted site matches for a specific date."""
    return query_all(_get_conn_ref(), 'fb_matches', 'date = ?', (target_date,))


def load_harvested_site_matches(target_date: str) -> List[Dict[str, Any]]:
    """Loads all harvested site matches for a specific date."""
    return query_all(_get_conn_ref(), 'fb_matches',
                     "date = ? AND booking_status = 'harvested'", (target_date,))


def update_site_match_status(site_match_id: str, status: str,
                             fixture_id: Optional[str] = None,
                             details: Optional[str] = None,
                             booking_code: Optional[str] = None,
                             booking_url: Optional[str] = None,
                             matched: Optional[str] = None, commit: bool = True, **kwargs):
    """Updates the booking status, fixture_id, or booking details for a site match."""
    conn = _get_conn_ref()
    updates = {'booking_status': status, 'status': status, 'last_updated': dt.now().isoformat()}
    if fixture_id:
        updates['fixture_id'] = fixture_id
    if details:
        updates['booking_details'] = details
    if booking_code:
        updates['booking_code'] = booking_code
    if booking_url:
        updates['booking_url'] = booking_url
    if matched:
        updates['matched'] = matched
    if 'odds' in kwargs:
        updates['odds'] = kwargs['odds']

    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates['site_match_id'] = site_match_id
    conn.execute(f"UPDATE fb_matches SET {set_clause} WHERE site_match_id = :site_match_id", updates)
    if commit:
        conn.commit()


# ─── Legacy CSV stubs (no-op — writes go through SQLite) ───

def _read_csv(filepath: str) -> List[Dict[str, str]]:
    """Legacy: reads from SQLite instead of CSV."""
    return query_all(_get_conn_ref(), filepath) if filepath else []

def _write_csv(filepath: str, data: List[Dict], fieldnames: List[str]):
    """Legacy no-op: writes go through SQLite now."""
    pass

def _append_to_csv(filepath: str, data_row: Dict, fieldnames: List[str]):
    """Legacy no-op."""
    pass

def upsert_entry(filepath: str, data_row: Dict, fieldnames: List[str], unique_key: str):
    """Legacy: routes to appropriate SQLite upsert."""
    pass

def batch_upsert(filepath: str, data_rows: List[Dict], fieldnames: List[str], unique_key: str):
    """Legacy: routes to appropriate SQLite batch upsert."""
    pass

append_to_csv = _append_to_csv

# Legacy CSV_LOCK — no longer needed, WAL handles concurrency
CSV_LOCK = asyncio.Lock()

# Legacy headers dict — kept for any external code referencing it
files_and_headers = {}
