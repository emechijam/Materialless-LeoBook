# league_db_misc.py: Misc entity CRUD for the LeoBook SQLite database.
# Part of LeoBook Data — Access Layer
#
# Covers: standings, audit_log, live_scores, fb_matches, countries,
#         accuracy_reports, match_odds, and generic query helpers.

import sqlite3
from typing import List, Dict, Any, Optional
from Core.Utils.constants import now_ng


# ---------------------------------------------------------------------------
# Standings
# ---------------------------------------------------------------------------

def upsert_standing(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True):
    """Insert or update a standings row."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO standings (standings_key, league_id, team_id, team_name,
               position, played, wins, draws, losses,
               goals_for, goals_against, goal_difference, points,
               country_league, last_updated)
           VALUES (:standings_key, :league_id, :team_id, :team_name,
               :position, :played, :wins, :draws, :losses,
               :goals_for, :goals_against, :goal_difference, :points,
               :country_league, :last_updated)
           ON CONFLICT(standings_key) DO UPDATE SET
               position       = excluded.position,
               played         = excluded.played,
               wins           = excluded.wins,
               draws          = excluded.draws,
               losses         = excluded.losses,
               goals_for      = excluded.goals_for,
               goals_against  = excluded.goals_against,
               goal_difference = excluded.goal_difference,
               points         = excluded.points,
               last_updated   = excluded.last_updated
        """,
        {
            "standings_key": data["standings_key"],
            "league_id": data.get("league_id"),
            "team_id": data.get("team_id"),
            "team_name": data.get("team_name"),
            "position": data.get("position"),
            "played": data.get("played"),
            "wins": data.get("wins"),
            "draws": data.get("draws"),
            "losses": data.get("losses"),
            "goals_for": data.get("goals_for"),
            "goals_against": data.get("goals_against"),
            "goal_difference": data.get("goal_difference"),
            "points": data.get("points"),
            "country_league": data.get("country_league"),
            "last_updated": now,
        },
    )
    if commit:
        conn.commit()


def get_standings(conn: sqlite3.Connection, country_league: str = None) -> List[Dict[str, Any]]:
    """Get standings, optionally filtered by country_league."""
    if country_league:
        rows = conn.execute(
            "SELECT * FROM standings WHERE country_league = ? ORDER BY position",
            (country_league,),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM standings ORDER BY country_league, position").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def log_audit_event(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True):
    """Insert an audit log entry."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO audit_log (id, timestamp, event_type, description,
               balance_before, balance_after, stake, status, last_updated)
           VALUES (:id, :timestamp, :event_type, :description,
               :balance_before, :balance_after, :stake, :status, :last_updated)
        """,
        {
            "id": data.get("id", now),
            "timestamp": data.get("timestamp", now),
            "event_type": data.get("event_type"),
            "description": data.get("description"),
            "balance_before": data.get("balance_before"),
            "balance_after": data.get("balance_after"),
            "stake": data.get("stake"),
            "status": data.get("status"),
            "last_updated": now,
        },
    )
    if commit:
        conn.commit()


# ---------------------------------------------------------------------------
# Live scores
# ---------------------------------------------------------------------------

def upsert_live_score(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True):
    """Insert or update a live score entry."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO live_scores (fixture_id, date, match_time,
               home_team, away_team,
               home_score, away_score, minute, status,
               country_league, match_link, timestamp, last_updated)
           VALUES (:fixture_id, :date, :match_time,
               :home_team, :away_team,
               :home_score, :away_score, :minute, :status,
               :country_league, :match_link, :timestamp, :last_updated)
           ON CONFLICT(fixture_id) DO UPDATE SET
               date           = COALESCE(excluded.date, live_scores.date),
               match_time     = COALESCE(excluded.match_time, live_scores.match_time),
               home_score     = excluded.home_score,
               away_score     = excluded.away_score,
               minute         = excluded.minute,
               status         = excluded.status,
               timestamp      = excluded.timestamp,
               last_updated   = excluded.last_updated
        """,
        {
            "fixture_id": data["fixture_id"],
            "date": data.get("date"),
            "match_time": data.get("match_time"),
            "home_team": data.get("home_team"),
            "away_team": data.get("away_team"),
            "home_score": data.get("home_score"),
            "away_score": data.get("away_score"),
            "minute": data.get("minute"),
            "status": data.get("status"),
            "country_league": data.get("country_league"),
            "match_link": data.get("match_link"),
            "timestamp": data.get("timestamp", now),
            "last_updated": now,
        },
    )
    if commit:
        conn.commit()


# ---------------------------------------------------------------------------
# FB Matches
# ---------------------------------------------------------------------------

