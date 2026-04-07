# rule_engine_manager.py: Rule engine registry + semantic market chooser.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: RuleEngineManager, SemanticRuleEngine
# Called by: Leo.py, progressive_backtester.py, prediction_pipeline.py

"""
Loads and persists rule engines from Data/Store/rule_engines.json
(schema aligned with Flutter RuleConfigModel / rule_config.RuleConfig).
"""

from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

from Core.Intelligence.market_ontology import MarketOntology
from Core.Intelligence.rule_config import RuleConfig

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENGINES_PATH = PROJECT_ROOT / "Data" / "Store" / "rule_engines.json"


class RuleEngineManager:
    """CRUD + default selection for JSON-backed rule engines."""

    @staticmethod
    def _path() -> Path:
        ENGINES_PATH.parent.mkdir(parents=True, exist_ok=True)
        return ENGINES_PATH

    @staticmethod
    def _load_list() -> List[Dict[str, Any]]:
        p = RuleEngineManager._path()
        if not p.exists():
            defaults = [
                RuleEngineManager._builtin_default_dict(),
                RuleEngineManager._builtin_basketball_default_dict(),
            ]
            RuleEngineManager._save_list(defaults)
            return defaults
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(raw, list) or not raw:
                defaults = [
                    RuleEngineManager._builtin_default_dict(),
                    RuleEngineManager._builtin_basketball_default_dict(),
                ]
                RuleEngineManager._save_list(defaults)
                return defaults
            # Back-fill basketball default if missing (upgrade path)
            ids = {e.get("id") for e in raw}
            if "basketball_default" not in ids:
                raw.append(RuleEngineManager._builtin_basketball_default_dict())
                RuleEngineManager._save_list(raw)
            return raw
        except (json.JSONDecodeError, OSError):
            defaults = [
                RuleEngineManager._builtin_default_dict(),
                RuleEngineManager._builtin_basketball_default_dict(),
            ]
            RuleEngineManager._save_list(defaults)
            return defaults

    @staticmethod
    def _save_list(engines: List[Dict[str, Any]]) -> None:
        p = RuleEngineManager._path()
        p.write_text(json.dumps(engines, indent=2, ensure_ascii=False), encoding="utf-8")

    @staticmethod
    def _builtin_default_dict() -> Dict[str, Any]:
        """Football default engine — matches RuleConfig / RuleConfigModel defaults."""
        return {
            "id": "default",
            "name": "Default",
            "description": "Standard LeoBook prediction logic",
            "is_default": True,
            "is_builtin_default": True,
            "sport": "football",
            "scope": {"type": "global", "leagues": [], "teams": []},
            "weights": {
                "xg_advantage": 3.0,
                "xg_draw": 2.0,
                "h2h_home_win": 3.0,
                "h2h_away_win": 3.0,
                "h2h_draw": 4.0,
                "h2h_over25": 3.0,
                "standings_top_vs_bottom": 6.0,
                "standings_table_advantage": 3.0,
                "standings_gd_strong": 2.0,
                "standings_gd_weak": 2.0,
                "form_score_2plus": 4.0,
                "form_score_3plus": 2.0,
                "form_concede_2plus": 4.0,
                "form_no_score": 5.0,
                "form_clean_sheet": 5.0,
                "form_vs_top_win": 3.0,
            },
            "parameters": {
                "h2h_lookback_days": 540,
                "min_form_matches": 3,
                "risk_preference": "conservative",
            },
            "accuracy": {
                "total_predictions": 0,
                "correct": 0,
                "win_rate": 0.0,
                "last_backtested": None,
                "backtest_period": None,
            },
        }

    @staticmethod
    def _builtin_basketball_default_dict() -> Dict[str, Any]:
        """Basketball default engine — O/U focused for basketball markets."""
        return {
            "id": "basketball_default",
            "name": "Basketball Default",
            "description": "O/U focused rule engine for basketball (Total, Team, Halves, Quarters)",
            "is_default": False,
            "is_builtin_default": True,
            "sport": "basketball",
            "scope": {"type": "global", "leagues": [], "teams": []},
            "weights": {
                # Basketball-specific O/U symbolic weights
                "bb_form_high_scoring":      4.0,
                "bb_form_low_scoring":       3.5,
                "bb_form_strong_defense":    4.5,
                "bb_form_weak_defense":      3.5,
                "bb_form_high_pace":         3.0,
                "bb_form_low_pace":          3.0,
                "bb_h2h_total_over":         5.0,
                "bb_h2h_total_under":        5.0,
                "bb_h2h_home_dom":           1.5,
                "bb_h2h_away_dom":           1.5,
                "bb_standings_elite_offense": 3.5,
                "bb_standings_elite_defense": 3.5,
                "bb_xpts_high_total":        6.0,
                "bb_xpts_low_total":         6.0,
            },
            "parameters": {
                "h2h_lookback_days": 540,
                "min_form_matches": 5,
                "risk_preference": "conservative",
            },
            "accuracy": {
                "total_predictions": 0,
                "correct": 0,
                "win_rate": 0.0,
                "last_backtested": None,
                "backtest_period": None,
            },
        }

    @staticmethod
    def list_engines() -> List[Dict[str, Any]]:
        return copy.deepcopy(RuleEngineManager._load_list())

    @staticmethod
    def get_engine(engine_id: str) -> Optional[Dict[str, Any]]:
        for e in RuleEngineManager._load_list():
            if e.get("id") == engine_id:
                return copy.deepcopy(e)
        return None

    @staticmethod
    def get_default() -> Dict[str, Any]:
        engines = RuleEngineManager._load_list()
        for e in engines:
            if e.get("is_default"):
                return copy.deepcopy(e)
        return copy.deepcopy(engines[0])

    @staticmethod
    def set_default(engine_id: str) -> bool:
        engines = RuleEngineManager._load_list()
        found = False
        for e in engines:
            e["is_default"] = e.get("id") == engine_id
            if e["is_default"]:
                found = True
        if not found:
            return False
        RuleEngineManager._save_list(engines)
        return True

    @staticmethod
    def to_rule_config(engine: Dict[str, Any]) -> RuleConfig:
        w = engine.get("weights") or {}
        p = engine.get("parameters") or {}
        sc = engine.get("scope") or {}
        scope_type = sc.get("type", "global")
        leagues = sc.get("leagues") or []
        teams = sc.get("teams") or []
        if not isinstance(leagues, list):
            leagues = []
        if not isinstance(teams, list):
            teams = []
        return RuleConfig(
            id=str(engine.get("id", "default")),
            name=str(engine.get("name", "Custom")),
            description=str(engine.get("description", "")),
            xg_advantage=float(w.get("xg_advantage", 3.0)),
            xg_draw=float(w.get("xg_draw", 2.0)),
            h2h_home_win=float(w.get("h2h_home_win", 3.0)),
            h2h_away_win=float(w.get("h2h_away_win", 3.0)),
            h2h_draw=float(w.get("h2h_draw", 4.0)),
            h2h_over25=float(w.get("h2h_over25", 3.0)),
            standings_top_vs_bottom=float(w.get("standings_top_vs_bottom", 6.0)),
            standings_table_advantage=float(w.get("standings_table_advantage", 3.0)),
            standings_gd_strong=float(w.get("standings_gd_strong", 2.0)),
            standings_gd_weak=float(w.get("standings_gd_weak", 2.0)),
            form_score_2plus=float(w.get("form_score_2plus", 4.0)),
            form_score_3plus=float(w.get("form_score_3plus", 2.0)),
            form_concede_2plus=float(w.get("form_concede_2plus", 4.0)),
            form_no_score=float(w.get("form_no_score", 5.0)),
            form_clean_sheet=float(w.get("form_clean_sheet", 5.0)),
            form_vs_top_win=float(w.get("form_vs_top_win", 3.0)),
            h2h_lookback_days=int(p.get("h2h_lookback_days", 540)),
            min_form_matches=int(p.get("min_form_matches", 3)),
            risk_preference=str(p.get("risk_preference", "conservative")),
            scope_type=str(scope_type),
            scope_leagues=[str(x) for x in leagues],
            scope_teams=[str(x) for x in teams],
        )

    @staticmethod
    def update_engine(engine_id: str, updates: Dict[str, Any]) -> bool:
        engines = RuleEngineManager._load_list()
        for i, e in enumerate(engines):
            if e.get("id") != engine_id:
                continue
            merged = copy.deepcopy(e)
            for key, val in updates.items():
                if key == "accuracy" and isinstance(val, dict):
                    acc = merged.get("accuracy") or {}
                    acc.update(val)
                    merged["accuracy"] = acc
                elif key in ("weights", "parameters", "scope") and isinstance(val, dict):
                    inner = merged.get(key) or {}
                    inner.update(val)
                    merged[key] = inner
                else:
                    merged[key] = val
            engines[i] = merged
            RuleEngineManager._save_list(engines)
            return True
        return False

    @staticmethod
    def save_engine_dict(engine: Dict[str, Any]) -> bool:
        """Insert or replace an engine by id."""
        engines = RuleEngineManager._load_list()
        eid = engine.get("id")
        if not eid:
            return False
        for i, ex in enumerate(engines):
            if ex.get("id") == eid:
                # Preserve builtin flag if existing
                if ex.get("is_builtin_default"):
                    engine = copy.deepcopy(engine)
                    engine["is_builtin_default"] = True
                engines[i] = copy.deepcopy(engine)
                RuleEngineManager._save_list(engines)
                return True
        engines.append(copy.deepcopy(engine))
        RuleEngineManager._save_list(engines)
        return True

    @staticmethod
    def print_engine_list() -> None:
        for e in RuleEngineManager._load_list():
            d = " (default)" if e.get("is_default") else ""
            b = " [builtin]" if e.get("is_builtin_default") else ""
            print(f"  • {e.get('id')}: {e.get('name')}{d}{b}")

    @staticmethod
    def print_engine(engine: Dict[str, Any]) -> None:
        print(json.dumps(engine, indent=2, ensure_ascii=False))


