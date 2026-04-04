# trainer_context.py: Fixture context builder for RL training rows.
# Part of LeoBook Core — Intelligence (RL Engine)
#
# Functions: build_fixture_context()
# Called by: trainer.py (train_from_fixtures)
#
# Enriches each training fixture with form, H2H, xG, and standing snapshots.
# All queries target the training SQLite connection (no network calls).

"""
Fixture context builder for RL training.

Called once per fixture to populate the enrichment fields (form, H2H, xG,
standings snapshot) needed by the feature encoder and reward functions.
Standings are cached per country_league+date via _standings_cache to avoid
redundant queries across fixtures on the same training day.
"""

import json
from typing import Dict, Any

from Core.Utils.constants import MIN_FORM_MATCHES

# Per-training-session standings cache: keyed by (country_league, date)
_standings_cache: dict = {}


def build_fixture_context(
    conn,
    home_tid: str,
    away_tid: str,
    country_league: str,
    league_id: str,
    season: str,
    f_date: str,
    h_score,
    a_score,
) -> dict:
    """Return a dict of enrichment fields for a single training fixture.

    Args:
        conn:           SQLite connection (read-only during training).
        home_tid:       home_team_id string.
        away_tid:       away_team_id string.
        country_league: Human-readable league label (used as standings cache key).
        league_id:      league_id (used for computed_standings filter).
        season:         Season label (used for standings filter).
        f_date:         Fixture date YYYY-MM-DD (training boundary — all form
                        data must be BEFORE this date to prevent leakage).
        h_score:        Home score (unused here; passed for caller convenience).
        a_score:        Away score (unused here; passed for caller convenience).

    Returns:
        Dict with enrichment fields and `is_complete` flag (True when both
        teams have MIN_FORM_MATCHES results and standings are available).
    """

    def _safe_int(v):
        try:
            return int(v or 0)
        except (ValueError, TypeError):
            return 0

    # 1. Form: last 10 completed results for each team BEFORE f_date ────────
    home_form = conn.execute(
        """SELECT fixture_id, home_team_id, away_team_id, home_score, away_score
           FROM schedules
           WHERE date < ? AND (home_team_id=? OR away_team_id=?)
             AND home_score IS NOT NULL AND away_score IS NOT NULL
           ORDER BY date DESC LIMIT 10""",
        (f_date, home_tid, home_tid)
    ).fetchall()

    away_form = conn.execute(
        """SELECT fixture_id, home_team_id, away_team_id, home_score, away_score
           FROM schedules
           WHERE date < ? AND (home_team_id=? OR away_team_id=?)
             AND home_score IS NOT NULL AND away_score IS NOT NULL
           ORDER BY date DESC LIMIT 10""",
        (f_date, away_tid, away_tid)
    ).fetchall()

    # 2. H2H: last 10 head-to-head fixtures ──────────────────────────────────
    h2h = conn.execute(
        """SELECT fixture_id, home_score, away_score
           FROM schedules
           WHERE ((home_team_id=? AND away_team_id=?) OR (home_team_id=? AND away_team_id=?))
             AND home_score IS NOT NULL AND away_score IS NOT NULL
           ORDER BY date DESC LIMIT 10""",
        (home_tid, away_tid, away_tid, home_tid)
    ).fetchall()

    # 3. Standings snapshot (cached per country_league + date) ──────────────
    global _standings_cache
    cache_key = (country_league, f_date)
    if cache_key not in _standings_cache:
        from Data.Access.league_db import computed_standings
        try:
            rows = computed_standings(
                conn=conn, league_id=league_id, season=season, before_date=f_date
            )
            _standings_cache[cache_key] = [dict(r) for r in rows]
        except Exception:
            _standings_cache[cache_key] = []
    standings = _standings_cache[cache_key]

    # 4. xG proxy: avg goals scored in last 10 per team ─────────────────────
    def _avg_scored(form_rows, team_id):
        goals = []
        for r in form_rows:
            try:
                if r[1] == team_id:
                    goals.append(_safe_int(r[3]))
                else:
                    goals.append(_safe_int(r[4]))
            except Exception:
                pass
        return round(sum(goals) / len(goals), 2) if goals else 0.0

    xg_home = _avg_scored(home_form, home_tid)
    xg_away = _avg_scored(away_form, away_tid)

    hfn  = len(home_form)
    afn  = len(away_form)
    h2h_n = len(h2h)
    st_n  = len(standings)

    is_complete = (hfn >= MIN_FORM_MATCHES and afn >= MIN_FORM_MATCHES and st_n > 0)

    return {
        "is_complete":        is_complete,
        "home_form_n":        hfn,
        "away_form_n":        afn,
        "h2h_count":          h2h_n,
        "h2h_fixture_ids":    json.dumps([r[0] for r in h2h]),
        "form_fixture_ids":   json.dumps(
            [r[0] for r in home_form] + [r[0] for r in away_form]
        ),
        "standings_snapshot": json.dumps(standings),
        "xg_home":            xg_home,
        "xg_away":            xg_away,
        "home_tags":          f"form:{hfn}" if hfn else "",
        "away_tags":          f"form:{afn}" if afn else "",
        "h2h_tags":           f"h2h:{h2h_n}" if h2h_n else "",
        "standings_tags":     f"standings:{st_n}" if st_n else "",
    }


def clear_standings_cache() -> None:
    """Reset the standings cache. Call between training sessions."""
    global _standings_cache
    _standings_cache = {}


__all__ = ["build_fixture_context", "clear_standings_cache"]
