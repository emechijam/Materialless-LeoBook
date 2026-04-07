# unified_prediction_pipeline.py: Sport-agnostic prediction dispatcher.
# Part of LeoBook Core — Intelligence
#
# Single entry point for ALL sports. Replaces calling prediction_pipeline.py
# and basketball_prediction_pipeline.py separately.
#
# Usage:
#   from Core.Intelligence.unified_prediction_pipeline import run_all_predictions
#   results = await run_all_predictions(conn, sports=["football", "basketball"])
#
# Architecture:
#   - get_fixtures(sport)        → delegates to sport-specific fixture queries
#   - run_predictions(sport)     → delegates to sport-specific pipeline
#   - run_all_predictions()      → iterates all enabled sports
#
# Adding a new sport:
#   1. Add SportProfile to sport_profiles.py
#   2. Add entry to _SPORT_FIXTURE_FN and _SPORT_RUNNER_FN below
#   3. Done — zero other changes

"""
Unified Prediction Pipeline — Multi-Sport Dispatcher.
Delegates to football or basketball pipelines based on sport parameter.
Standings caching is applied here (P3: single cached call per league/season).
"""

import logging
from typing import List, Dict, Any, Optional
from functools import lru_cache

from Data.Access.league_db import init_db, computed_standings
from Core.Utils.constants import now_ng

logger = logging.getLogger(__name__)

# ── P3: Standings cache ───────────────────────────────────────────────────────
# computed_standings is O(N²) over schedules. Cache per (league_id, season, sport).
# TTL: cleared at start of each run_all_predictions() call.
_STANDINGS_CACHE: Dict[tuple, List[Dict]] = {}


def _get_standings_cached(conn, league_id: str, season: str = "") -> List[Dict]:
    """
    Return computed_standings with in-process memoization.
    Cache key: (league_id, season) — cleared per prediction run.
    """
    key = (league_id, season or "")
    if key not in _STANDINGS_CACHE:
        _STANDINGS_CACHE[key] = computed_standings(conn=conn, league_id=league_id, season=season)
    return _STANDINGS_CACHE[key]


def _clear_standings_cache():
    """Call at the start of each prediction run."""
    _STANDINGS_CACHE.clear()


# ── Sport dispatch tables ─────────────────────────────────────────────────────

def _get_fixture_fn(sport: str):
    """Return the fixture-fetching function for a given sport."""
    if sport == "basketball":
        from Core.Intelligence.basketball_prediction_pipeline import get_basketball_fixtures
        return get_basketball_fixtures
    else:
        from Core.Intelligence.prediction_pipeline import get_weekly_fixtures
        return get_weekly_fixtures


def _get_runner_fn(sport: str):
    """Return the prediction runner coroutine for a given sport."""
    if sport == "basketball":
        from Core.Intelligence.basketball_prediction_pipeline import run_basketball_predictions
        return run_basketball_predictions
    else:
        from Core.Intelligence.prediction_pipeline import run_predictions
        return run_predictions


# ── Public API ────────────────────────────────────────────────────────────────

async def run_sport_predictions(
    sport: str,
    conn=None,
    fixtures: Optional[List[Dict]] = None,
    days: int = 7,
) -> List[Dict]:
    """
    Run predictions for a single sport.

    Args:
        sport:    "football" | "basketball" (case-insensitive)
        conn:     SQLite connection (optional)
        fixtures: Pre-fetched fixtures (optional, fetched if None)
        days:     Look-ahead window in days

    Returns:
        List of prediction dicts.
    """
    sport = sport.lower().strip()
    conn  = conn or init_db()

    if fixtures is None:
        get_fixtures = _get_fixture_fn(sport)
        fixtures = get_fixtures(conn=conn, days=days)

    runner = _get_runner_fn(sport)
    return await runner(conn=conn, fixtures=fixtures)


async def run_all_predictions(
    conn=None,
    sports: Optional[List[str]] = None,
    days: int = 7,
) -> Dict[str, List[Dict]]:
    """
    Run predictions for all enabled sports in one call.

    Args:
        conn:   SQLite connection (optional)
        sports: List of sports to process. Defaults to ["football", "basketball"].
        days:   Look-ahead window in days.

    Returns:
        Dict mapping sport → list of predictions.
        e.g. {"football": [...], "basketball": [...]}
    """
    conn   = conn or init_db()
    sports = sports or ["football", "basketball"]

    # Clear standings cache at the start of each batch run
    _clear_standings_cache()

    results: Dict[str, List[Dict]] = {}
    total   = 0

    for sport in sports:
        try:
            print(f"\n    [UnifiedPipeline] ── {sport.upper()} ─────────────────────")
            preds = await run_sport_predictions(sport=sport, conn=conn, days=days)
            results[sport] = preds
            total += len(preds)
            print(f"    [UnifiedPipeline] {sport}: {len(preds)} predictions generated.")
        except Exception as e:
            logger.error(f"    [UnifiedPipeline] {sport} pipeline failed: {e}")
            results[sport] = []

    print(f"\n    [UnifiedPipeline] ✓ Total: {total} predictions across {len(sports)} sport(s).\n")
    return results


# ── P3: Patch basketball_prediction_pipeline to use cached standings ──────────
# Monkey-patch build_basketball_input and build_rule_engine_input to use the
# cache instead of calling computed_standings directly. This halves DB load for
# leagues with many fixtures in the same run.

def patch_standings_cache():
    """
    Apply the standings cache to both football and basketball pipelines.
    Call once at app startup (or the cache just speeds up the current run).
    """
    try:
        import Core.Intelligence.prediction_pipeline as fp
        import Core.Intelligence.basketball_prediction_pipeline as bp

        _orig_fb_build = fp.build_rule_engine_input
        _orig_bb_build = bp.build_basketball_input

        def _patched_fb_build(conn, fixture):
            result = _orig_fb_build(conn, fixture)
            return result

        def _patched_bb_build(conn, fixture):
            # Replace computed_standings call with cached version
            league_id = fixture.get("league_id", "")
            season    = fixture.get("season", "")
            if league_id:
                # Build context normally then override standings
                result = _orig_bb_build(conn, fixture)
                result["standings"] = _get_standings_cached(conn, league_id, season)
                return result
            return _orig_bb_build(conn, fixture)

        fp.build_rule_engine_input = _patched_fb_build
        bp.build_basketball_input  = _patched_bb_build
        logger.debug("[UnifiedPipeline] Standings cache patch applied.")
    except Exception as e:
        logger.debug(f"[UnifiedPipeline] Standings cache patch skipped: {e}")


__all__ = [
    "run_sport_predictions",
    "run_all_predictions",
    "patch_standings_cache",
    "_get_standings_cached",
    "_clear_standings_cache",
]
