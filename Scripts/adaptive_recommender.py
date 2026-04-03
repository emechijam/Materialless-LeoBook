# adaptive_recommender.py: EMA-based adaptive bet recommender for Project Stairway.
# Part of LeoBook Scripts — Pipeline
#
# Split from recommend_bets.py (v9.6.0)
# Class: AdaptiveRecommender

"""
AdaptiveRecommender Module
EMA-smoothed per-market/league/confidence-level accuracy weights.
Learns from resolved predictions and scores candidates for top-20% selection.
"""

import json
import os
from pathlib import Path

from Core.Utils.constants import now_ng
from Data.Access.prediction_accuracy import get_market_option

# Resolve project root relative to this file (Scripts/ parent)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)

RECOMMENDER_DB = Path(_PROJECT_ROOT) / "Data" / "Store" / "recommender_weights.json"

# Stairway constants (re-exported for callers that import from here)
STAIRWAY_ODDS_MIN = 1.20
STAIRWAY_ODDS_MAX = 4.00
STAIRWAY_DAILY_MIN = 2
STAIRWAY_DAILY_MAX = 8
TARGET_ACCURACY = 0.70  # 70% accuracy floor for Stairway survival


class AdaptiveRecommender:
    """
    Learning-based recommendation selector for Project Stairway.

    Tracks per-market and per-league accuracy using Exponential Moving Average (EMA).
    Each run of `learn()` updates the weights so that future `score()` calls
    naturally prefer markets/leagues that have historically been accurate.

    Weight structure:
        {
            "market_weights": {"1X2 - Home": {"ema_acc": 0.65, "n": 42}, ...},
            "league_weights": {"England - Premier League": {"ema_acc": 0.72, "n": 31}, ...},
            "confidence_weights": {"Very High": {"ema_acc": 0.78, "n": 50}, ...},
            "meta": {"last_learn": "2026-03-22", "total_learned": 1234}
        }
    """

    EMA_ALPHA = 0.15  # Smoothing factor — higher = more recent-weighting

    # ── Specialization Thresholds ──
    # If a league/market has EMA accuracy BELOW this floor after MIN_SAMPLES,
    # it is gated out entirely — the system stops recommending from it.
    SPEC_MIN_EMA = 0.40      # 40% — worse than a coin flip on binary markets
    SPEC_MIN_SAMPLES = 20    # Need at least 20 observations before gating

    def __init__(self, weights_path: str = None):
        self._weights_path = Path(weights_path) if weights_path else RECOMMENDER_DB
        self.weights = self._load()

    def _load(self) -> dict:
        """Load weights from disk, or create defaults."""
        if self._weights_path.exists():
            try:
                with open(self._weights_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "market_weights": {},
            "league_weights": {},
            "confidence_weights": {},
            "meta": {"last_learn": "", "total_learned": 0}
        }

    def _save(self):
        """Persist weights to disk."""
        os.makedirs(self._weights_path.parent, exist_ok=True)
        with open(self._weights_path, 'w', encoding='utf-8') as f:
            json.dump(self.weights, f, indent=2, ensure_ascii=False)

    def learn(self, all_predictions: list):
        """
        Update EMA weights from all resolved predictions (outcome_correct known).
        Called once per recommendation cycle to keep weights fresh.
        """
        mw = self.weights["market_weights"]
        lw = self.weights["league_weights"]
        cw = self.weights["confidence_weights"]
        learned = 0

        for p in all_predictions:
            outcome = str(p.get('outcome_correct', ''))
            if outcome not in ('True', 'False', '1', '0'):
                continue

            is_correct = 1.0 if outcome in ('True', '1') else 0.0
            market = get_market_option(
                p.get('prediction', ''), p.get('home_team', ''), p.get('away_team', '')
            )
            league = p.get('country_league', 'Unknown')
            conf = p.get('confidence', 'Medium')

            for bucket, key in [(mw, market), (lw, league), (cw, conf)]:
                if key not in bucket:
                    bucket[key] = {"ema_acc": 0.50, "n": 0}
                entry = bucket[key]
                entry["ema_acc"] = (
                    self.EMA_ALPHA * is_correct + (1 - self.EMA_ALPHA) * entry["ema_acc"]
                )
                entry["n"] += 1

            learned += 1

        self.weights["meta"]["last_learn"] = now_ng().strftime("%Y-%m-%d %H:%M")
        self.weights["meta"]["total_learned"] = learned
        self._save()
        return learned

    def learn_from_day(self, day_predictions: list):
        """
        Walk-forward single-day EMA update.
        Called by trainer.py for each historical date during --train-rl.

        Each item in day_predictions must have:
            - 'market': str (e.g. 'Over/Under - Over 2.5')
            - 'country_league': str
            - 'confidence': str
            - 'is_correct': bool
        """
        mw = self.weights["market_weights"]
        lw = self.weights["league_weights"]
        cw = self.weights["confidence_weights"]

        for p in day_predictions:
            is_correct = 1.0 if p.get('is_correct') else 0.0
            market = p.get('market', 'Unknown')
            league = p.get('country_league', 'Unknown')
            conf = p.get('confidence', 'Medium')

            for bucket, key in [(mw, market), (lw, league), (cw, conf)]:
                if key not in bucket:
                    bucket[key] = {"ema_acc": 0.50, "n": 0}
                entry = bucket[key]
                entry["ema_acc"] = (
                    self.EMA_ALPHA * is_correct + (1 - self.EMA_ALPHA) * entry["ema_acc"]
                )
                entry["n"] += 1

        self.weights["meta"]["total_learned"] = (
            self.weights["meta"].get("total_learned", 0) + len(day_predictions)
        )
        self._save()

    def select_top_picks(self, candidates: list, min_picks: int = 2, max_picks: int = 8) -> list:
        """
        Score and select top 20% of candidates, bounded by [min_picks, max_picks].
        Returns the selected candidates sorted by score descending.
        """
        for c in candidates:
            c['rec_score'] = self.score(c, c.get('market', 'Unknown'))
        candidates.sort(key=lambda x: x['rec_score'], reverse=True)
        n = max(min_picks, int(len(candidates) * 0.20))
        n = min(n, max_picks, len(candidates))
        return candidates[:n]

    def copy_to_production(self):
        """Copy training weights to production path."""
        import shutil
        if self._weights_path != RECOMMENDER_DB and self._weights_path.exists():
            shutil.copy2(self._weights_path, RECOMMENDER_DB)
            print(f"  [Recommender] Training weights copied to production: {RECOMMENDER_DB}")

    def score(self, prediction: dict, market: str) -> float:
        """
        Compute adaptive recommendation score with calibration + specialization.

        Calibration:
            Instead of using discrete confidence labels (Low/Med/High/Very High),
            the score is based on the ACTUAL observed win rates from EMA data.
            Market EMA of 0.65 means "this market type wins 65% of the time" —
            that IS the calibrated probability.

        Specialization:
            If a league or market has EMA < SPEC_MIN_EMA after SPEC_MIN_SAMPLES
            observations, score returns 0.0 — the prediction is excluded.

        Score = 45% market_EMA + 35% league_EMA + 20% sample_reliability

        Returns float in [0, 1]. Returns 0.0 for gated-out predictions.
        """
        mw = self.weights.get("market_weights", {})
        lw = self.weights.get("league_weights", {})

        league = prediction.get('country_league', 'Unknown')

        market_entry = mw.get(market, {})
        league_entry = lw.get(league, {})

        market_acc = market_entry.get("ema_acc", 0.50)
        market_n = market_entry.get("n", 0)
        league_acc = league_entry.get("ema_acc", 0.50)
        league_n = league_entry.get("n", 0)

        # ── Specialization Gate ──
        if market_n >= self.SPEC_MIN_SAMPLES and market_acc < self.SPEC_MIN_EMA:
            return 0.0
        if league_n >= self.SPEC_MIN_SAMPLES and league_acc < self.SPEC_MIN_EMA:
            return 0.0

        # ── Calibrated Score ──
        reliability = min((market_n + league_n) / 200.0, 1.0)
        total = (
            market_acc * 0.45 +
            league_acc * 0.35 +
            reliability * 0.20
        )
        return round(total, 4)

    def calibrated_prob(self, market: str, league: str) -> float:
        """
        Return the calibrated win probability for a market+league combination.
        This is the actual expected accuracy based on learned EMA data.
        """
        mw = self.weights.get("market_weights", {})
        lw = self.weights.get("league_weights", {})

        m_acc = mw.get(market, {}).get("ema_acc", 0.50)
        l_acc = lw.get(league, {}).get("ema_acc", 0.50)
        m_n = mw.get(market, {}).get("n", 0)
        l_n = lw.get(league, {}).get("n", 0)

        if m_n + l_n == 0:
            return 0.50
        return (m_acc * m_n + l_acc * l_n) / (m_n + l_n)
