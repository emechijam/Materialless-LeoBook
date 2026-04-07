# basketball_pts_predictor.py: Expected points + Normal distribution for all periods.
# Part of LeoBook Core — Intelligence (AI Engine) — Basketball Rule Engine
#
# Classes: BasketballPtsPredictor
# Single source of truth for translating team rolling averages → period distributions.
# Delegates to compute_bb_probs() in basketball_markets.py.

from typing import List, Dict, Any

from Core.Intelligence.basketball_tag_generator import BasketballTagGenerator
from Core.Intelligence.basketball_markets import (
    compute_bb_probs,
    BB_DEFAULT_HOME_AVG,
    BB_DEFAULT_AWAY_AVG,
    BB_DEFAULT_STD,
)


class BasketballPtsPredictor:
    """
    Translates raw match dicts into rolling team averages, then feeds
    compute_bb_probs() to get the Normal distribution for every period.

    Output of get_match_expected_points() is consumed by:
        BasketballRuleEngine.analyze()   — symbolic voting
        generate_bb_predictions()        — full market predictions
    """

    # ─────────────────────────────────────────────────────────────
    # Team-level expected points
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def compute_team_avg(
        matches: List[Dict],
        team_name: str,
        is_home_game: bool = True,
    ) -> Dict[str, float]:
        """
        Compute rolling average points score for a team from its last N matches.

        Returns:
            {"team_avg": float, "opp_avg": float, "n": int}
        """
        valid = [m for m in matches if m]
        if not valid:
            default = BB_DEFAULT_HOME_AVG if is_home_game else BB_DEFAULT_AWAY_AVG
            return {"team_avg": default, "opp_avg": BB_DEFAULT_AWAY_AVG, "n": 0}

        team_pts_list = []
        opp_pts_list  = []

        for m in valid:
            ph, pa = BasketballTagGenerator._parse_match_scores(m)
            is_home_match = m.get("home", "") == team_name
            team_pts_list.append(ph if is_home_match else pa)
            opp_pts_list.append(pa if is_home_match else ph)

        n = len(team_pts_list)
        team_avg = sum(team_pts_list) / n

        # Small home/away adjustment (+3% when playing at home vs neutral rolling avg)
        if is_home_game:
            team_avg = team_avg * 1.03
        else:
            team_avg = team_avg * 0.97

        opp_avg = sum(opp_pts_list) / n

        return {"team_avg": round(team_avg, 1), "opp_avg": round(opp_avg, 1), "n": n}

    # ─────────────────────────────────────────────────────────────
    # Full match expected points + distributions
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_match_expected_points(
        home_form: List[Dict],
        away_form: List[Dict],
        home_team: str,
        away_team: str,
        home_std: float = BB_DEFAULT_STD,
        away_std: float = BB_DEFAULT_STD,
    ) -> Dict[str, Any]:
        """
        Compute expected points for every market period using the Normal model.

        Quarter/half-level expected values are derived from actual period_scores
        in historical form matches when available — otherwise uses the standard
        25% / 50% fraction of the full-game expected total.

        Returns a unified dict consumed by BasketballRuleEngine and generate_bb_predictions:
            home_expected, away_expected, total_expected,
            half1_expected, half2_expected, q1_expected,
            home_avg_used, away_avg_used,
            dist  — full compute_bb_probs() output (for generate_bb_predictions)
        """
        home_stats = BasketballPtsPredictor.compute_team_avg(home_form, home_team, True)
        away_stats = BasketballPtsPredictor.compute_team_avg(away_form, away_team, False)

        home_avg = home_stats["team_avg"]
        away_avg = away_stats["team_avg"]

        dist = compute_bb_probs(
            home_avg=home_avg,
            away_avg=away_avg,
            home_std=home_std,
            away_std=away_std,
        )

        # ── Period-level averages from actual period_scores ───────────────────
        # Collect all form matches that carry period_scores for more precise Q/H estimates.
        all_form = [m for m in (home_form + away_form) if m and m.get("period_scores")]

        q1_totals: List[float] = []
        h1_totals: List[float] = []
        h2_totals: List[float] = []

        for m in all_form:
            ps = m["period_scores"]
            if not isinstance(ps, dict):
                continue
            # Q1
            q1 = ps.get("q1")
            if isinstance(q1, dict):
                qh = q1.get("home", 0) or 0
                qa = q1.get("away", 0) or 0
                q1_totals.append(float(qh) + float(qa))
            # H1 = Q1 + Q2 when available, else direct h1 key
            h1 = ps.get("h1")
            q2 = ps.get("q2")
            if isinstance(h1, dict):
                h1_totals.append(float(h1.get("home", 0) or 0) + float(h1.get("away", 0) or 0))
            elif isinstance(q2, dict) and isinstance(q1, dict):
                # Derive H1 = Q1 + Q2
                h1v = (
                    float((q1.get("home") or 0)) + float((q2.get("home") or 0))
                    + float((q1.get("away") or 0)) + float((q2.get("away") or 0))
                )
                h1_totals.append(h1v)
            # H2 = Q3 + Q4 when available, else direct h2 key
            h2 = ps.get("h2")
            q3 = ps.get("q3")
            q4 = ps.get("q4")
            if isinstance(h2, dict):
                h2_totals.append(float(h2.get("home", 0) or 0) + float(h2.get("away", 0) or 0))
            elif isinstance(q3, dict) and isinstance(q4, dict):
                h2v = (
                    float((q3.get("home") or 0)) + float((q4.get("home") or 0))
                    + float((q3.get("away") or 0)) + float((q4.get("away") or 0))
                )
                h2_totals.append(h2v)

        # Use actual period averages when we have enough data, else fractions
        mu_total = dist["mu_total"]
        q1_exp = round(sum(q1_totals) / len(q1_totals), 1) if len(q1_totals) >= 3 else round(dist["mu_q1"], 1)
        h1_exp = round(sum(h1_totals) / len(h1_totals), 1) if len(h1_totals) >= 3 else round(dist["mu_half1"], 1)
        h2_exp = round(sum(h2_totals) / len(h2_totals), 1) if len(h2_totals) >= 3 else round(dist["mu_half2"], 1)

        return {
            "home_expected":  round(dist["mu_home"],  1),
            "away_expected":  round(dist["mu_away"],  1),
            "total_expected": round(mu_total, 1),
            "half1_expected": h1_exp,
            "half2_expected": h2_exp,
            "q1_expected":    q1_exp,
            "home_avg_used":  home_avg,
            "away_avg_used":  away_avg,
            # Metadata: how many matches had period_scores (for UI trust signal)
            "period_data_n":  len(all_form),
            "dist":           dist,
        }

