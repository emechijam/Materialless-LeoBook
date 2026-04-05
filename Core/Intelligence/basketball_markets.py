# basketball_markets.py: Basketball prediction model — Normal distribution, full market action space.
# Part of LeoBook Core — Intelligence
#
# Classes/Functions:
#   BB_MARKET_CATEGORIES  — market_id → {label, category, period, side?}
#   BB_ACTIONS            — basketball action space (market types, both Over + Under)
#   compute_bb_probs()    — Normal distribution point probabilities per period/team
#   generate_bb_predictions() — per-match predictions for all BB markets given extracted odds
#   select_best_bb_market()   — picks highest-EV Stairway-gated market
#
# Probability model:
#   Basketball scores follow a roughly Normal distribution (Central Limit Theorem —
#   ~100 independent scoring possessions per game). Unlike football (Poisson), we use:
#     P(total > L) = 1 − Φ((L − μ) / σ)
#   Period averages scale by known NBA/international proportions.

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

# ── Stairway constraints (mirrors market_space.py) ────────────────────────────
_ODDS_MIN: float = 1.20
_ODDS_MAX: float = 4.00
_MIN_PROB:  float = 0.52   # Only bet when model probability ≥ 52%

# ── Default sport-wide averages (NBA baseline; overridden by team data) ────────
BB_DEFAULT_HOME_AVG:  float = 115.0
BB_DEFAULT_AWAY_AVG:  float = 112.0
BB_DEFAULT_STD:       float = 13.5   # per-team std dev

# Period fractions (share of full-game total)
_HALF1_FRAC  = 0.48
_HALF2_FRAC  = 0.52
_Q1_FRAC     = 0.25

# Std-dev scaling by period (sqrt(fraction) × correlation factor)
_HALF_STD_SCALE = 0.72
_Q1_STD_SCALE   = 0.55

# ── Market category registry ───────────────────────────────────────────────────
# Maps football.com data-market-id → enrichment metadata.
# Used by fb_basketball_odds.py to tag each extracted odds row.
BB_MARKET_CATEGORIES: Dict[str, Dict] = {
    # ── Full game ──────────────────────────────────────────────
    "219":  {"label": "Winner (incl. OT)",       "category": "winner",  "period": "full"},
    "225":  {"label": "Total O/U (incl. OT)",     "category": "total",   "period": "full"},
    "223":  {"label": "Handicap (incl. OT)",      "category": "handicap","period": "full"},
    "229":  {"label": "Odd/Even (incl. OT)",      "category": "odd_even","period": "full"},
    "292":  {"label": "Winner & O/U (incl. OT)",  "category": "combo",   "period": "full"},
    "290":  {"label": "Winning Margin (incl. OT)","category": "margin",  "period": "full"},
    "849":  {"label": "Any Team Winning Margin",  "category": "margin",  "period": "full"},
    # ── Team totals ────────────────────────────────────────────
    "227":  {"label": "Home Team O/U (incl. OT)", "category": "team_ou", "period": "full",  "side": "home"},
    "228":  {"label": "Away Team O/U (incl. OT)", "category": "team_ou", "period": "full",  "side": "away"},
    # ── Regulation only ────────────────────────────────────────
    "1":    {"label": "1X2",                      "category": "winner",  "period": "reg"},
    "11":   {"label": "Draw No Bet",              "category": "dnb",     "period": "reg"},
    "14":   {"label": "Handicap",                 "category": "handicap","period": "reg"},
    "18":   {"label": "Over/Under",               "category": "total",   "period": "reg"},
    # ── 1st Half ──────────────────────────────────────────────
    "60":   {"label": "1st Half 1X2",             "category": "winner",  "period": "half1"},
    "64":   {"label": "1st Half Draw No Bet",     "category": "dnb",     "period": "half1"},
    "66":   {"label": "1st Half Handicap",        "category": "handicap","period": "half1"},
    "68":   {"label": "1st Half O/U",             "category": "total",   "period": "half1"},
    "69":   {"label": "1st Half Home O/U",        "category": "team_ou", "period": "half1", "side": "home"},
    "70":   {"label": "1st Half Away O/U",        "category": "team_ou", "period": "half1", "side": "away"},
    "74":   {"label": "1st Half Odd/Even",        "category": "odd_even","period": "half1"},
    # ── 2nd Half ──────────────────────────────────────────────
    "83":   {"label": "2nd Half 1X2",             "category": "winner",  "period": "half2"},
    "86":   {"label": "2nd Half Draw No Bet",     "category": "dnb",     "period": "half2"},
    "88":   {"label": "2nd Half Handicap",        "category": "handicap","period": "half2"},
    "90":   {"label": "2nd Half O/U",             "category": "total",   "period": "half2"},
    "94":   {"label": "2nd Half Odd/Even",        "category": "odd_even","period": "half2"},
    # ── Quarter markets ────────────────────────────────────────
    "235":  {"label": "1st Quarter 1X2",          "category": "winner",  "period": "q1"},
    "236":  {"label": "1st Quarter O/U",          "category": "total",   "period": "q1"},
    "301":  {"label": "1st Quarter Winning Margin","category": "margin", "period": "q1"},
    "302":  {"label": "1st Quarter Draw No Bet",  "category": "dnb",     "period": "q1"},
    "303":  {"label": "1st Quarter Handicap",     "category": "handicap","period": "q1"},
    "304":  {"label": "1st Quarter Odd/Even",     "category": "odd_even","period": "q1"},
    "756":  {"label": "1st Quarter Home O/U",     "category": "team_ou", "period": "q1",   "side": "home"},
    "757":  {"label": "1st Quarter Away O/U",     "category": "team_ou", "period": "q1",   "side": "away"},
}

