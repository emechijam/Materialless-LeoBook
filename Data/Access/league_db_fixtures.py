# league_db_fixtures.py: Fixture (schedule) CRUD operations for the LeoBook SQLite database.
# Part of LeoBook Data — Access Layer

import json
import sqlite3
from typing import List, Dict, Any
from Core.Utils.constants import now_ng


def upsert_fixture(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True) -> int:
    """Insert or update a fixture. Returns the row id."""
    now = now_ng().isoformat()
    extra_json = json.dumps(data.get("extra")) if data.get("extra") else None

    cur = conn.execute(
        """INSERT INTO schedules (
               fixture_id, date, time, league_id,
               home_team_id, home_team_name, away_team_id, away_team_name,
               home_score, away_score, extra, league_stage,
               match_status, season, home_crest, away_crest, url,
               country_league, match_link,
               home_red_cards, away_red_cards, winner,
               last_updated
           ) VALUES (
               :fixture_id, :date, :time, :league_id,
               :home_team_id, :home_team_name, :away_team_id, :away_team_name,
               :home_score, :away_score, :extra, :league_stage,
               :match_status, :season, :home_crest, :away_crest, :url,
               :country_league, :match_link,
               :home_red_cards, :away_red_cards, :winner,
               :last_updated
           )
           ON CONFLICT(fixture_id) DO UPDATE SET
               date           = COALESCE(excluded.date, schedules.date),
               time           = COALESCE(excluded.time, schedules.time),
               home_team_id   = COALESCE(excluded.home_team_id, schedules.home_team_id),
               home_team_name = COALESCE(excluded.home_team_name, schedules.home_team_name),
               away_team_id   = COALESCE(excluded.away_team_id, schedules.away_team_id),
               away_team_name = COALESCE(excluded.away_team_name, schedules.away_team_name),
               home_score     = COALESCE(excluded.home_score, schedules.home_score),
               away_score     = COALESCE(excluded.away_score, schedules.away_score),
               extra          = COALESCE(excluded.extra, schedules.extra),
               match_status   = COALESCE(excluded.match_status, schedules.match_status),
               home_crest     = COALESCE(excluded.home_crest, schedules.home_crest),
               away_crest     = COALESCE(excluded.away_crest, schedules.away_crest),
               country_league  = COALESCE(excluded.country_league, schedules.country_league),
               match_link     = COALESCE(excluded.match_link, schedules.match_link),
               home_red_cards = COALESCE(excluded.home_red_cards, schedules.home_red_cards),
               away_red_cards = COALESCE(excluded.away_red_cards, schedules.away_red_cards),
               winner         = COALESCE(excluded.winner, schedules.winner),
               last_updated   = excluded.last_updated
        """,
        {
            "fixture_id": data.get("fixture_id", ""),
            "date": data.get("date"),
            "time": data.get("time", data.get("match_time")),
            "league_id": data.get("league_id"),
            "home_team_id": data.get("home_team_id"),
            "home_team_name": data.get("home_team_name", data.get("home_team")),
            "away_team_id": data.get("away_team_id"),
            "away_team_name": data.get("away_team_name", data.get("away_team")),
            "home_score": data.get("home_score"),
            "away_score": data.get("away_score"),
            "extra": extra_json,
            "league_stage": data.get("league_stage"),
            "match_status": data.get("match_status"),
            "season": data.get("season"),
            "home_crest": data.get("home_crest"),
            "away_crest": data.get("away_crest"),
            "url": data.get("url"),
            "country_league": data.get("country_league"),
            "match_link": data.get("match_link"),
            "home_red_cards": data.get("home_red_cards", 0),
            "away_red_cards": data.get("away_red_cards", 0),
            "winner": data.get("winner"),
            "last_updated": now,
        },
    )
    if commit:
        conn.commit()
    return cur.lastrowid


def bulk_upsert_fixtures(conn: sqlite3.Connection, fixtures: List[Dict[str, Any]], commit: bool = True):
    """Batch insert/update fixtures for performance."""
    now = now_ng().isoformat()
    rows = []
    for f in fixtures:
        extra_json = json.dumps(f.get("extra")) if f.get("extra") else None
        rows.append((
            f.get("fixture_id", ""), f.get("date"), f.get("time", f.get("match_time")),
            f.get("league_id"),
            f.get("home_team_id"), f.get("home_team_name", f.get("home_team")),
            f.get("away_team_id"), f.get("away_team_name", f.get("away_team")),
            f.get("home_score"), f.get("away_score"),
            extra_json, f.get("league_stage"),
            f.get("match_status"), f.get("season"),
            f.get("home_crest"), f.get("away_crest"),
            f.get("url"), f.get("country_league"), f.get("match_link"),
            f.get("home_red_cards", 0), f.get("away_red_cards", 0), f.get("winner"),
            now,
        ))
    conn.executemany(
        """INSERT INTO schedules (
               fixture_id, date, time, league_id,
               home_team_id, home_team_name, away_team_id, away_team_name,
               home_score, away_score, extra, league_stage,
               match_status, season, home_crest, away_crest, url,
               country_league, match_link,
               home_red_cards, away_red_cards, winner,
               last_updated
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(fixture_id) DO UPDATE SET
               date           = COALESCE(excluded.date, schedules.date),
               time           = COALESCE(excluded.time, schedules.time),
               league_id      = COALESCE(excluded.league_id, schedules.league_id),
               home_team_id   = COALESCE(excluded.home_team_id, schedules.home_team_id),
               home_team_name = COALESCE(excluded.home_team_name, schedules.home_team_name),
               away_team_id   = COALESCE(excluded.away_team_id, schedules.away_team_id),
               away_team_name = COALESCE(excluded.away_team_name, schedules.away_team_name),
               home_score     = COALESCE(excluded.home_score, schedules.home_score),
               away_score     = COALESCE(excluded.away_score, schedules.away_score),
               extra          = COALESCE(excluded.extra, schedules.extra),
               league_stage   = COALESCE(excluded.league_stage, schedules.league_stage),
               match_status   = COALESCE(excluded.match_status, schedules.match_status),
               season         = COALESCE(excluded.season, schedules.season),
               home_crest     = COALESCE(excluded.home_crest, schedules.home_crest),
               away_crest     = COALESCE(excluded.away_crest, schedules.away_crest),
               url            = COALESCE(excluded.url, schedules.url),
               country_league  = COALESCE(excluded.country_league, schedules.country_league),
               match_link     = COALESCE(excluded.match_link, schedules.match_link),
               home_red_cards = COALESCE(excluded.home_red_cards, schedules.home_red_cards),
               away_red_cards = COALESCE(excluded.away_red_cards, schedules.away_red_cards),
               winner         = COALESCE(excluded.winner, schedules.winner),
               last_updated   = excluded.last_updated
        """,
        rows,
    )
    if commit:
        conn.commit()
