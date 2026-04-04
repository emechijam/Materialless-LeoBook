# league_db_leagues.py: League CRUD operations for the LeoBook SQLite database.
# Part of LeoBook Data — Access Layer
#
# Imported by league_db.py (re-exported) and used directly by enrichment modules.

import sqlite3
from typing import List, Dict, Any, Optional
from Core.Utils.constants import now_ng


def upsert_league(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True) -> int:
    """Insert or update a league. Returns the row id."""
    now = now_ng().isoformat()
    cur = conn.execute(
        """INSERT INTO leagues (league_id, fs_league_id, country_code, continent, name, crest,
               current_season, url, region, region_flag, region_url,
               other_names, abbreviations, search_terms, date_updated, last_updated)
           VALUES (:league_id, :fs_league_id, :country_code, :continent, :name, :crest,
               :current_season, :url, :region, :region_flag, :region_url,
               :other_names, :abbreviations, :search_terms, :date_updated, :last_updated)
           ON CONFLICT(league_id) DO UPDATE SET
               fs_league_id   = COALESCE(excluded.fs_league_id, leagues.fs_league_id),
               country_code   = COALESCE(excluded.country_code, leagues.country_code),
               continent      = COALESCE(excluded.continent, leagues.continent),
               name           = COALESCE(excluded.name, leagues.name),
               crest          = COALESCE(excluded.crest, leagues.crest),
               current_season = COALESCE(excluded.current_season, leagues.current_season),
               url            = COALESCE(excluded.url, leagues.url),
               region         = COALESCE(excluded.region, leagues.region),
               region_flag    = COALESCE(excluded.region_flag, leagues.region_flag),
               region_url     = COALESCE(excluded.region_url, leagues.region_url),
               other_names    = COALESCE(excluded.other_names, leagues.other_names),
               abbreviations  = COALESCE(excluded.abbreviations, leagues.abbreviations),
               search_terms   = COALESCE(excluded.search_terms, leagues.search_terms),
               date_updated   = COALESCE(excluded.date_updated, leagues.date_updated),
               last_updated   = excluded.last_updated
        """,
        {
            "league_id": data["league_id"],
            "fs_league_id": data.get("fs_league_id"),
            "country_code": data.get("country_code"),
            "continent": data.get("continent"),
            "name": data.get("name", data.get("league", "")),
            "crest": data.get("crest", data.get("league_crest")),
            "current_season": data.get("current_season"),
            "url": data.get("url", data.get("league_url")),
            "region": data.get("region"),
            "region_flag": data.get("region_flag"),
            "region_url": data.get("region_url"),
            "other_names": data.get("other_names"),
            "abbreviations": data.get("abbreviations"),
            "search_terms": data.get("search_terms"),
            "date_updated": data.get("date_updated"),
            "last_updated": now,
        },
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def get_league_db_id(conn: sqlite3.Connection, league_id: str) -> Optional[int]:
    """Get the auto-increment id for a league by its league_id string."""
    row = conn.execute("SELECT id FROM leagues WHERE league_id = ?", (league_id,)).fetchone()
    return row["id"] if row else None


def mark_league_processed(conn: sqlite3.Connection, league_id: str, commit: bool = True):
    """Flag a league as fully enriched."""
    conn.execute(
        "UPDATE leagues SET processed = 1, last_updated = ? WHERE league_id = ?",
        (now_ng().isoformat(), league_id),
    )
    if commit:
        conn.commit()


def get_unprocessed_leagues(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return all leagues not yet processed."""
    rows = conn.execute(
        "SELECT * FROM leagues WHERE processed = 0 ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


def get_leagues_with_gaps(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return leagues with missing critical enrichment data.

    Checks: fs_league_id, region, crest, current_season.
    """
    rows = conn.execute(
        """SELECT * FROM leagues
           WHERE url IS NOT NULL AND url != ''
             AND (
               processed = 0
               OR fs_league_id IS NULL OR fs_league_id = ''
               OR region IS NULL OR region = ''
               OR crest IS NULL OR crest = ''
               OR current_season IS NULL OR current_season = ''
             )
           ORDER BY id"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_leagues_missing_seasons(conn: sqlite3.Connection, min_seasons: int = 2) -> List[Dict[str, Any]]:
    """Return processed leagues that have fewer than min_seasons in the schedules table."""
    rows = conn.execute("""
        SELECT league_id FROM schedules
        WHERE season IS NOT NULL AND season != ''
        GROUP BY league_id
        HAVING COUNT(DISTINCT season) >= ?
    """, (min_seasons,)).fetchall()

    ok_ids = {r[0] for r in rows}
    all_processed = conn.execute("SELECT * FROM leagues WHERE processed = 1 AND url != ''").fetchall()

    return [dict(row) for row in all_processed if row['league_id'] not in ok_ids]


def get_stale_leagues(conn: sqlite3.Connection, days: int = 7) -> List[Dict[str, Any]]:
    """Return leagues not updated in the last N days."""
    rows = conn.execute(
        """SELECT * FROM leagues
           WHERE url IS NOT NULL AND url != ''
             AND (
               last_updated IS NULL
               OR last_updated < datetime('now', ? || ' days')
             )
           ORDER BY id""",
        (f"-{days}",)
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_leagues(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Return ALL leagues that have a Flashscore URL (for --reload)."""
    rows = conn.execute(
        """SELECT * FROM leagues
           WHERE url IS NOT NULL AND url != ''
           ORDER BY id"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_active_leagues(conn: sqlite3.Connection, days: int = 7) -> List[Dict[str, Any]]:
    """Return leagues that have fixtures within ±N days of today (for --refresh)."""
    rows = conn.execute(
        """SELECT DISTINCT l.*
           FROM leagues l
           INNER JOIN schedules s ON s.league_id = l.league_id
           WHERE l.url IS NOT NULL AND l.url != ''
             AND s.date >= date('now', ? || ' days')
             AND s.date <= date('now', '+' || ? || ' days')
           ORDER BY l.id""",
        (f"-{days}", str(days))
    ).fetchall()
    return [dict(r) for r in rows]