# ── Basketball action space ────────────────────────────────────────────────────
# Unlike football (fixed lines like Over/Under 2.5), basketball lines are dynamic
# (e.g. Over/Under 220.5 varies game-to-game). BB_ACTIONS defines market TYPE
# actions; the prediction engine searches extracted odds to find the best available
# line for each action type.
#
# Likelihood % = historical probability that the market resolves in this direction,
#                derived from NBA 2021-25 season averages.
BB_ACTIONS: List[Dict] = [
    # ── Full-game Total O/U ── highest-volume, best model signal
    {"key": "total_over",      "label": "Total Over",       "category": "total",   "period": "full",  "outcome": "Over",  "likelihood": 51},
    {"key": "total_under",     "label": "Total Under",      "category": "total",   "period": "full",  "outcome": "Under", "likelihood": 49},
    # ── 1st Half Total O/U
    {"key": "half1_over",      "label": "1H Total Over",    "category": "total",   "period": "half1", "outcome": "Over",  "likelihood": 51},
    {"key": "half1_under",     "label": "1H Total Under",   "category": "total",   "period": "half1", "outcome": "Under", "likelihood": 49},
    # ── 2nd Half Total O/U
    {"key": "half2_over",      "label": "2H Total Over",    "category": "total",   "period": "half2", "outcome": "Over",  "likelihood": 51},
    {"key": "half2_under",     "label": "2H Total Under",   "category": "total",   "period": "half2", "outcome": "Under", "likelihood": 49},
    # ── 1st Quarter Total O/U
    {"key": "q1_over",         "label": "Q1 Total Over",    "category": "total",   "period": "q1",    "outcome": "Over",  "likelihood": 51},
    {"key": "q1_under",        "label": "Q1 Total Under",   "category": "total",   "period": "q1",    "outcome": "Under", "likelihood": 49},
    # ── Home Team O/U
    {"key": "home_team_over",  "label": "Home Over",        "category": "team_ou", "period": "full",  "outcome": "Over",  "side": "home", "likelihood": 52},
    {"key": "home_team_under", "label": "Home Under",       "category": "team_ou", "period": "full",  "outcome": "Under", "side": "home", "likelihood": 48},
    # ── Away Team O/U
    {"key": "away_team_over",  "label": "Away Over",        "category": "team_ou", "period": "full",  "outcome": "Over",  "side": "away", "likelihood": 50},
    {"key": "away_team_under", "label": "Away Under",       "category": "team_ou", "period": "full",  "outcome": "Under", "side": "away", "likelihood": 50},
    # ── 1st Half Team O/U
    {"key": "half1_home_over", "label": "1H Home Over",     "category": "team_ou", "period": "half1", "outcome": "Over",  "side": "home", "likelihood": 52},
    {"key": "half1_home_under","label": "1H Home Under",    "category": "team_ou", "period": "half1", "outcome": "Under", "side": "home", "likelihood": 48},
    {"key": "half1_away_over", "label": "1H Away Over",     "category": "team_ou", "period": "half1", "outcome": "Over",  "side": "away", "likelihood": 50},
    {"key": "half1_away_under","label": "1H Away Under",    "category": "team_ou", "period": "half1", "outcome": "Under", "side": "away", "likelihood": 50},
    # ── Winner (moneyline)
    {"key": "winner_home",     "label": "Home Win",         "category": "winner",  "period": "full",  "outcome": "Home",  "likelihood": 58},
    {"key": "winner_away",     "label": "Away Win",         "category": "winner",  "period": "full",  "outcome": "Away",  "likelihood": 42},
    # ── Handicap (best line)
    {"key": "handicap_home",   "label": "Handicap Home",    "category": "handicap","period": "full",  "outcome": "Home",  "likelihood": 50},
    {"key": "handicap_away",   "label": "Handicap Away",    "category": "handicap","period": "full",  "outcome": "Away",  "likelihood": 50},
    # ── Draw No Bet
    {"key": "dnb_home",        "label": "DNB Home",         "category": "dnb",     "period": "reg",   "outcome": "Home",  "likelihood": 58},
    {"key": "dnb_away",        "label": "DNB Away",         "category": "dnb",     "period": "reg",   "outcome": "Away",  "likelihood": 42},
]

