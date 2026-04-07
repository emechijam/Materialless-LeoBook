# base_rule_engine.py: Shared abstract base for all sport-specific rule engines.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Eliminates ~60% code duplication between RuleEngine and BasketballRuleEngine.
# Each sport subclass only overrides: _min_form_matches, _run_voting(), _build_output().
#
# Used by: rule_engine.py, basketball_rule_engine.py

"""
BaseRuleEngine — Sport-agnostic scaffolding.

Contract:
  • analyze(context, config, live_odds) → Dict  (identical signature across sports)
  • Subclass implements _run_voting() and _build_output()
  • All shared logic (gate, H2H filter, weight loading, confidence) lives here
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from abc import ABC, abstractmethod

from Core.Intelligence.learning_engine import LearningEngine
from Core.Intelligence.rule_config import RuleConfig


class BaseRuleEngine(ABC):
    """
    Abstract base rule engine.

    Shared flow:
        1. Validate team names
        2. Scope-filter via RuleConfig
        3. All-or-Nothing data gate
        4. H2H date filter
        5. Load region-specific learned weights
        6. Subclass _run_voting()  → (scores_dict, reasoning)
        7. Subclass _build_output() → raw prediction dict
        8. Confidence calibration (shared)

    Subclasses MUST implement:
        - _min_form_matches  (class-level int)
        - _run_voting(home_form, away_form, h2h, standings, weights, config, context)
        - _build_output(voting_result, context, weights, config, live_odds)
    """

    # ── Override in subclass ─────────────────────────────────────────────────
    _min_form_matches: int = 5   # default; football uses MIN_FORM_MATCHES constant

    # ── Shared: confidence calibration thresholds ────────────────────────────
    _CONF_VERY_HIGH = 0.75
    _CONF_HIGH      = 0.60
    _CONF_MEDIUM    = 0.45

    @classmethod
    def analyze(
        cls,
        context: Dict[str, Any],
        config: Optional[RuleConfig] = None,
        live_odds: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Unified entry point — identical signature across all sports.
        Override _run_voting + _build_output for sport-specific logic.
        """
        if config is None:
            config = cls._default_config()

        h2h_data       = context.get("h2h_data", {})
        standings      = context.get("standings", [])
        home_team      = h2h_data.get("home_team")
        away_team      = h2h_data.get("away_team")
        country_league = h2h_data.get("country_league", "GLOBAL")

        # ── 1. Basic sanity ──────────────────────────────────────────────────
        if not home_team or not away_team:
            return {"type": "SKIP", "confidence": "Low", "reason": "Missing team names"}

        # ── 2. Scope filter ──────────────────────────────────────────────────
        if not config.matches_scope(country_league, home_team, away_team):
            return {"type": "SKIP", "confidence": "Low", "reason": "Outside engine scope"}

        home_form = [m for m in h2h_data.get("home_last_10_matches", []) if m][:10]
        away_form = [m for m in h2h_data.get("away_last_10_matches", []) if m][:10]
        h2h_raw   = h2h_data.get("head_to_head", [])

        # ── 3. All-or-Nothing Contract ───────────────────────────────────────
        hfn = len(home_form)
        afn = len(away_form)
        stn = len(standings)
        min_f = cls._min_form_matches
        if hfn < min_f or afn < min_f or stn == 0:
            return {
                "type":       "SKIP",
                "confidence": "Low",
                "reason":     f"Contract violation: H:{hfn}, A:{afn}, St:{stn} (need {min_f}/0)",
            }

        # ── 4. H2H date filter ───────────────────────────────────────────────
        h2h = cls._filter_h2h(h2h_raw, config.h2h_lookback_days)

        # ── 5. Load region-specific learned weights ──────────────────────────
        weights = LearningEngine.load_weights(country_league)

        # Merge live_odds from context if not passed explicitly
        if live_odds is None:
            live_odds = context.get("real_odds")

        # ── 6. Sport-specific voting ─────────────────────────────────────────
        voting_result = cls._run_voting(
            home_form, away_form, h2h, standings, weights, config, context,
            home_team=home_team, away_team=away_team,
        )

        if voting_result.get("skip"):
            return {
                "type":       "SKIP",
                "confidence": "Low",
                "reason":     voting_result.get("reason", "No valid signal"),
            }

        # ── 7. Sport-specific output builder ────────────────────────────────
        output = cls._build_output(
            voting_result=voting_result,
            context=context,
            weights=weights,
            config=config,
            live_odds=live_odds,
            home_form_n=hfn,
            away_form_n=afn,
            h2h_n=len(h2h),
        )

        return output

    # ── Shared utilities ─────────────────────────────────────────────────────

    @staticmethod
    def _filter_h2h(h2h_raw: List[Dict], lookback_days: int) -> List[Dict]:
        """Filter H2H matches to the configured lookback window."""
        try:
            from Core.Utils.constants import now_ng
            cutoff = now_ng() - timedelta(days=lookback_days)
        except Exception:
            cutoff = datetime.utcnow() - timedelta(days=lookback_days)

        result = []
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
                        result.append(m)
                else:
                    result.append(m)
            except Exception:
                result.append(m)
        return result

    @staticmethod
    def calibrate_confidence(
        raw_conf: float,
        weights: Dict[str, Any],
    ) -> tuple:
        """
        Apply LearningEngine calibration to a raw [0-1] confidence score.

        Returns:
            (calibrated_score: float, label: str)
        """
        calibration = weights.get("confidence_calibration", {})

        if raw_conf > 0.8:   base_label = "Very High"
        elif raw_conf > 0.65: base_label = "High"
        elif raw_conf > 0.5:  base_label = "Medium"
        else:                 base_label = "Low"

        calibrated = calibration.get(base_label, raw_conf)

        if calibrated > 0.75:   label = "Very High"
        elif calibrated > 0.60: label = "High"
        elif calibrated > 0.45: label = "Medium"
        else:                   label = "Low"

        return calibrated, label

    # ── Abstract methods (must override) ────────────────────────────────────

    @classmethod
    @abstractmethod
    def _default_config(cls) -> RuleConfig:
        """Return the default RuleConfig for this sport."""
        ...

    @classmethod
    @abstractmethod
    def _run_voting(
        cls,
        home_form: List[Dict],
        away_form: List[Dict],
        h2h: List[Dict],
        standings: List[Dict],
        weights: Dict[str, Any],
        config: RuleConfig,
        context: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform all sport-specific signal analysis and voting.

        Returns dict with at minimum:
            {
              "scores": {...},         # e.g. {"home": 5, "draw": 2, "away": 3}
              "reasoning": [...],      # human-readable reason list
              "skip": bool,            # True → return SKIP immediately
              # + any sport-specific fields the _build_output needs
            }
        """
        ...

    @classmethod
    @abstractmethod
    def _build_output(
        cls,
        voting_result: Dict[str, Any],
        context: Dict[str, Any],
        weights: Dict[str, Any],
        config: RuleConfig,
        live_odds: Any,
        home_form_n: int,
        away_form_n: int,
        h2h_n: int,
    ) -> Dict[str, Any]:
        """
        Build the final prediction dict from voting_result + market generators.
        Called only when voting_result["skip"] is False.
        """
        ...
