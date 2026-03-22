# rule_config.py: Configuration object for custom prediction rules.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: RuleConfig

from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class RuleConfig:
    # Identity
    id: str = "default"
    name: str = "Default"
    description: str = "Standard LeoBook prediction logic"
    
    # Weightings (0-10 scale)
    xg_advantage: float = 3.0
    xg_draw: float = 2.0
    
    h2h_home_win: float = 3.0
    h2h_away_win: float = 3.0
    h2h_draw: float = 4.0
    h2h_over25: float = 3.0
    
    standings_top_vs_bottom: float = 6.0
    standings_table_advantage: float = 3.0
    standings_gd_strong: float = 2.0
    standings_gd_weak: float = 2.0
    
    form_score_2plus: float = 4.0
    form_score_3plus: float = 2.0
    form_concede_2plus: float = 4.0
    form_no_score: float = 5.0
    form_clean_sheet: float = 5.0
    form_vs_top_win: float = 3.0
    
    # Parameters
    h2h_lookback_days: int = 540
    min_form_matches: int = 3
    risk_preference: str = "conservative"
    
    # Scope
    scope_type: str = "global"          # "global" | "league" | "team"
    scope_leagues: List[str] = field(default_factory=list)
    scope_teams: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return self.__dict__

    @staticmethod
    def from_dict(data: Dict) -> 'RuleConfig':
        # Filter to only known fields to avoid TypeError on unexpected keys
        known_fields = {f.name for f in RuleConfig.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return RuleConfig(**filtered)

    def matches_scope(self, country_league: str = "", home_team: str = "", away_team: str = "") -> bool:
        """Check if a match falls within this engine's scope."""
        if self.scope_type == "global":
            return True
        if self.scope_type == "league" and self.scope_leagues:
            return any(sl.lower() in country_league.lower() for sl in self.scope_leagues)
        if self.scope_type == "team" and self.scope_teams:
            teams_lower = [t.lower() for t in self.scope_teams]
            return home_team.lower() in teams_lower or away_team.lower() in teams_lower
        return True
