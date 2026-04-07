# basketball_rule_engine.py: Symbolic Rule Engine for basketball O/U markets.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: BasketballRuleEngine
# Markets: Total O/U, Team O/U (home/away), Halves O/U, Quarters O/U
#
# Architecture mirror of rule_engine.py — same contract so ensemble.py,
# progressive_backtester.py, and prediction_pipeline work with zero changes.
#
# Output contract (raw_scores keys):
#   {"over": float, "under": float}   — symbolic vote totals for ensemble merge

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from Core.Intelligence.basketball_tag_generator import BasketballTagGenerator
from Core.Intelligence.basketball_pts_predictor import BasketballPtsPredictor
from Core.Intelligence.basketball_markets import generate_bb_predictions, select_best_bb_market
from Core.Intelligence.learning_engine import LearningEngine
from Core.Intelligence.rule_config import RuleConfig


class BasketballRuleEngine:
    """
    Symbolic prediction engine for basketball Over/Under markets.

    analyze() signature identical to football RuleEngine.analyze() for full
    compatibility with the ensemble, backtester, and prediction pipeline.

    Flow:
        1. Data-readiness gate (All-or-Nothing Contract)
        2. Tag generation (form / H2H / standings)
        3. Expected points via Normal distribution (BasketballPtsPredictor)
        4. Symbolic over/under vote using loaded region weights
        5. Full market predictions via generate_bb_predictions()
        6. Stairway gate via select_best_bb_market()
        7. Return structured prediction compatible with EnsembleEngine.merge()
    """

    # Weight keys used in learning_engine — must match BB_DEFAULT_WEIGHTS keys
    _WEIGHT_KEYS = [
        "bb_form_high_scoring",
        "bb_form_low_scoring",
        "bb_form_strong_defense",
        "bb_form_weak_defense",
        "bb_form_high_pace",
        "bb_form_low_pace",
        "bb_h2h_total_over",
        "bb_h2h_total_under",
        "bb_h2h_home_dom",
        "bb_h2h_away_dom",
        "bb_standings_elite_offense",
        "bb_standings_elite_defense",
        "bb_xpts_high_total",
        "bb_xpts_low_total",
    ]

    # Thresholds for expected-points voting
    _XPTS_HIGH_TOTAL = 228.0   # Expected total → strong OVER signal
    _XPTS_LOW_TOTAL  = 212.0   # Expected total → strong UNDER signal

    # Minimum form matches per team (mirrors MIN_FORM_MATCHES for football)
    _MIN_FORM_MATCHES = 5

    @staticmethod
    def analyze(
        context: Dict[str, Any],
        config: Optional[RuleConfig] = None,
        live_odds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Main basketball prediction entry point.

        Args:
            context:    Same structure as football pipeline:
                        {"h2h_data": {...}, "standings": [...], "real_odds": {...}}
                        real_odds may contain structured rows (see generate_bb_predictions).
            config:     Optional RuleConfig (defaults to basketball_default engine).
            live_odds:  Not used directly — odds come through context["real_odds"].

        Returns:
            Rich prediction dict or {"type": "SKIP", ...} on failure.
        """
        if config is None:
            config = RuleConfig(
                id="basketball_default",
                name="Basketball Default",
                description="O/U focused symbolic engine for basketball",
                risk_preference="conservative",
            )

        h2h_data     = context.get("h2h_data", {})
        standings    = context.get("standings", [])
        home_team    = h2h_data.get("home_team")
        away_team    = h2h_data.get("away_team")
        country_league = h2h_data.get("country_league", "GLOBAL_BB")

        # ── Basic sanity ─────────────────────────────────────────────────────
        if not home_team or not away_team:
            return {"type": "SKIP", "confidence": "Low", "reason": "Missing team names"}

        # Scope filter (reuses RuleConfig.matches_scope)
        if not config.matches_scope(country_league, home_team, away_team):
            return {"type": "SKIP", "confidence": "Low", "reason": "Outside engine scope"}

        home_form = [m for m in h2h_data.get("home_last_10_matches", []) if m][:10]
        away_form = [m for m in h2h_data.get("away_last_10_matches", []) if m][:10]
        h2h_raw   = h2h_data.get("head_to_head", [])

        # ── ALL-OR-NOTHING CONTRACT ──────────────────────────────────────────
        hfn = len(home_form)
        afn = len(away_form)
        stn = len(standings)
        if hfn < BasketballRuleEngine._MIN_FORM_MATCHES or \
           afn < BasketballRuleEngine._MIN_FORM_MATCHES or \
           stn == 0:
            return {
                "type": "SKIP",
                "confidence": "Low",
                "reason": f"Contract violation: H:{hfn}, A:{afn}, Standings:{stn}",
            }

        # H2H lookback filter (reuse config.h2h_lookback_days)
        try:
            from Core.Utils.constants import now_ng
            cutoff = now_ng() - timedelta(days=config.h2h_lookback_days)
        except Exception:
            cutoff = datetime.utcnow() - timedelta(days=config.h2h_lookback_days)

        h2h = []
        for m in h2h_raw:
            if not m:
                continue
            try:
                date_str = m.get("date", "")
                if date_str:
                    if "-" in date_str and len(date_str.split("-")[0]) == 4:
                        d = datetime.strptime(date_str, "%Y-%m-%d")
                    else:
                        d = datetime.strptime(date_str, "%d.%m.%Y")
                    if d >= cutoff:
                        h2h.append(m)
                else:
                    h2h.append(m)
            except Exception:
                h2h.append(m)

        # ── TAG GENERATION ───────────────────────────────────────────────────
        home_tags      = BasketballTagGenerator.generate_form_tags(home_form, home_team, True)
        away_tags      = BasketballTagGenerator.generate_form_tags(away_form, away_team, False)
        h2h_tags       = BasketballTagGenerator.generate_h2h_tags(h2h, home_team, away_team)
        standings_tags = BasketballTagGenerator.generate_standings_tags(standings, home_team, away_team)

        all_tags = set(home_tags + away_tags + h2h_tags + standings_tags)

        # ── EXPECTED POINTS (Normal model) ───────────────────────────────────
        pts = BasketballPtsPredictor.get_match_expected_points(
            home_form, away_form, home_team, away_team
        )
        total_exp     = pts["total_expected"]
        home_expected = pts["home_expected"]
        away_expected = pts["away_expected"]

        # ── LEARNED WEIGHTS ──────────────────────────────────────────────────
        weights = LearningEngine.load_weights(country_league)

        # ── SYMBOLIC VOTING ──────────────────────────────────────────────────
        over_score  = 0.0
        under_score = 0.0
        reasoning   = []

        _w = lambda key, default: float(weights.get(key, default))

        # Form signals
        if any("HIGH_SCORING" in t for t in home_tags + away_tags):
            over_score += _w("bb_form_high_scoring", 4.0)
            reasoning.append("High-scoring form boosted OVER")

        if any("LOW_SCORING" in t for t in home_tags + away_tags):
            under_score += _w("bb_form_low_scoring", 3.5)
            reasoning.append("Low-scoring form boosted UNDER")

        if any("STRONG_DEFENSE" in t for t in home_tags + away_tags):
            under_score += _w("bb_form_strong_defense", 4.5)
            reasoning.append("Strong defense boosted UNDER")

        if any("WEAK_DEFENSE" in t for t in home_tags + away_tags):
            over_score += _w("bb_form_weak_defense", 3.5)
            reasoning.append("Weak defense boosted OVER")

        if any("HIGH_PACE" in t for t in home_tags + away_tags):
            over_score += _w("bb_form_high_pace", 3.0)
            reasoning.append("High-pace teams boosted OVER")

        if any("LOW_PACE" in t for t in home_tags + away_tags):
            under_score += _w("bb_form_low_pace", 3.0)
            reasoning.append("Low-pace teams boosted UNDER")

        # H2H signals
        if "H2H_TOTAL_OVER_220" in h2h_tags:
            over_score += _w("bb_h2h_total_over", 5.0)
            reasoning.append("H2H historically high-scoring")

        if "H2H_TOTAL_UNDER_210" in h2h_tags:
            under_score += _w("bb_h2h_total_under", 5.0)
            reasoning.append("H2H historically low-scoring")

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        if f"{home_slug}_H2H_DOM" in h2h_tags:
            # Home domination → more competitive game → slight over signal
            over_score += _w("bb_h2h_home_dom", 1.5)
        if f"{away_slug}_H2H_DOM" in h2h_tags:
            over_score += _w("bb_h2h_away_dom", 1.5)

        # Standings signals
        if any("ELITE_OFFENSE" in t for t in standings_tags):
            over_score += _w("bb_standings_elite_offense", 3.5)
            reasoning.append("Elite offense in standings")

        if any("ELITE_DEFENSE" in t for t in standings_tags):
            under_score += _w("bb_standings_elite_defense", 3.5)
            reasoning.append("Elite defense in standings")

        # Expected-points delta vs typical thresholds
        if total_exp >= BasketballRuleEngine._XPTS_HIGH_TOTAL:
            over_score += _w("bb_xpts_high_total", 6.0)
            reasoning.append(f"xPts {total_exp} → OVER signal")
        elif total_exp <= BasketballRuleEngine._XPTS_LOW_TOTAL:
            under_score += _w("bb_xpts_low_total", 6.0)
            reasoning.append(f"xPts {total_exp} → UNDER signal")

        # ── FULL MARKET PREDICTIONS (Normal model + extracted odds) ──────────
        real_odds_context = context.get("real_odds", {})
        # Structured rows (from fb_basketball_odds.py) come through "rows" key.
        # If not present, extracted_rows is empty → generate_bb_predictions falls
        # back to synthetic probability at expected line.
        extracted_rows = []
        if isinstance(real_odds_context, dict):
            extracted_rows = real_odds_context.get("rows", [])
        elif isinstance(real_odds_context, list):
            extracted_rows = real_odds_context  # direct list format

        bb_predictions = generate_bb_predictions(
            extracted_rows=extracted_rows,
            home_avg=pts["home_avg_used"],
            away_avg=pts["away_avg_used"],
        )

        best_market = select_best_bb_market(bb_predictions)

        if not best_market:
            return {
                "type":       "SKIP",
                "confidence": "Low",
                "reason":     "No Stairway-gated market found",
                "raw_scores": {"over": over_score, "under": under_score},
            }

        # ── CONFIDENCE CALIBRATION ───────────────────────────────────────────
        prob = best_market.get("prob", 0.0)
        if prob >= 0.68:
            confidence = "Very High"
        elif prob >= 0.60:
            confidence = "High"
        elif prob >= 0.52:
            confidence = "Medium"
        else:
            confidence = "Low"

        rec_score = int(prob * 100)
        if confidence == "Very High":
            rec_score = min(rec_score + 5, 100)

        # ── FINAL OUTPUT ─────────────────────────────────────────────────────
        market_label = best_market.get("label", "")
        line_str     = best_market.get("line", "")
        market_pred  = f"{market_label} {line_str}".strip()

        return {
            # ── Core prediction fields (mirrors football RuleEngine output) ──
            "type":               best_market.get("action_key", market_pred),
            "market_prediction":  market_pred,
            "market_type":        best_market.get("category", "total"),
            "odds":               best_market.get("odds", 1.0),
            "confidence":         confidence,
            "recommendation_score": rec_score,
            "market_reliability": round(prob * 100, 1),
            "reason":             reasoning[:3],

            # ── Basketball specifics ─────────────────────────────────────────
            "total_expected":     round(total_exp, 1),
            "home_expected":      round(home_expected, 1),
            "away_expected":      round(away_expected, 1),
            "half1_expected":     pts["half1_expected"],
            "half2_expected":     pts["half2_expected"],
            "q1_expected":        pts["q1_expected"],

            # ── Full action space (for RL training and ensemble) ─────────────
            "bb_predictions":     bb_predictions,
            "best_market":        best_market,

            # ── Ensemble contract: over/under logits (normalised later) ──────
            "raw_scores":         {"over": over_score, "under": under_score},

            # ── v9.8.0: period targeting for DB persistence ───────────────────
            # market_line: the numeric line (e.g. 220.5) from the chosen market
            "market_line":        float(best_market.get("line", 0) or 0) or None,
            # market_period: maps category → standard period key
            "market_period":      {
                "total":   "full",
                "h1":      "h1",
                "h2":      "h2",
                "q1":      "q1",
                "q2":      "q2",
                "q3":      "q3",
                "q4":      "q4",
                "team":    "full",  # team total = full game
            }.get(best_market.get("category", "total"), "full"),

            # ── Tags (for UI + debugging) ────────────────────────────────────
            "home_tags":          home_tags,
            "away_tags":          away_tags,
            "h2h_tags":           h2h_tags,
            "standings_tags":     standings_tags,

            # ── Context sizes (for UI trust badges) ──────────────────────────
            "home_form_n":        hfn,
            "away_form_n":        afn,
            "h2h_n":              len(h2h),
        }
