# trainer_phases.py: Reward functions and expert signal mixins for RLTrainer.
# Part of LeoBook Core — Intelligence (RL Engine)
# Mixed into RLTrainer via TrainerPhasesMixin.
# No instantiation needed — use only via RLTrainer.

from typing import Dict, Any, Optional
import torch

from Core.Utils.constants import XG_HOME_FALLBACK, XG_AWAY_FALLBACK, XG_MIN_THRESHOLD
from .feature_encoder import FeatureEncoder
from .market_space import (
    ACTIONS, N_ACTIONS, SYNTHETIC_ODDS, STAIRWAY_BETTABLE,
    compute_poisson_probs, probs_to_tensor_30dim,
    derive_ground_truth, stairway_gate,
)


class TrainerPhasesMixin:
    """
    Reward computation and expert signal methods.
    Requires self.device and self.kl_weight from RLTrainer.
    """

    # -------------------------------------------------------------------
    # Reward functions (30-dim action space)
    # -------------------------------------------------------------------

    @staticmethod
    def _get_correct_actions(outcome: Dict[str, Any]) -> set:
        """Map actual outcome to the set of correct action indices (30-dim)."""
        home_score = outcome.get("home_score", 0)
        away_score = outcome.get("away_score", 0)
        gt = derive_ground_truth(int(home_score), int(away_score))
        correct = set()
        for action in ACTIONS:
            key = action["key"]
            if gt.get(key) is True:
                correct.add(action["idx"])
        return correct

    @staticmethod
    def _compute_phase1_reward(
        chosen_action_idx: int,
        home_score: int,
        away_score: int,
    ) -> float:
        """
        Phase 1 reward: accuracy-based (no odds data yet).
        Correct prediction of bettable market = +1.0
        Correct prediction of non-bettable = +0.3
        Wrong prediction = -0.5
        no_bet when good bets existed = -0.2
        no_bet when all markets low confidence = +0.1
        """
        action = ACTIONS[chosen_action_idx]
        key = action["key"]
        gt = derive_ground_truth(int(home_score), int(away_score))

        if key == "no_bet":
            any_bettable_correct = any(
                gt.get(ACTIONS[i]["key"], False) is True
                for i in STAIRWAY_BETTABLE
            )
            return -0.2 if any_bettable_correct else +0.1

        outcome = gt.get(key)
        if outcome is None:
            return 0.0

        bettable, _ = stairway_gate(key)
        if outcome is True:
            return 1.0 if bettable else 0.3
        else:
            return -0.5

    @staticmethod
    def _compute_phase2_reward(
        chosen_action_idx: int,
        home_score: int,
        away_score: int,
        live_odds: Optional[float] = None,
        model_prob: Optional[float] = None,
    ) -> float:
        """
        Phase 2 reward: value-based (real or xG-derived fair odds).

        FIX-3: When live_odds is None, we use xG-derived fair odds per fixture
        rather than the static SYNTHETIC_ODDS lookup. This gives a match-specific
        reward signal even before real odds data is available.
        """
        action = ACTIONS[chosen_action_idx]
        key = action["key"]
        gt = derive_ground_truth(int(home_score), int(away_score))

        if key == "no_bet":
            any_value_bet_missed = any(
                gt.get(ACTIONS[i]["key"], False) is True
                for i in STAIRWAY_BETTABLE
                if SYNTHETIC_ODDS.get(ACTIONS[i]["key"], 0) >= 1.30
            )
            return -0.3 if any_value_bet_missed else +0.1

        bettable, reason = stairway_gate(key, live_odds, model_prob)
        if not bettable:
            return -0.1

        outcome = gt.get(key)
        if outcome is None:
            return 0.0

        odds = live_odds if live_odds else SYNTHETIC_ODDS.get(key, 1.5)
        if outcome is True:
            return odds - 1.0
        else:
            return -1.0

    # -------------------------------------------------------------------
    # Expert signal (Rule Engine + Poisson)
    # -------------------------------------------------------------------

    def _get_rule_engine_probs(self, vision_data: Dict[str, Any]) -> torch.Tensor:
        """
        Expert signal: Poisson probability distribution over 30-dim action space.

        FIX-5: When form data is empty, falls back to league-average xG
        (1.4 home / 1.1 away) to avoid identical expert tensors.

        Returns: torch.Tensor shape (30,) summing to 1.0
        """
        h2h = vision_data.get("h2h_data", {})
        home_form = [m for m in h2h.get("home_last_10_matches", []) if m][:10]
        away_form = [m for m in h2h.get("away_last_10_matches", []) if m][:10]
        home_team = h2h.get("home_team", "")
        away_team = h2h.get("away_team", "")

        xg_home = FeatureEncoder._compute_xg(home_form, home_team, is_home=True)
        xg_away = FeatureEncoder._compute_xg(away_form, away_team, is_home=False)

        if xg_home < XG_MIN_THRESHOLD:
            xg_home = XG_HOME_FALLBACK
        if xg_away < XG_MIN_THRESHOLD:
            xg_away = XG_AWAY_FALLBACK

        raw_scores = None
        try:
            from ..rule_engine import RuleEngine
            analysis = RuleEngine.analyze(vision_data)
            if analysis.get("type") != "SKIP":
                raw_scores = analysis.get("raw_scores")
        except Exception:
            pass

        probs = compute_poisson_probs(xg_home, xg_away, raw_scores)

        for action in ACTIONS:
            key = action["key"]
            if key == "no_bet":
                continue
            bettable, _ = stairway_gate(key)
            if not bettable:
                probs[key] *= 0.3

        vec = probs_to_tensor_30dim(probs)
        tensor = torch.tensor(vec, dtype=torch.float32)

        if tensor.sum() < 0.1:
            return torch.ones(N_ACTIONS, dtype=torch.float32).to(self.device) / N_ACTIONS

        return (tensor / tensor.sum()).to(self.device)

    def _get_xg_fair_odds(self, vision_data: Dict[str, Any]) -> Dict[str, float]:
        """
        Compute per-fixture xG-derived fair odds for all 30 markets.

        FIX-3: Used as the odds fallback in Phase 2 reward when real historical
        odds are not available. Match-specific rather than global static SYNTHETIC_ODDS.
        """
        h2h = vision_data.get("h2h_data", {})
        home_form = [m for m in h2h.get("home_last_10_matches", []) if m][:10]
        away_form = [m for m in h2h.get("away_last_10_matches", []) if m][:10]
        home_team = h2h.get("home_team", "")
        away_team = h2h.get("away_team", "")

        xg_home = FeatureEncoder._compute_xg(home_form, home_team, is_home=True)
        xg_away = FeatureEncoder._compute_xg(away_form, away_team, is_home=False)

        if xg_home < XG_MIN_THRESHOLD:
            xg_home = XG_HOME_FALLBACK
        if xg_away < XG_MIN_THRESHOLD:
            xg_away = XG_AWAY_FALLBACK

        probs = compute_poisson_probs(xg_home, xg_away, None)
        fair_odds: Dict[str, float] = {}
        for action in ACTIONS:
            key = action["key"]
            if key == "no_bet":
                continue
            p = probs.get(key, 0.0)
            if p > 0.01:
                fair_odds[key] = min(max(1.0 / p, 1.01), 20.0)
            else:
                fair_odds[key] = SYNTHETIC_ODDS.get(key, 1.5)
        return fair_odds


__all__ = ["TrainerPhasesMixin"]