BB_N_ACTIONS: int = len(BB_ACTIONS)


# ── Draw calibration by period ────────────────────────────────────────────────
# Basketball's FINAL result (incl. OT) CANNOT be a draw — overtime is always
# played. However, REGULATION-TIME markets (period != "full") CAN settle in a
# draw because:
#   - 1X2 regulation (market_id=1): settles at end of 48/40 min regulation
#   - Half-time 1X2 (60, 83): settles at end of each 24/20 min half
#   - Quarter 1X2 (235): settles at end of 12/10 min quarter
# All three are genuine 3-way markets where draw has a real probability.
#
# The raw Normal model underestimates draw probability (~2% raw vs ~7% NBA
# empirical) because scores are discrete integers. An empirical boost factor
# corrects for this clustering.
#
# Source: NBA 2015-2024 seasons — ~6.8% of games tied at end of regulation.
_DRAW_BOOST: Dict[str, float] = {
    "reg":   3.5,   # Full regulation (48 min): ~2% raw → ~7% calibrated
    "half1": 3.0,   # 1st half (24 min): slightly less time, fewer ties
    "half2": 3.0,   # 2nd half
    "q1":    4.5,   # Quarter (12 min): shortest, more integer ties
}
_DRAW_MAX: float = 0.14   # Cap draw probability at 14% (highest observed quarter rate)


# ── Normal distribution helpers ───────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    """Standard Normal CDF via math.erf (no external dependency)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _prob_over(mu: float, sigma: float, line: float) -> float:
    """P(X > line) with half-point continuity correction."""
    if sigma <= 0:
        return 1.0 if mu > line else 0.0
    z = (line + 0.5 - mu) / sigma
    return max(0.001, min(0.999, 1.0 - _norm_cdf(z)))


def _prob_home_win(mu_home: float, mu_away: float,
                   sigma_home: float, sigma_away: float) -> float:
    """
    P(home_score > away_score) — 2-WAY model for incl. OT markets (period='full').
    Basketball OT is always played, so P(home) + P(away) = 1.0 exactly.
    DO NOT use this for regulation-time 1X2 markets — use _prob_3way() instead.
    """
    mu_diff = mu_home - mu_away
    sigma_diff = math.sqrt(sigma_home ** 2 + sigma_away ** 2)
    if sigma_diff <= 0:
        return 0.5
    return max(0.01, min(0.99, 1.0 - _norm_cdf(-mu_diff / sigma_diff)))


