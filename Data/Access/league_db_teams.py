# league_db_teams.py: Team CRUD operations for the LeoBook SQLite database.
# Part of LeoBook Data — Access Layer

import json
import sqlite3
from typing import Dict, Any, Optional
from Core.Utils.constants import now_ng


def upsert_team(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True) -> int:
    """Insert or update a team by team_id. Returns the row id."""
    now = now_ng().isoformat()
    new_league_ids = data.get("league_ids", [])
    team_id = data.get("team_id")

    # BUG #6 fix: Merge league_ids with existing instead of replacing
    if team_id:
        existing = conn.execute(
            "SELECT league_ids FROM teams WHERE team_id = ?", (team_id,)
        ).fetchone()
        if existing and existing[0]:
            try:
                old_ids = json.loads(existing[0])
                if isinstance(old_ids, list):
                    new_league_ids = list(set(old_ids + new_league_ids))
            except (json.JSONDecodeError, TypeError):
                pass

    league_ids_json = json.dumps(new_league_ids) if new_league_ids else None

    if team_id:
        cur = conn.execute(
            """INSERT INTO teams (team_id, name, league_ids, crest, country_code, url,
                   country, city, stadium, other_names, abbreviations, search_terms, last_updated)
               VALUES (:team_id, :name, :league_ids, :crest, :country_code, :url,
                   :country, :city, :stadium, :other_names, :abbreviations, :search_terms, :last_updated)
               ON CONFLICT(team_id) DO UPDATE SET
                   name           = COALESCE(NULLIF(teams.name, ''), excluded.name),
                   league_ids     = COALESCE(excluded.league_ids, teams.league_ids),
                   crest          = COALESCE(excluded.crest, teams.crest),
                   country_code   = COALESCE(NULLIF(excluded.country_code, ''), teams.country_code),
                   url            = COALESCE(excluded.url, teams.url),
                   country        = COALESCE(excluded.country, teams.country),
                   city           = COALESCE(excluded.city, teams.city),
                   stadium        = COALESCE(excluded.stadium, teams.stadium),
                   other_names    = COALESCE(excluded.other_names, teams.other_names),
                   abbreviations  = COALESCE(excluded.abbreviations, teams.abbreviations),
                   search_terms   = COALESCE(excluded.search_terms, teams.search_terms),
                   last_updated   = excluded.last_updated
            """,
            {
                "team_id": team_id,
                "name": data.get("name", data.get("team_name", "")),
                "league_ids": league_ids_json,
                "crest": data.get("crest", data.get("team_crest")),
                "country_code": data.get("country_code") or None,
                "url": data.get("url", data.get("team_url")),
                "country": data.get("country"),
                "city": data.get("city"),
                "stadium": data.get("stadium"),
                "other_names": data.get("other_names"),
                "abbreviations": data.get("abbreviations"),
                "search_terms": data.get("search_terms"),
                "last_updated": now,
            },
        )
    else:
        # Fallback: no team_id — look up by name+country_code to avoid duplicates
        name = data.get("name", data.get("team_name", ""))
        country_code = data.get("country_code") or None
        existing = None
        if country_code:
            existing = conn.execute(
                "SELECT id FROM teams WHERE name = ? AND country_code = ?",
                (name, country_code),
            ).fetchone()
        if not existing:
            existing = conn.execute(
                "SELECT id FROM teams WHERE name = ?", (name,)
            ).fetchone()

        if existing:
            cur = conn.execute(
                """UPDATE teams SET
                       league_ids   = :league_ids,
                       crest        = COALESCE(:crest, crest),
                       country_code = COALESCE(NULLIF(:country_code, ''), country_code),
                       url          = COALESCE(:url, url),
                       last_updated = :last_updated
                   WHERE id = :row_id""",
                {
                    "league_ids": league_ids_json,
                    "crest": data.get("crest"),
                    "country_code": country_code,
                    "url": data.get("url"),
                    "last_updated": now,
                    "row_id": existing[0],
                },
            )
        else:
            cur = conn.execute(
                """INSERT INTO teams (name, league_ids, crest, country_code, url, last_updated)
                   VALUES (:name, :league_ids, :crest, :country_code, :url, :last_updated)""",
                {
                    "name": name,
                    "league_ids": league_ids_json,
                    "crest": data.get("crest"),
                    "country_code": country_code,
                    "url": data.get("url"),
                    "last_updated": now,
                },
            )
    if commit:
        conn.commit()
    return cur.lastrowid


def get_team_id(conn: sqlite3.Connection, name: str, country_code: str = None) -> Optional[int]:
    """Look up team id by name (and optionally country_code)."""
    if country_code:
        row = conn.execute(
            "SELECT id FROM teams WHERE name = ? AND country_code = ?", (name, country_code)
        ).fetchone()
    else:
        row = conn.execute("SELECT id FROM teams WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else None
