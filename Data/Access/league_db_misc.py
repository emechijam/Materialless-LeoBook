# league_db_misc.py: Misc entity CRUD for the LeoBook SQLite database.
# Part of LeoBook Data — Access Layer
#
# Covers: standings, audit_log, live_scores, fb_matches, countries,
#         accuracy_reports, match_odds, user_credentials, generic query helpers.

import os
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

def log_audit_event(conn: sqlite3.Connection, data: Dict[str, Any],
                    user_id: str = '', commit: bool = True):
    """Insert an audit log entry scoped to user_id."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO audit_log (id, user_id, timestamp, event_type, description,
               balance_before, balance_after, stake, status, last_updated)
           VALUES (:id, :user_id, :timestamp, :event_type, :description,
               :balance_before, :balance_after, :stake, :status, :last_updated)
        """,
        {
            "id": data.get("id", now),
            "user_id": user_id,
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
    """Insert or update a live score entry.

    Columns added for multi-sport support:
      sport       - 'football' | 'basketball' (from extractor)
      part_scores - JSON string of quarter scores for basketball (null for football)
    Both columns are IGNORED gracefully if they don't exist on older DB schemas
    (the INSERT will fail silently on those columns and fall back to the UPDATE).
    Safe approach: try with sport/part_scores, fall back without on OperationalError.
    """
    import json as _j
    now = now_ng().isoformat()

    # Serialize part_scores if present
    ps = data.get('part_scores') or data.get('period_scores')
    if isinstance(ps, dict):
        ps = _j.dumps(ps)
    sport = data.get('sport', 'football')

    _base_params = {
        "fixture_id":     data["fixture_id"],
        "date":           data.get("date"),
        "match_time":     data.get("match_time"),
        "home_team":      data.get("home_team"),
        "away_team":      data.get("away_team"),
        "home_score":     data.get("home_score"),
        "away_score":     data.get("away_score"),
        "minute":         data.get("minute"),
        "status":         data.get("status"),
        "country_league": data.get("country_league"),
        "match_link":     data.get("match_link"),
        "timestamp":      data.get("timestamp", now),
        "last_updated":   now,
    }

    # Try extended INSERT with sport + part_scores first
    try:
        conn.execute(
            """INSERT INTO live_scores (fixture_id, date, match_time,
                   home_team, away_team,
                   home_score, away_score, minute, status,
                   country_league, match_link, sport, part_scores,
                   timestamp, last_updated)
               VALUES (:fixture_id, :date, :match_time,
                   :home_team, :away_team,
                   :home_score, :away_score, :minute, :status,
                   :country_league, :match_link, :sport, :part_scores,
                   :timestamp, :last_updated)
               ON CONFLICT(fixture_id) DO UPDATE SET
                   date           = COALESCE(excluded.date, live_scores.date),
                   match_time     = COALESCE(excluded.match_time, live_scores.match_time),
                   home_score     = excluded.home_score,
                   away_score     = excluded.away_score,
                   minute         = excluded.minute,
                   status         = excluded.status,
                   sport          = COALESCE(excluded.sport, live_scores.sport),
                   part_scores    = COALESCE(excluded.part_scores, live_scores.part_scores),
                   timestamp      = excluded.timestamp,
                   last_updated   = excluded.last_updated
            """,
            {**_base_params, "sport": sport, "part_scores": ps},
        )
    except Exception:
        # Fallback for legacy schema without sport/part_scores columns
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
            _base_params,
        )
    if commit:
        conn.commit()


# ---------------------------------------------------------------------------
# FB Matches
# ---------------------------------------------------------------------------