def _prob_3way(mu_home: float, mu_away: float,
               sigma_home: float, sigma_away: float,
               period: str = "reg") -> Tuple[float, float, float]:
    """
    (p_home, p_draw, p_away) — 3-WAY model for REGULATION-TIME markets only.

    Used for market IDs: 1 (1X2), 60 (1H 1X2), 83 (2H 1X2), 235 (Q1 1X2),
    and Draw No Bet markets 11, 64, 86, 302.

    Basketball regulation CAN end in a tie (teams are equal at buzzer) before
    overtime is played. The draw probability is empirically ~7% (NBA, full game)
    and ~8-12% for quarters.

    The raw Normal model predicts ~2% draw because score differences are
    treated as continuous. An empirical boost (_DRAW_BOOST) corrects for
    the discrete-integer clustering effect.

    Returns probabilities that sum exactly to 1.0.
    """
    mu_diff = mu_home - mu_away
    sigma_diff = math.sqrt(sigma_home ** 2 + sigma_away ** 2)

    if sigma_diff <= 0:
        # Degenerate case — distribute sensibly
        if mu_diff > 2:   return (0.88, 0.07, 0.05)
        if mu_diff < -2:  return (0.05, 0.07, 0.88)
        return (0.465, 0.07, 0.465)

    # ── Raw draw probability via continuity correction ───────────────────
    # P(|home - away| <= 0.5) ≈ P(tied integer score)
    p_draw_raw = (
        _norm_cdf((0.5 - mu_diff) / sigma_diff)
        - _norm_cdf((-0.5 - mu_diff) / sigma_diff)
    )

    # Apply empirical boost then cap
    boost = _DRAW_BOOST.get(period, 3.5)
    p_draw = min(p_draw_raw * boost, _DRAW_MAX)

    # ── 2-way win probabilities from continuous Normal ────────────────────
    p_home_2w = 1.0 - _norm_cdf(-mu_diff / sigma_diff)
    p_away_2w = 1.0 - p_home_2w

    # ── Renormalize to 3-way sum = 1.0 ───────────────────────────────────
    remaining = 1.0 - p_draw
    p_home = max(0.01, min(0.97, p_home_2w * remaining))
    p_away = max(0.01, min(0.97, p_away_2w * remaining))

    # Final clamp to ensure exactly 1.0
    total = p_home + p_draw + p_away
    return (p_home / total, p_draw / total, p_away / total)


def _prob_handicap(mu_home: float, mu_away: float,
                   sigma_home: float, sigma_away: float,
                   spread: float) -> float:
    """P(home - away > spread). Spread markets always resolve (no draw possible)."""
    mu_diff = mu_home - mu_away
    sigma_diff = math.sqrt(sigma_home ** 2 + sigma_away ** 2)
    if sigma_diff <= 0:
        return 0.5
    z = (spread + 0.5 - mu_diff) / sigma_diff
    return max(0.01, min(0.99, 1.0 - _norm_cdf(z)))


# ── Period mean/std derivation ────────────────────────────────────────────────

def compute_bb_probs(
    home_avg: float = BB_DEFAULT_HOME_AVG,
    away_avg: float = BB_DEFAULT_AWAY_AVG,
    home_std: float = BB_DEFAULT_STD,
    away_std: float = BB_DEFAULT_STD,
) -> Dict[str, float]:
    """
    Compute expected means and std-devs for all periods/sides.

    Returns a flat dict of floats:
        mu_total, sigma_total,
        mu_home,  sigma_home,
        mu_away,  sigma_away,
        mu_half1, sigma_half1,
        mu_half2, sigma_half2,
        mu_q1,    sigma_q1,
        mu_half1_home, sigma_half1_home,
        mu_half1_away, sigma_half1_away,
        mu_q1_home,    sigma_q1_home,
        mu_q1_away,    sigma_q1_away,
    """
    mu_total   = home_avg + away_avg
    sigma_total = math.sqrt(home_std ** 2 + away_std ** 2)

    mu_half1   = mu_total * _HALF1_FRAC
    sigma_half1 = sigma_total * math.sqrt(_HALF1_FRAC) * _HALF_STD_SCALE

    mu_half2   = mu_total * _HALF2_FRAC
    sigma_half2 = sigma_total * math.sqrt(_HALF2_FRAC) * _HALF_STD_SCALE

    mu_q1      = mu_total * _Q1_FRAC
    sigma_q1   = sigma_total * math.sqrt(_Q1_FRAC) * _Q1_STD_SCALE

    return {
        "mu_total":       mu_total,   "sigma_total":       sigma_total,
        "mu_home":        home_avg,   "sigma_home":        home_std,
        "mu_away":        away_avg,   "sigma_away":        away_std,
        "mu_half1":       mu_half1,   "sigma_half1":       sigma_half1,
        "mu_half2":       mu_half2,   "sigma_half2":       sigma_half2,
        "mu_q1":          mu_q1,      "sigma_q1":          sigma_q1,
        "mu_half1_home":  home_avg * _HALF1_FRAC,
        "sigma_half1_home": home_std * math.sqrt(_HALF1_FRAC) * _HALF_STD_SCALE,
        "mu_half1_away":  away_avg * _HALF1_FRAC,
        "sigma_half1_away": away_std * math.sqrt(_HALF1_FRAC) * _HALF_STD_SCALE,
        "mu_q1_home":     home_avg * _Q1_FRAC,
        "sigma_q1_home":  home_std * math.sqrt(_Q1_FRAC) * _Q1_STD_SCALE,
        "mu_q1_away":     away_avg * _Q1_FRAC,
        "sigma_q1_away":  away_std * math.sqrt(_Q1_FRAC) * _Q1_STD_SCALE,
    }