class SemanticRuleEngine:
    def __init__(self):
        self.ontology = MarketOntology.load()

    def choose_market(self, fixture_data: dict, xG_home: float, xG_away: float) -> dict:
        total_xg = xG_home + xG_away

        # Step 2: Semantic scoring using ontology
        best_market = None
        best_score = -1.0
        for mkt_name, mkt in self.ontology.markets.items():
            if mkt.semantic_meaning.startswith("Total goals"):
                if (mkt.exact_outcome == "Under" and total_xg < mkt.typical_xg_range[1]) or (
                    mkt.exact_outcome == "Over" and total_xg > mkt.typical_xg_range[0]
                ):
                    score = mkt.likelihood_percent * 0.01 + (
                        1.0 if mkt.risk_profile == "safe" else 0.0
                    )
                    if score > best_score:
                        best_score = score
                        best_market = mkt
            elif mkt.base_market in ["Double Chance", "1X2"]:
                score = mkt.likelihood_percent * 0.01
                if score > best_score:
                    best_score = score
                    best_market = mkt

        # Step 3: Safety guardrails (secondary only — never override semantic choice silently)
        override_reason = None
        final_market = best_market
        if best_market and best_market.risk_profile == "safe" and total_xg > 3.8:
            override_reason = f"xG too high ({total_xg:.2f}) for safe market"
            final_market = self.ontology.markets.get("Over/Under - Over 2.5", best_market)

        if final_market is None:
            return {
                "chosen_market": "SKIP",
                "market_id": "",
                "outcome": "",
                "line": "",
                "statistical_edge": 0.0,
                "override_reason": "No semantic market",
                "explanation": "Semantic engine found no suitable market",
            }

        return {
            "chosen_market": final_market.market_outcome,
            "market_id": final_market.market_id,
            "outcome": final_market.exact_outcome,
            "line": final_market.line,
            "statistical_edge": round(best_score * 100, 1),
            "override_reason": override_reason,
            "explanation": f"{final_market.semantic_meaning} (xG {total_xg:.2f}, likelihood {final_market.likelihood_percent}%)",
        }


if __name__ == "__main__":
    engine = SemanticRuleEngine()
    test_cases = [
        {"xG_home": 1.06, "xG_away": 0.64},
        {"xG_home": 0.70, "xG_away": 1.17},
        {"xG_home": 1.40, "xG_away": 1.57},
    ]
    for i, case in enumerate(test_cases):
        result = engine.choose_market({}, case["xG_home"], case["xG_away"])
        print(f"Test {i+1}: {result['chosen_market']} | {result['explanation']}")
        if result["override_reason"]:
            print(f"  Override: {result['override_reason']}")