def upsert_fb_match(conn: sqlite3.Connection, data: Dict[str, Any],
                    user_id: str, commit: bool = True):
    """Insert or update an fb_matches entry scoped to user_id."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO fb_matches (site_match_id, user_id, date, time, home_team, away_team,
               url, last_updated, fixture_id, matched)
           VALUES (:site_match_id, :user_id, :date, :time, :home_team, :away_team,
               :url, :last_updated, :fixture_id, :matched)
           ON CONFLICT(site_match_id, user_id) DO UPDATE SET
               date           = COALESCE(excluded.date, fb_matches.date),
               fixture_id     = COALESCE(excluded.fixture_id, fb_matches.fixture_id),
               matched        = COALESCE(excluded.matched, fb_matches.matched),
               last_updated   = excluded.last_updated
        """,
        {
            "site_match_id": data["site_match_id"],
            "user_id": user_id,
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

def upsert_accuracy_report(conn: sqlite3.Connection, data: Dict[str, Any],
                           user_id: str, commit: bool = True):
    """Insert or update an accuracy report scoped to user_id."""
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO accuracy_reports (report_id, user_id, timestamp, volume, win_rate,
               return_pct, period, last_updated)
           VALUES (:report_id, :user_id, :timestamp, :volume, :win_rate,
               :return_pct, :period, :last_updated)
           ON CONFLICT(report_id, user_id) DO UPDATE SET
               volume     = excluded.volume,
               win_rate   = excluded.win_rate,
               return_pct = excluded.return_pct,
               last_updated = excluded.last_updated
        """,
        {
            "report_id": data["report_id"],
            "user_id": user_id,
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
    _retries: int = 5,
) -> int:
    """Bulk upsert match odds. Returns rows written.

    Retries up to _retries times on 'database is locked' with exponential
    backoff (1s, 2s, 4s, 8s, 16s). This handles multi-process contention
    where two Leo.py sessions (e.g. --chapter 1 and live streamer) share
    the same SQLite file.
    """
    import time as _time

    if not odds_list:
        return 0

    _SQL = """
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
    """
    _rows = [
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
    ]

    for attempt in range(_retries):
        try:
            conn.executemany(_SQL, _rows)
            if commit:
                conn.commit()
            return len(odds_list)
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower() and attempt < _retries - 1:
                wait = 2 ** attempt  # 1, 2, 4, 8, 16 seconds
                print(f"  [DB] upsert_match_odds_batch: locked, retry {attempt + 1}/{_retries - 1} in {wait}s")
                _time.sleep(wait)
            else:
                raise

    return 0  # unreachable — raise above exits first


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


# ---------------------------------------------------------------------------
# User credentials (per-user platform credentials, encrypted at rest)
# ---------------------------------------------------------------------------

def _get_fernet():
    """Return a Fernet cipher using CREDENTIAL_ENCRYPTION_KEY from .env.
    Generates and prints a key if not set (Phase 1 convenience only)."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        raise RuntimeError(
            "cryptography package required for credential storage. "
            "Run: pip install cryptography"
        )
    raw_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
    if not raw_key:
        key = Fernet.generate_key()
        print(
            "[CREDENTIALS] WARNING: CREDENTIAL_ENCRYPTION_KEY not set. "
            f"Add this to .env: CREDENTIAL_ENCRYPTION_KEY={key.decode()}"
        )
        return Fernet(key)
    return Fernet(raw_key.encode())


def store_user_credential(conn: sqlite3.Connection, user_id: str, platform: str,
                          credential_key: str, credential_value: str,
                          commit: bool = True):
    """Store an encrypted credential for user_id on platform."""
    fernet = _get_fernet()
    encrypted = fernet.encrypt(credential_value.encode()).decode()
    now = now_ng().isoformat()
    conn.execute(
        """INSERT INTO user_credentials (user_id, platform, credential_key, credential_value, last_updated)
           VALUES (:user_id, :platform, :credential_key, :credential_value, :last_updated)
           ON CONFLICT(user_id, platform, credential_key) DO UPDATE SET
               credential_value = excluded.credential_value,
               last_updated     = excluded.last_updated
        """,
        {
            "user_id": user_id,
            "platform": platform,
            "credential_key": credential_key,
            "credential_value": encrypted,
            "last_updated": now,
        },
    )
    if commit:
        conn.commit()


def get_user_credential(conn: sqlite3.Connection, user_id: str, platform: str,
                        credential_key: str) -> Optional[str]:
    """Retrieve and decrypt a credential for user_id on platform.
    Returns None if not found."""
    row = conn.execute(
        "SELECT credential_value FROM user_credentials "
        "WHERE user_id = ? AND platform = ? AND credential_key = ?",
        (user_id, platform, credential_key),
    ).fetchone()
    if not row:
        return None
    fernet = _get_fernet()
    return fernet.decrypt(row[0].encode()).decode()


def get_user_platform_credentials(conn: sqlite3.Connection, user_id: str,
                                   platform: str) -> Dict[str, str]:
    """Return all decrypted credentials for user_id on platform as a dict."""
    rows = conn.execute(
        "SELECT credential_key, credential_value FROM user_credentials "
        "WHERE user_id = ? AND platform = ?",
        (user_id, platform),
    ).fetchall()
    if not rows:
        return {}
    fernet = _get_fernet()
    return {r[0]: fernet.decrypt(r[1].encode()).decode() for r in rows}