# ── Main prediction generator ─────────────────────────────────────────────────

def generate_bb_predictions(
    extracted_rows: List[Dict],
    home_avg:  float = BB_DEFAULT_HOME_AVG,
    away_avg:  float = BB_DEFAULT_AWAY_AVG,
    home_std:  float = BB_DEFAULT_STD,
    away_std:  float = BB_DEFAULT_STD,
) -> Dict[str, Dict]:
    """
    Generate basketball market predictions using extracted live odds + Normal model.

    For each BB_ACTION, finds the best available line in extracted_rows (highest
    probability × positive EV within Stairway gate 1.20–4.00), then returns
    a prediction dict per action key.

    Args:
        extracted_rows: output from extract_basketball_match_odds() — each row has
                        market_id, category, period, side (opt), line (opt),
                        over_odds, under_odds, home_odds, away_odds, odds_value.
        home_avg / away_avg: rolling average points scored per team.
        home_std / away_std: rolling std-dev of points scored per team.

    Returns:
        dict[action_key] = {
            action_key, label, category, period, outcome, line (opt),
            prob, odds, ev, gated, gate_reason, market_id (opt)
        }
    """
    dist = compute_bb_probs(home_avg, away_avg, home_std, away_std)
    predictions: Dict[str, Dict] = {}

    # Index extracted rows by (category, period, side)
    _idx: Dict[Tuple, List[Dict]] = {}
    for row in extracted_rows:
        cat    = row.get("category", "")
        period = row.get("period",   "")
        side   = row.get("side",     "")
        key    = (cat, period, side)
        _idx.setdefault(key, []).append(row)

    for action in BB_ACTIONS:
        akey    = action["key"]
        cat     = action["category"]
        period  = action["period"]
        outcome = action["outcome"]  # "Over" | "Under" | "Home" | "Away"
        side    = action.get("side", "")

        # ── Over/Under markets ───────────────────────────────────────────────
        if cat in ("total", "team_ou"):
            mu, sigma = _mu_sigma_for(dist, cat, period, side)
            candidates = _idx.get((cat, period, side), [])
            best = _best_ou_line(candidates, outcome, mu, sigma)
            if best:
                predictions[akey] = {**best, "action_key": akey, "label": action["label"],
                                     "category": cat, "period": period, "outcome": outcome}
            else:
                # Synthetic fallback: compute prob at expected line with synthetic odds
                synthetic_line = round(mu / 0.5) * 0.5  # nearest 0.5
                prob = _prob_over(mu, sigma, synthetic_line) if outcome == "Over" else \
                       1.0 - _prob_over(mu, sigma, synthetic_line)
                syn_odds = round(1.0 / max(prob, 0.01), 3)
                gated, reason = _stairway_gate(prob, syn_odds)
                predictions[akey] = {
                    "action_key": akey, "label": action["label"],
                    "category": cat, "period": period, "outcome": outcome,
                    "line": str(synthetic_line), "prob": round(prob, 4),
                    "odds": syn_odds, "ev": round(prob * syn_odds - 1.0, 4),
                    "gated": gated, "gate_reason": reason, "market_id": None,
                }

        # ── Winner (moneyline) ───────────────────────────────────────────────
        elif cat == "winner":
            if period == "full":
                # ── Incl. OT: basketball CANNOT end in draw — 2-way market ──
                # OT is always played, P(home) + P(away) = 1.0 exactly.
                p_home = _prob_home_win(dist["mu_home"], dist["mu_away"],
                                        dist["sigma_home"], dist["sigma_away"])
                prob = p_home if outcome == "Home" else 1.0 - p_home
            else:
                # ── Regulation / half / quarter: 3-way market ────────────────
                # Basketball regulation CAN end tied before OT is played.
                # Market settles at the buzzer, so Draw is a real outcome.
                # We bet on Home or Away but adjust probability to 3-way.
                p_home, _p_draw, p_away = _prob_3way(
                    dist["mu_home"], dist["mu_away"],
                    dist["sigma_home"], dist["sigma_away"],
                    period=period,
                )
                prob = p_home if outcome == "Home" else p_away

            odds_row = _best_1x2_odds(_idx.get((cat, period, ""), []), outcome)
            odds = odds_row["odds"] if odds_row else round(1.0 / max(prob, 0.01), 3)
            mid  = odds_row.get("market_id") if odds_row else None
            ev   = round(prob * odds - 1.0, 4)
            gated, reason = _stairway_gate(prob, odds)
            predictions[akey] = {
                "action_key": akey, "label": action["label"],
                "category": cat, "period": period, "outcome": outcome,
                "prob": round(prob, 4), "odds": odds, "ev": ev,
                "gated": gated, "gate_reason": reason, "market_id": mid,
            }

        # ── Handicap ─────────────────────────────────────────────────────────
        elif cat == "handicap":
            # Spread markets always resolve (half-point lines prevent ties):
            # no draw possible regardless of period.
            candidates = _idx.get((cat, period, ""), [])
            best = _best_handicap(candidates, outcome,
                                  dist["mu_home"], dist["mu_away"],
                                  dist["sigma_home"], dist["sigma_away"])
            if best:
                predictions[akey] = {**best, "action_key": akey, "label": action["label"],
                                     "category": cat, "period": period, "outcome": outcome}

        # ── Draw No Bet ───────────────────────────────────────────────────────
        elif cat == "dnb":
            # DNB only exists for regulation-time markets (removes draw outcome).
            # P(bet wins) = P(home regulation win) — draw → stake returned (void).
            # P(bet loses) = P(away regulation win).
            # We use 3-way regulation probabilities; DNB odds already price out draw.
            p_home, _p_draw, p_away = _prob_3way(
                dist["mu_home"], dist["mu_away"],
                dist["sigma_home"], dist["sigma_away"],
                period=period if period != "full" else "reg",
            )
            prob = p_home if outcome == "Home" else p_away
            odds_row = _best_1x2_odds(_idx.get((cat, period, ""), []), outcome)
            odds = odds_row["odds"] if odds_row else round(1.0 / max(prob, 0.01), 3)
            mid  = odds_row.get("market_id") if odds_row else None
            ev   = round(prob * odds - 1.0, 4)
            gated, reason = _stairway_gate(prob, odds)
            predictions[akey] = {
                "action_key": akey, "label": action["label"],
                "category": cat, "period": period, "outcome": outcome,
                "prob": round(prob, 4), "odds": odds, "ev": ev,
                "gated": gated, "gate_reason": reason, "market_id": mid,
            }

    return predictions


