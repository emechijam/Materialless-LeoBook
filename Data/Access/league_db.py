# league_db.py: Unified SQLite database layer for ALL LeoBook data.
# Part of LeoBook Data — Access Layer
#
# This is THE SINGLE source of truth for all persistent data.
# CSV files are auto-imported on first init_db() call, then renamed to .csv.bak.
#
# Entity-specific CRUD has been split into focused sub-modules for maintainability:
#   league_db_leagues.py     — League read/write operations
#   league_db_teams.py       — Team read/write operations
#   league_db_fixtures.py    — Fixture (schedule) read/write operations
#   league_db_predictions.py — Prediction read/write operations
#   league_db_misc.py        — Standings, audit, live scores, fb_matches, countries,
#                              accuracy reports, match odds, and generic helpers
#
# All public symbols are re-exported here so existing imports remain unchanged:
#   from Data.Access.league_db import upsert_fixture   # still works

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from Core.Utils.constants import now_ng
from Data.Access.league_db_schema import (
    _SCHEMA_SQL, _ALTER_MIGRATIONS, _COMPUTED_STANDINGS_SQL,
)

# ── Sub-module re-exports ─────────────────────────────────────────────────────
from Data.Access.league_db_leagues import (       # noqa: F401
    upsert_league, get_league_db_id, mark_league_processed,
    get_unprocessed_leagues, get_leagues_with_gaps, get_leagues_missing_seasons,
    get_stale_leagues, get_all_leagues, get_active_leagues,
)
from Data.Access.league_db_teams import (         # noqa: F401
    upsert_team, get_team_id,
)
from Data.Access.league_db_fixtures import (      # noqa: F401
    upsert_fixture, bulk_upsert_fixtures,
)
from Data.Access.league_db_predictions import (   # noqa: F401
    upsert_prediction, get_predictions, update_prediction,
)
from Data.Access.league_db_misc import (          # noqa: F401
    upsert_standing, get_standings,
    log_audit_event,
    upsert_live_score,
    upsert_fb_match,
    upsert_country,
    upsert_accuracy_report,
    upsert_match_odds_batch,
    query_all, count_rows,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Store")
DB_PATH = os.path.join(DB_DIR, "leobook.db")
LEAGUES_JSON_PATH = os.path.join(DB_DIR, "leagues.json")

# Module-level cache for leagues.json
_leagues_json_cache: Optional[Dict[str, Dict[str, Any]]] = None


def get_fb_url_for_league(conn, league_id: str) -> Optional[str]:
    """
    Returns the fb_url for a league from leagues.json if it has been mapped.
    Cached at module level to avoid redundant disk I/O.
    """
    global _leagues_json_cache

    if _leagues_json_cache is None:
        try:
            if os.path.exists(LEAGUES_JSON_PATH):
                with open(LEAGUES_JSON_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    _leagues_json_cache = {l['league_id']: l for l in data if 'league_id' in l}
            else:
                _leagues_json_cache = {}
        except Exception as e:
            print(f"  [DB] Error loading leagues.json for cache: {e}")
            _leagues_json_cache = {}

    league_entry = _leagues_json_cache.get(league_id)
    return league_entry.get('fb_url') if league_entry else None


# ── Connection ────────────────────────────────────────────────────────────────

def get_connection() -> sqlite3.Connection:
    """Get a thread-safe SQLite connection with WAL mode.
    Auto-recovers from corrupted DB by deleting and recreating."""
    os.makedirs(DB_DIR, exist_ok=True)
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.DatabaseError as e:
        if "malformed" in str(e).lower():
            print(f"  [!] Corrupted DB detected — deleting and recreating: {DB_PATH}")
            try:
                conn.close()
            except Exception:
                pass
            for suffix in ('', '-wal', '-shm'):
                path = DB_PATH + suffix
                if os.path.exists(path):
                    os.remove(path)
            conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=10000")
            conn.row_factory = sqlite3.Row
            return conn
        raise


# ── Computed standings ────────────────────────────────────────────────────────

def computed_standings(conn=None, league_id=None, season=None, before_date=None):
    """Compute league standings on-the-fly from the schedules table.

    Always up-to-date, even during live matches (if scores are propagated).
    Replaces the old standings table (removed in v7.0).

    Args:
        conn:        SQLite connection (optional, uses default)
        league_id:   Filter by league_id (optional)
        season:      Filter by season (optional)
        before_date: Only include matches before this date (YYYY-MM-DD).
                     Used by RL training to reconstruct historical standings.
                     Default None = no date filter (live behaviour preserved).

    Returns:
        List of dicts with: league_id, team_id, team_name, season,
        played, wins, draws, losses, goals_for, goals_against,
        goal_difference, points
    """
    conn = conn or init_db()
    filters = ""
    params = []
    if league_id:
        filters += " AND league_id = ?"
        params.append(league_id)
    if season:
        filters += " AND season = ?"
        params.append(season)
    if before_date:
        filters += " AND date < ?"
        params.append(before_date)

    sql = _COMPUTED_STANDINGS_SQL.format(filters=filters)
    cursor = conn.execute(sql, params)
    columns = [d[0] for d in cursor.description]
    results = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for i, res in enumerate(results):
        res["position"] = i + 1

    return results


# ── Schema migrations ─────────────────────────────────────────────────────────

def _run_alter_migrations(conn: sqlite3.Connection):
    """Add columns to existing tables. Silently skips if column already exists."""
    for table, column, col_type in _ALTER_MIGRATIONS:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    conn.commit()


def _get_table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    """Get list of column names for a table."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [r[1] for r in rows]


def _create_post_alter_indexes(conn: sqlite3.Connection):
    """Create indexes on columns added by ALTER TABLE."""
    post_alter_indexes = [
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_team_id_unique ON teams(team_id)",
        "CREATE INDEX IF NOT EXISTS idx_teams_team_id ON teams(team_id)",
    ]
    for sql in post_alter_indexes:
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.commit()


def _reconstruct_teams_table_if_legacy_unique_exists(conn: sqlite3.Connection):
    """Remove legacy UNIQUE(name, country_code) constraint from teams table."""
    try:
        res = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='teams'").fetchone()
        if not res:
            return
        sql = res[0]

        if "UNIQUE(name, country_code)" not in sql and "UNIQUE (name, country_code)" not in sql:
            return

        print("  [Migration] Removing legacy UNIQUE constraint from teams table...")

        temp_table_sql = """
            CREATE TABLE teams_new (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id             TEXT UNIQUE,
                name                TEXT NOT NULL,
                league_ids          JSON,
                crest               TEXT,
                country_code        TEXT,
                url                 TEXT,
                hq_crest            INTEGER DEFAULT 0,
                country             TEXT,
                city                TEXT,
                stadium             TEXT,
                other_names         TEXT,
                abbreviations       TEXT,
                search_terms        TEXT,
                last_updated        TEXT DEFAULT (datetime('now'))
            )
        """
        conn.execute(temp_table_sql)

        cursor = conn.execute("PRAGMA table_info(teams)")
        existing_cols = [row[1] for row in cursor.fetchall()]

        target_cols = [
            'id', 'team_id', 'name', 'league_ids', 'crest', 'country_code', 'url',
            'hq_crest', 'country', 'city', 'stadium', 'other_names', 'abbreviations',
            'search_terms', 'last_updated'
        ]
        cols_to_copy = [c for c in target_cols if c in existing_cols]
        cols_str = ", ".join(cols_to_copy)

        conn.execute(f"INSERT INTO teams_new ({cols_str}) SELECT {cols_str} FROM teams")
        conn.execute("DROP TABLE teams")
        conn.execute("ALTER TABLE teams_new RENAME TO teams")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_teams_team_id_unique ON teams(team_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_teams_team_id ON teams(team_id)")

        conn.commit()
        print("  [Migration] [OK] Teams table reconstructed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"  [Migration] [!] Error reconstructing teams table: {e}")


def _migrate_match_odds_if_needed(conn: sqlite3.Connection):
    """Drop old match_odds table if it has the legacy schema (last_updated column)."""
    try:
        res = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='match_odds'"
        ).fetchone()
        if not res:
            return
        if 'last_updated' in res[0]:
            print("  [Migration] Dropping legacy match_odds table (schema v7 -> v8)...")
            conn.execute("DROP TABLE IF EXISTS match_odds")
            conn.commit()
            print("  [Migration] [OK] match_odds will be recreated with v8 schema.")
    except Exception as e:
        print(f"  [Migration] [!] match_odds check failed: {e}")


# ── DB initialisation ─────────────────────────────────────────────────────────

def init_db(conn: Optional[sqlite3.Connection] = None) -> sqlite3.Connection:
    """Create all tables, run migrations. Returns the connection."""
    if conn is None:
        conn = get_connection()

    _migrate_match_odds_if_needed(conn)

    conn.executescript(_SCHEMA_SQL)
    conn.commit()

    _run_alter_migrations(conn)
    _create_post_alter_indexes(conn)
    _reconstruct_teams_table_if_legacy_unique_exists(conn)
    _initialize_countries(conn)

    return conn


def _initialize_countries(conn: sqlite3.Connection):
    """Populates countries table from Data/Store/country.json if empty."""
    row_count = conn.execute("SELECT COUNT(*) FROM countries").fetchone()[0]
    if row_count > 0:
        return

    json_path = os.path.join(DB_DIR, "country.json")
    if not os.path.exists(json_path):
        print(f"  [DB] Warning: {json_path} not found. Skipping country init.")
        return

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            countries = json.load(f)

        now = datetime.utcnow().isoformat()
        countries_data = [
            {
                'code': c.get('code'),
                'name': c.get('name'),
                'continent': c.get('continent', ''),
                'capital': c.get('capital', ''),
                'flag_1x1': c.get('flag_1x1', ''),
                'flag_4x3': c.get('flag_4x3', ''),
                'last_updated': now
            }
            for c in countries
        ]

        conn.executemany("""
            INSERT INTO countries (code, name, continent, capital, flag_1x1, flag_4x3, last_updated)
            VALUES (:code, :name, :continent, :capital, :flag_1x1, :flag_4x3, :last_updated)
            ON CONFLICT(code) DO UPDATE SET
                name=excluded.name,
                continent=excluded.continent,
                capital=excluded.capital,
                flag_1x1=excluded.flag_1x1,
                flag_4x3=excluded.flag_4x3,
                last_updated=excluded.last_updated
        """, countries_data)
        conn.commit()
        print(f"  [DB] Initialized {len(countries)} countries from country.json.")
    except Exception as e:
        print(f"  [DB] Error initializing countries: {e}")
