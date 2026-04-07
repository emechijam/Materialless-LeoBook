# sport_profiles.py: Centralised per-sport configuration for LeoBook.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Single source of truth for:
#   • Market thresholds (xG, O/U, BTTS)
#   • Default voting weights
#   • LearningEngine reason→rule maps
#   • Minimum form contract requirements
#
# Adding a new sport = one new SportProfile entry here, zero changes elsewhere.

"""
SportProfile registry.

Usage:
    from Core.Intelligence.sport_profiles import get_sport_profile, PROFILES

    profile = get_sport_profile("basketball")
    profile.min_form_matches   # 5
    profile.reason_to_rule_map # {"H2H historically high-scoring": "bb_h2h_total_over", ...}
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True)
class SportProfile:
    """
    Immutable per-sport configuration.
    All thresholds, weight keys, and reason maps live here.
    """
    sport:                  str
    min_form_matches:       int
    xg_advantage_threshold: float           = 0.0      # not used for basketball
    xg_draw_threshold:      float           = 0.0
    xg_contradiction_threshold: float       = 0.0
    xpts_high_total:        float           = 0.0      # basketball
    xpts_low_total:         float           = 0.0      # basketball
    default_h2h_lookback:   int             = 365      # days
    rec_score_base_weight:  int             = 60
    reason_to_rule_map:     Dict[str, str]  = field(default_factory=dict)
    default_weights:        Dict[str, Any]  = field(default_factory=dict)


# ─── Football ─────────────────────────────────────────────────────────────────
_FOOTBALL_REASON_MAP: Dict[str, str] = {
    # H2H
    "strong in H2H":               "h2h_home_win",      # "{team} strong in H2H"
    "H2H home strong":             "h2h_home_win",
    "H2H away strong":             "h2h_away_win",
    "H2H suggests Draw":           "h2h_draw",
    "H2H drawish":                 "h2h_draw",
    # Standings
    "Top vs Bottom":               "standings_top_vs_bottom",
    "Top (":                       "standings_top_vs_bottom",  # partial match
    "strong GD":                   "standings_gd_strong",
    "weak GD":                     "standings_gd_weak",
    # Form
    "scores 2+ often":             "form_score_2plus",
    "scores 2+":                   "form_score_2plus",
    "concedes 2+ often":           "form_concede_2plus",
    "concedes 2+":                 "form_concede_2plus",
    "fails to score":              "form_no_score",
    "strong defense":              "form_clean_sheet",
    # xG
    "xG advantage":                "xg_advantage",
    "Close xG suggests draw":      "xg_draw",
}

_FOOTBALL_DEFAULT_WEIGHTS: Dict[str, Any] = {
    "h2h_home_win":               3.0,
    "h2h_away_win":               3.0,
    "h2h_draw":                   3.0,
    "h2h_over25":                 3.0,
    "standings_top_vs_bottom":    5.0,
    "standings_table_advantage":  3.0,
    "standings_gd_strong":        2.0,
    "standings_gd_weak":          2.0,
    "form_score_2plus":           3.0,
    "form_score_3plus":           2.0,
    "form_concede_2plus":         3.0,
    "form_no_score":              4.0,
    "form_clean_sheet":           4.0,
    "form_vs_top_win":            3.0,
    "xg_advantage":               4.0,
    "xg_draw":                    2.0,
    "confidence_calibration": {
        "Very High": 0.70,
        "High":      0.60,
        "Medium":    0.50,
        "Low":       0.40,
    }
}

FOOTBALL = SportProfile(
    sport                       = "football",
    min_form_matches            = 5,
    xg_advantage_threshold      = 0.3,    # mirrors XG_ADVANTAGE_THRESHOLD constant
    xg_draw_threshold           = 0.2,    # mirrors XG_DRAW_THRESHOLD
    xg_contradiction_threshold  = 0.8,    # mirrors XG_CONTRADICTION_THRESHOLD
    default_h2h_lookback        = 365,
    rec_score_base_weight       = 60,
    reason_to_rule_map          = _FOOTBALL_REASON_MAP,
    default_weights             = _FOOTBALL_DEFAULT_WEIGHTS,
)


# ─── Basketball ───────────────────────────────────────────────────────────────
_BB_REASON_MAP: Dict[str, str] = {
    # Form signals
    "High-scoring form boosted OVER":   "bb_form_high_scoring",
    "Low-scoring form boosted UNDER":   "bb_form_low_scoring",
    "Strong defense boosted UNDER":     "bb_form_strong_defense",
    "Weak defense boosted OVER":        "bb_form_weak_defense",
    "High-pace teams boosted OVER":     "bb_form_high_pace",
    "Low-pace teams boosted UNDER":     "bb_form_low_pace",
    # H2H signals
    "H2H historically high-scoring":   "bb_h2h_total_over",
    "H2H historically low-scoring":    "bb_h2h_total_under",
    # Standings
    "Elite offense in standings":       "bb_standings_elite_offense",
    "Elite defense in standings":       "bb_standings_elite_defense",
    # Expected points
    "xPts":                             "bb_xpts_high_total",  # partial match for both high/low
    "→ OVER signal":                    "bb_xpts_high_total",
    "→ UNDER signal":                   "bb_xpts_low_total",
    # Home/Away dominance
    "home dominance":                   "bb_h2h_home_dom",
    "away dominance":                   "bb_h2h_away_dom",
}

_BB_DEFAULT_WEIGHTS: Dict[str, Any] = {
    "bb_form_high_scoring":         4.0,
    "bb_form_low_scoring":          3.5,
    "bb_form_strong_defense":       4.5,
    "bb_form_weak_defense":         3.5,
    "bb_form_high_pace":            3.0,
    "bb_form_low_pace":             3.0,
    "bb_h2h_total_over":            5.0,
    "bb_h2h_total_under":           5.0,
    "bb_h2h_home_dom":              1.5,
    "bb_h2h_away_dom":              1.5,
    "bb_standings_elite_offense":   3.5,
    "bb_standings_elite_defense":   3.5,
    "bb_xpts_high_total":           6.0,
    "bb_xpts_low_total":            6.0,
    "confidence_calibration": {
        "Very High": 0.68,
        "High":      0.60,
        "Medium":    0.52,
        "Low":       0.40,
    }
}

BASKETBALL = SportProfile(
    sport                       = "basketball",
    min_form_matches            = 5,
    xpts_high_total             = 228.0,
    xpts_low_total              = 212.0,
    default_h2h_lookback        = 540,
    rec_score_base_weight       = 60,
    reason_to_rule_map          = _BB_REASON_MAP,
    default_weights             = _BB_DEFAULT_WEIGHTS,
)


# ─── Registry ─────────────────────────────────────────────────────────────────
PROFILES: Dict[str, SportProfile] = {
    "football":   FOOTBALL,
    "basketball": BASKETBALL,
    # Tennis, Baseball etc. added here — zero changes elsewhere
}


def get_sport_profile(sport: str) -> SportProfile:
    """
    Return the SportProfile for a sport name.
    Falls back to FOOTBALL for unknown sports.
    """
    return PROFILES.get(sport.lower().strip(), FOOTBALL)


def get_combined_reason_map() -> Dict[str, str]:
    """
    Return a single merged reason→rule map covering all sports.
    Used by LearningEngine.analyze_performance() for multi-sport prediction rows.
    """
    merged: Dict[str, str] = {}
    for profile in PROFILES.values():
        merged.update(profile.reason_to_rule_map)
    return merged


def get_combined_default_weights() -> Dict[str, Any]:
    """
    Return merged DEFAULT_WEIGHTS covering all sports.
    Used by LearningEngine._merge_defaults() so all keys have a fallback.
    """
    import copy
    merged: Dict[str, Any] = {}
    merged_cal: Dict[str, float] = {}
    for profile in PROFILES.values():
        w = dict(profile.default_weights)
        cal = w.pop("confidence_calibration", {})
        merged.update(w)
        # Take the more conservative calibration for shared keys
        for k, v in cal.items():
            if k not in merged_cal or v < merged_cal[k]:
                merged_cal[k] = v
    merged["confidence_calibration"] = merged_cal
    return merged


__all__ = [
    "SportProfile", "PROFILES",
    "FOOTBALL", "BASKETBALL",
    "get_sport_profile",
    "get_combined_reason_map",
    "get_combined_default_weights",
]