def select_best_bb_market(predictions: Dict[str, Dict]) -> Optional[Dict]:
    """
    Pick the single best basketball market for the Stairway bet.

    Priority: probability-first (highest model confidence), then EV as tie-break.
    Only considers markets that pass the Stairway gate AND have prob ≥ _MIN_PROB.
    """
    gated = [
        v for v in predictions.values()
        if v.get("gated") and v.get("prob", 0) >= _MIN_PROB
    ]
    if not gated:
        return None
    gated.sort(key=lambda x: (x["prob"], x.get("ev", 0)), reverse=True)
    return gated[0]


# ── Private helpers ────────────────────────────────────────────────────────────

def _mu_sigma_for(dist: Dict, category: str, period: str, side: str) -> Tuple[float, float]:
    """Select the correct (mu, sigma) from dist for a given market."""
    if category == "total":
        key_mu = f"mu_{period}" if period in ("half1", "half2", "q1") else "mu_total"
        key_sg = f"sigma_{period}" if period in ("half1", "half2", "q1") else "sigma_total"
    else:  # team_ou
        if period == "full":
            key_mu = f"mu_{side}"
            key_sg = f"sigma_{side}"
        else:
            key_mu = f"mu_{period}_{side}"
            key_sg = f"sigma_{period}_{side}"
    return dist.get(key_mu, BB_DEFAULT_HOME_AVG), dist.get(key_sg, BB_DEFAULT_STD)


