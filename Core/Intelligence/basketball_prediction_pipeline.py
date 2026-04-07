# basketball_prediction_pipeline.py: Pure DB-driven basketball prediction pipeline.
# Part of LeoBook Core — Intelligence
#
# Functions: get_basketball_fixtures(), build_basketball_input(), run_basketball_predictions()
# Called by: Leo.py (basketball prediction chapter)
#
# Architecture mirror of prediction_pipeline.py.
# Uses BasketballRuleEngine instead of RuleEngine.
# Raw scores passed to EnsembleEngine use {'over', 'under'} schema.

"""
Basketball Prediction Pipeline — Phase 1.
All data sourced from the schedules table (populated by weekly enrichment).
No browser automation. Targets: Total O/U, Team O/U, Halves O/U, Quarters O/U.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from Data.Access.league_db import init_db, computed_standings, get_fb_url_for_league
from Data.Access.db_helpers import save_prediction
from Core.Intelligence.basketball_rule_engine import BasketballRuleEngine
from Core.Intelligence.ensemble import EnsembleEngine
from Core.Intelligence.rule_config import RuleConfig
from Core.Intelligence.rule_engine_manager import RuleEngineManager
from Core.Utils.constants import now_ng

logger = logging.getLogger(__name__)

# Basketball league sport tags — used to filter from the schedules table
# Any league with sport = 'basketball' (or tagged as such in leagues.json) is eligible.
_BASKETBALL_SPORT_VALUES = {"basketball", "nba", "ncaa", "fiba"}

_PREDICTOR_HINT_PATH = Path(__file__).resolve().parents[2] / "Data" / "Store" / "recommender_predictor_hint.json"


def _load_predictor_hint() -> Optional[dict]:
    """Optional recommender->predictor hook."""
    try:
        if _PREDICTOR_HINT_PATH.is_file():
            with open(_PREDICTOR_HINT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _schedule_to_match_dict(row: Dict) -> Dict:
    """
    Convert a schedules table row into the basketball match dict format.

    BasketballTagGenerator._parse_match_scores expects:
        home: str, away: str, home_score: int, away_score: int, date: str

    period_scores: decoded JSON blob from schedules.period_scores column.
        Format: {"q1": {"home": 28, "away": 22}, "q2": ..., "ot": ...}
    """
    home_score = row.get("home_score")
    away_score = row.get("away_score")

    ph = pa = 0
    if home_score is not None and away_score is not None:
        try:
            ph, pa = int(home_score), int(away_score)
        except (ValueError, TypeError):
            ph = pa = 0

    # Decode period_scores: stored as JSON string in SQLite, dict from Supabase
    period_scores = row.get("period_scores")
    if isinstance(period_scores, str):
        try:
            period_scores = json.loads(period_scores)
        except (ValueError, TypeError):
            period_scores = None

    return {
        "home":          row.get("home_team_name", ""),
        "away":          row.get("away_team_name", ""),
        "home_score":    ph,
        "away_score":    pa,
        # Also include score string for any football-style fallback
        "score":         f"{ph}-{pa}",
        "winner":        "Home" if ph > pa else ("Away" if pa > ph else "Draw"),
        "date":          row.get("date", ""),
        "fixture_id":    row.get("fixture_id", ""),
        "period_scores": period_scores,  # {"q1":{"home":28,"away":22}, ...} or None
    }


def get_basketball_fixtures(conn=None, days: int = 7) -> List[Dict]:
    """
    Query schedules for the next N days of basketball matches not yet played.

    Filters by sport='basketball' on the leagues table (LEFT JOINed).
    Returns schedule row dicts.
    """
    conn = conn or init_db()
    now  = now_ng()

    date_strings = []
    for i in range(days + 1):
        target = now + timedelta(days=i)
        date_strings.append(target.strftime("%Y-%m-%d"))

    placeholders = ",".join(["?"] * len(date_strings))
    params = date_strings + list(_BASKETBALL_SPORT_VALUES)

    try:
        rows = conn.execute(
            f"""SELECT
                   COALESCE(NULLIF(s.home_team_name, ''), h.name) AS home_team_name,
                   COALESCE(NULLIF(s.away_team_name, ''), a.name) AS away_team_name,
                   s.*
                FROM schedules s
                LEFT JOIN teams h ON s.home_team_id = h.team_id
                LEFT JOIN teams a ON s.away_team_id = a.team_id
                LEFT JOIN leagues l ON s.league_id = l.league_id
                WHERE s.date IN ({placeholders})
                  AND (s.match_status IS NULL OR s.match_status = 'scheduled' OR s.match_status = '')
                  AND LOWER(COALESCE(l.sport, '')) IN ({','.join(['?']*len(_BASKETBALL_SPORT_VALUES))})
                ORDER BY s.date, s.time""",
            params,
        ).fetchall()
    except Exception as e:
        logger.warning(f"[BB Pipeline] Basketball filter failed ({e}), falling back to all sports.")
        # Graceful degradation: if leagues table has no sport column, skip filter
        rows = conn.execute(
            f"""SELECT
                   COALESCE(NULLIF(s.home_team_name, ''), h.name) AS home_team_name,
                   COALESCE(NULLIF(s.away_team_name, ''), a.name) AS away_team_name,
                   s.*
                FROM schedules s
                LEFT JOIN teams h ON s.home_team_id = h.team_id
                LEFT JOIN teams a ON s.away_team_id = a.team_id
                WHERE s.date IN ({placeholders})
                  AND (s.match_status IS NULL OR s.match_status = 'scheduled' OR s.match_status = '')
                ORDER BY s.date, s.time""",
            date_strings,
        ).fetchall()

    return [dict(r) for r in rows]


def compute_team_form_bb(conn, team_id: str, limit: int = 10) -> List[Dict]:
    """Get last N completed basketball matches for a team."""
    rows = conn.execute(
        """SELECT * FROM schedules
           WHERE (home_team_id = ? OR away_team_id = ?)
             AND home_score IS NOT NULL AND away_score IS NOT NULL
             AND home_score != '' AND away_score != ''
           ORDER BY date DESC
           LIMIT ?""",
        (team_id, team_id, limit),
    ).fetchall()
    return [_schedule_to_match_dict(dict(r)) for r in rows]


def compute_h2h_bb(conn, home_team_id: str, away_team_id: str, limit: int = 10) -> List[Dict]:
    """Get direct H2H matches between two basketball teams."""
    rows = conn.execute(
        """SELECT * FROM schedules
           WHERE ((home_team_id = ? AND away_team_id = ?)
               OR (home_team_id = ? AND away_team_id = ?))
             AND home_score IS NOT NULL AND away_score IS NOT NULL
             AND home_score != '' AND away_score != ''
           ORDER BY date DESC
           LIMIT ?""",
        (home_team_id, away_team_id, away_team_id, home_team_id, limit),
    ).fetchall()
    return [_schedule_to_match_dict(dict(r)) for r in rows]


def build_basketball_input(conn, fixture: Dict) -> Dict[str, Any]:
    """
    Assemble the h2h_data + standings dict that BasketballRuleEngine.analyze() expects.

    Returns:
        {"h2h_data": {...}, "standings": [...], "real_odds": {...}}
    """
    home_team_id   = fixture.get("home_team_id", "")
    away_team_id   = fixture.get("away_team_id", "")
    home_team      = fixture.get("home_team_name", "")
    away_team      = fixture.get("away_team_name", "")
    league_id      = fixture.get("league_id", "")
    country_league = fixture.get("country_league", "")
    season         = fixture.get("season", "")
    fixture_id     = fixture.get("fixture_id", "")

    # 1. Team form (last 10 basketball matches)
    home_form = compute_team_form_bb(conn, home_team_id, limit=10)
    away_form = compute_team_form_bb(conn, away_team_id, limit=10)

    # 2. H2H
    h2h = compute_h2h_bb(conn, home_team_id, away_team_id, limit=10)

    # 3. Standings (computed from schedules; uses points_for/against if stored)
    standings = []
    if league_id:
        standings = computed_standings(conn=conn, league_id=league_id, season=season)

    # 4. Real odds from match_odds table (basketball market IDs)
    #    Structured rows format: list of dicts with category, period, side, line, over_odds, under_odds
    real_odds_rows: List[Dict] = []
    if fixture_id:
        try:
            from Core.Intelligence.basketball_markets import BB_MARKET_CATEGORIES
            rows = conn.execute(
                """SELECT market_id, exact_outcome, line, odds_value,
                          over_odds, under_odds, home_odds, away_odds
                   FROM match_odds WHERE fixture_id = ?""",
                (fixture_id,)
            ).fetchall()
            for r in rows:
                r_dict = dict(r)
                mid = str(r_dict.get("market_id", ""))
                meta = BB_MARKET_CATEGORIES.get(mid, {})
                if not meta:
                    continue
                real_odds_rows.append({
                    "market_id":  mid,
                    "category":   meta.get("category", ""),
                    "period":     meta.get("period", "full"),
                    "side":       meta.get("side", ""),
                    "line":       r_dict.get("line"),
                    "over_odds":  r_dict.get("over_odds") or r_dict.get("odds_value"),
                    "under_odds": r_dict.get("under_odds"),
                    "home_odds":  r_dict.get("home_odds"),
                    "away_odds":  r_dict.get("away_odds"),
                    "odds_value": r_dict.get("odds_value"),
                    "outcome":    r_dict.get("exact_outcome", ""),
                })
        except Exception as e:
            logger.debug(f"[BB Pipeline] Odds query failed for {fixture_id}: {e}")

    h2h_data = {
        "home_team":             home_team,
        "away_team":             away_team,
        "country_league":        country_league or "GLOBAL_BB",
        "home_last_10_matches":  home_form,
        "away_last_10_matches":  away_form,
        "head_to_head":          h2h,
    }

    return {
        "h2h_data":  h2h_data,
        "standings": standings,
        "real_odds": {"rows": real_odds_rows},
    }


def _get_existing_bb_prediction_ids(conn) -> set:
    """Get fixture_ids already predicted for basketball."""
    try:
        rows = conn.execute(
            "SELECT fixture_id FROM predictions WHERE fixture_id IS NOT NULL AND sport = 'basketball'"
        ).fetchall()
        return {r[0] for r in rows}
    except Exception:
        try:
            # Fallback: sport column may not exist yet
            rows = conn.execute(
                "SELECT fixture_id FROM predictions WHERE fixture_id IS NOT NULL"
            ).fetchall()
            return {r[0] for r in rows}
        except Exception:
            return set()


async def run_basketball_predictions(
    conn=None,
    fixtures: List[Dict] = None,
) -> List[Dict]:
    """
    Main basketball prediction loop.

    Mirrors run_predictions() from prediction_pipeline.py exactly.
    Uses BasketballRuleEngine instead of RuleEngine.
    Passes {'over', 'under'} logits to EnsembleEngine.merge().

    Returns:
        List of generated prediction dicts.
    """
    conn = conn or init_db()

    if fixtures is None:
        fixtures = get_basketball_fixtures(conn)

    if not fixtures:
        print("    [BB Predictions] No basketball fixtures found for the next 7 days.")
        return []

    existing_ids = _get_existing_bb_prediction_ids(conn)
    new_fixtures = [f for f in fixtures if f.get("fixture_id") not in existing_ids]

    if not new_fixtures:
        print("    [BB Predictions] All basketball fixtures already predicted.")
        return []

    # Filter past matches
    now       = now_ng()
    today_str = now.strftime("%Y-%m-%d")
    now_time  = now.time()
    eligible  = []

    for f in new_fixtures:
        if f.get("date") == today_str:
            time_str = f.get("time", "")
            try:
                match_time = datetime.strptime(time_str, "%H:%M").time()
                if match_time > now_time:
                    eligible.append(f)
            except (ValueError, TypeError):
                eligible.append(f)
        else:
            eligible.append(f)

    if not eligible:
        print("    [BB Predictions] No eligible basketball fixtures.")
        return []

    print(f"    [BB Predictions] Processing {len(eligible)} basketball fixtures...")

    # Load basketball engine config
    bb_engine_dict = RuleEngineManager.get_engine("basketball_default") or {}
    config = RuleConfig(
        id="basketball_default",
        name="Basketball Default",
        risk_preference=str(
            (bb_engine_dict.get("parameters") or {}).get("risk_preference", "conservative")
        ),
        h2h_lookback_days=int(
            (bb_engine_dict.get("parameters") or {}).get("h2h_lookback_days", 540)
        ),
    )

    predictor_hint  = _load_predictor_hint()
    predictions_made = []
    skipped = 0

    for fixture in eligible:
        fixture_id = fixture.get("fixture_id", "unknown")
        home = fixture.get("home_team_name", "?")
        away = fixture.get("away_team_name", "?")

        try:
            # Build context from DB
            intelligence_context = build_basketball_input(conn, fixture)

            # ALL-OR-NOTHING gate
            home_form_n  = len(intelligence_context["h2h_data"]["home_last_10_matches"])
            away_form_n  = len(intelligence_context["h2h_data"]["away_last_10_matches"])
            standings_n  = len(intelligence_context.get("standings", []))

            if home_form_n < 5 or away_form_n < 5 or standings_n == 0:
                skipped += 1
                logger.warning(
                    f"    [BB Predictions] Skipping {home} vs {away}: "
                    f"Incomplete context (H:{home_form_n}, A:{away_form_n}, S:{standings_n})"
                )
                continue

            # Run symbolic basketball engine
            rule_prediction = BasketballRuleEngine.analyze(intelligence_context, config=config)
            if rule_prediction.get("type") == "SKIP":
                skipped += 1
                logger.debug(f"    [BB] SKIP {home} vs {away}: {rule_prediction.get('reason')}")
                continue

            # Ensemble merge (RL not yet trained for basketball → symbolic_fallback path)
            # When basketball RL is ready, inject rl_logits={"over": p, "under": 1-p}
            richness = EnsembleEngine.get_richness_score(
                fixture.get("league_id", "GLOBAL_BB"),
                current_season=fixture.get("season", ""),
            )
            merged = EnsembleEngine.merge(
                rule_logits=rule_prediction.get("raw_scores", {"over": 1.0, "under": 1.0}),
                rule_conf=rule_prediction.get("market_reliability", 50) / 100.0,
                rl_logits=None,   # Phase 1: no basketball RL model yet
                rl_conf=None,
                league_id=fixture.get("league_id", "GLOBAL_BB"),
                data_richness_score=richness,
            )

            # Build final prediction
            prediction = rule_prediction.copy()
            prediction["sport"]            = "basketball"
            prediction["ensemble_path"]    = merged["path"]
            prediction["ensemble_weights"] = merged["weights"]
            prediction["market_reliability"] = round(merged["confidence"] * 100, 1)

            # Calibrate confidence from merged output
            conf = merged["confidence"]
            if predictor_hint:
                league_name = fixture.get("country_league") or \
                    intelligence_context["h2h_data"].get("country_league", "")
                ema = (predictor_hint.get("league_ema") or {}).get(league_name)
                if ema is not None and isinstance(ema, (int, float)):
                    scale = 1.0 + 0.10 * (float(ema) - 0.5)
                    mr = float(prediction["market_reliability"])
                    prediction["market_reliability"] = round(min(99.0, max(1.0, mr * scale)), 1)
                    conf = prediction["market_reliability"] / 100.0

            if conf > 0.75:   prediction["confidence"] = "Very High"
            elif conf > 0.60: prediction["confidence"] = "High"
            elif conf > 0.45: prediction["confidence"] = "Medium"
            else:             prediction["confidence"] = "Low"

            p_type = prediction.get("type", "SKIP")
            if p_type == "SKIP":
                skipped += 1
                continue

            # Build match_data for save_prediction
            match_data = {
                "fixture_id":    fixture_id,
                "date":          fixture.get("date", ""),
                "match_time":    fixture.get("time", ""),
                "country_league": fixture.get("country_league", ""),
                "home_team":     home,
                "away_team":     away,
                "home_team_id":  fixture.get("home_team_id", ""),
                "away_team_id":  fixture.get("away_team_id", ""),
                "match_link":    fixture.get("match_link", ""),
                "sport":         "basketball",
            }

            save_prediction(match_data, prediction)
            predictions_made.append({**match_data, **prediction})
            print(
                f"      [BB✓] {home} vs {away} → "
                f"{prediction.get('market_prediction', p_type)} "
                f"({prediction.get('confidence', '?')})"
            )

        except Exception as e:
            logger.error(f"      [BB✗] Prediction failed for {home} vs {away}: {e}")
            skipped += 1

    print(f"\n    [BB Predictions] Done: {len(predictions_made)} predictions, {skipped} skipped.")
    return predictions_made