def upsert_fb_match(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True):
    """Insert or update an fb_matches entry (sync-safe columns only)."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO fb_matches (site_match_id, date, time, home_team, away_team,
               url, last_updated, fixture_id, matched)
           VALUES (:site_match_id, :date, :time, :home_team, :away_team,
               :url, :last_updated, :fixture_id, :matched)
           ON CONFLICT(site_match_id) DO UPDATE SET
               date           = COALESCE(excluded.date, fb_matches.date),
               fixture_id     = COALESCE(excluded.fixture_id, fb_matches.fixture_id),
               matched        = COALESCE(excluded.matched, fb_matches.matched),
               last_updated   = excluded.last_updated
        """,
        {
            "site_match_id": data["site_match_id"],
            "date": data.get("date"),
            "time": data.get("time", data.get("match_time")),
            "home_team": data.get("home_team"),
            "away_team": data.get("away_team"),
            "url": data.get("url"),
            "last_updated": now,
            "fixture_id": data.get("fixture_id"),
            "matched": data.get("matched"),
        },
    )
    if commit:
        conn.commit()


# ---------------------------------------------------------------------------
# Countries
# ---------------------------------------------------------------------------

def upsert_country(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True):
    """Insert or update a country entry."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO countries (code, name, continent, capital, flag_1x1, flag_4x3, last_updated)
           VALUES (:code, :name, :continent, :capital, :flag_1x1, :flag_4x3, :last_updated)
           ON CONFLICT(code) DO UPDATE SET
               name      = COALESCE(excluded.name, countries.name),
               continent = COALESCE(excluded.continent, countries.continent),
               capital   = COALESCE(excluded.capital, countries.capital),
               flag_1x1  = COALESCE(excluded.flag_1x1, countries.flag_1x1),
               flag_4x3  = COALESCE(excluded.flag_4x3, countries.flag_4x3),
               last_updated = excluded.last_updated
        """,
        {
            "code": data["code"],
            "name": data.get("name"),
            "continent": data.get("continent"),
            "capital": data.get("capital"),
            "flag_1x1": data.get("flag_1x1"),
            "flag_4x3": data.get("flag_4x3"),
            "last_updated": now,
        },
    )
    if commit:
        conn.commit()


# ---------------------------------------------------------------------------
# Accuracy reports
# ---------------------------------------------------------------------------

def upsert_accuracy_report(conn: sqlite3.Connection, data: Dict[str, Any], commit: bool = True):
    """Insert or update an accuracy report."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO accuracy_reports (report_id, timestamp, volume, win_rate,
               return_pct, period, last_updated)
           VALUES (:report_id, :timestamp, :volume, :win_rate,
               :return_pct, :period, :last_updated)
           ON CONFLICT(report_id) DO UPDATE SET
               volume     = excluded.volume,
               win_rate   = excluded.win_rate,
               return_pct = excluded.return_pct,
               last_updated = excluded.last_updated
        """,
        {
            "report_id": data["report_id"],
            "timestamp": data.get("timestamp"),
            "volume": data.get("volume"),
            "win_rate": data.get("win_rate"),
            "return_pct": data.get("return_pct"),
            "period": data.get("period"),
            "last_updated": now,
        },
    )
    if commit:
        conn.commit()


# ---------------------------------------------------------------------------
# Match odds (bulk)
# ---------------------------------------------------------------------------

def upsert_match_odds_batch(
    conn: sqlite3.Connection,
    odds_list: List[Dict[str, Any]],
    commit: bool = True,
) -> int:
    """Bulk upsert match odds. Returns rows written."""
    if not odds_list:
        return 0
    conn.executemany(
        """
        INSERT INTO match_odds (
            fixture_id, site_match_id, market_id, base_market,
            category, exact_outcome, line, odds_value,
            likelihood_pct, rank_in_list, extracted_at
        ) VALUES (
            :fixture_id, :site_match_id, :market_id, :base_market,
            :category, :exact_outcome, :line, :odds_value,
            :likelihood_pct, :rank_in_list, :extracted_at
        )
        ON CONFLICT(fixture_id, market_id, exact_outcome, line)
        DO UPDATE SET
            odds_value   = excluded.odds_value,
            extracted_at = excluded.extracted_at
        """,
        [
            {
                "fixture_id":     o["fixture_id"],
                "site_match_id":  o["site_match_id"],
                "market_id":      o["market_id"],
                "base_market":    o["base_market"],
                "category":       o.get("category", ""),
                "exact_outcome":  o["exact_outcome"],
                "line":           o.get("line") or "",
                "odds_value":     o["odds_value"],
                "likelihood_pct": o.get("likelihood_pct", 0),
                "rank_in_list":   o.get("rank_in_list", 0),
                "extracted_at":   o["extracted_at"],
            }
            for o in odds_list
        ],
    )
    if commit:
        conn.commit()
    return len(odds_list)


# ---------------------------------------------------------------------------
# Generic query helpers
# ---------------------------------------------------------------------------

def query_all(conn: sqlite3.Connection, table: str, where: str = None,
              params: tuple = (), order_by: str = None) -> List[Dict[str, Any]]:
    """Generic SELECT * from table with optional WHERE and ORDER BY."""
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    """Count rows in a table."""
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