def _stairway_gate(prob: float, odds: float) -> Tuple[bool, str]:
    if odds < _ODDS_MIN:
        return False, f"Odds {odds:.2f} below min {_ODDS_MIN}"
    if odds > _ODDS_MAX:
        return False, f"Odds {odds:.2f} above max {_ODDS_MAX}"
    if prob < _MIN_PROB:
        return False, f"Prob {prob:.2%} below min {_MIN_PROB:.0%}"
    return True, "OK"


def _best_ou_line(
    rows: List[Dict], outcome: str, mu: float, sigma: float,
) -> Optional[Dict]:
    """
    From Over/Under rows for this market, return the action with the best
    Stairway-gated EV (probability × odds − 1).  Both Over AND Under considered.
    """
    best_ev = -999.0
    best: Optional[Dict] = None

    for row in rows:
        try:
            line = float(row["line"])
        except (KeyError, TypeError, ValueError):
            continue

        if outcome == "Over":
            odds = row.get("over_odds")
            if not odds:
                continue
            prob = _prob_over(mu, sigma, line)
        else:  # Under
            odds = row.get("under_odds")
            if not odds:
                continue
            prob = 1.0 - _prob_over(mu, sigma, line)

        if not (_ODDS_MIN <= odds <= _ODDS_MAX):
            continue

        ev = round(prob * odds - 1.0, 4)
        if ev > best_ev:
            best_ev = ev
            gated, reason = _stairway_gate(prob, odds)
            best = {
                "line":      str(line),
                "prob":      round(prob, 4),
                "odds":      odds,
                "ev":        ev,
                "gated":     gated,
                "gate_reason": reason,
                "market_id": row.get("market_id"),
            }

    return best


def _best_1x2_odds(rows: List[Dict], outcome: str) -> Optional[Dict]:
    """Return the odds row for Home or Away from 1X2/winner/DNB rows."""
    outcome_lower = outcome.lower()
    for row in rows:
        row_outcome = (row.get("outcome") or "").lower()
        if outcome_lower in row_outcome or row_outcome in outcome_lower:
            odds = row.get("odds_value") or row.get("home_odds") or row.get("away_odds")
            if odds:
                return {"odds": float(odds), "market_id": row.get("market_id")}
    return None


def _best_handicap(
    rows: List[Dict], outcome: str,
    mu_home: float, mu_away: float, sigma_home: float, sigma_away: float,
) -> Optional[Dict]:
    """Return best handicap bet for Home or Away side."""
    best_ev = -999.0
    best: Optional[Dict] = None

    for row in rows:
        try:
            spread = float(row["line"])
        except (KeyError, TypeError, ValueError):
            continue

        if outcome == "Home":
            odds  = row.get("home_odds")
            prob  = _prob_handicap(mu_home, mu_away, sigma_home, sigma_away, spread)
        else:
            odds  = row.get("away_odds")
            prob  = _prob_handicap(mu_away, mu_home, sigma_away, sigma_home, -spread)

        if not odds or not (_ODDS_MIN <= odds <= _ODDS_MAX):
            continue

        ev = round(prob * odds - 1.0, 4)
        if ev > best_ev:
            best_ev = ev
            gated, reason = _stairway_gate(prob, odds)
            best = {
                "line": str(spread), "prob": round(prob, 4),
                "odds": odds, "ev": ev,
                "gated": gated, "gate_reason": reason,
                "market_id": row.get("market_id"),
            }

    return best
