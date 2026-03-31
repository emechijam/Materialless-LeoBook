# data_contract.py: Strict data contract validation for Flashscore enrichment.
# Part of LeoBook Modules — Flashscore
#
# All-or-Nothing: if any validation fails, the entire league extraction is rolled back.

import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class DataContractViolation(Exception):
    """Raised when extracted data violates the strict data contract."""
    pass

# ═══════════════════════════════════════════════════════════════════════════════
#  Internal Constants
# ═══════════════════════════════════════════════════════════════════════════════

_LEAGUE_REQUIRED_FIELDS = [
    "fs_league_id",
    "current_season",
    "crest",
    "region",
    "region_flag",
    "region_url",
]

_MATCH_ALWAYS_REQUIRED = [
    "fixture_id",
    "date",
    "time",
    "home_team_name",
    "away_team_name",
    "home_team_id",
    "away_team_id",
    "home_team_url",
    "away_team_url",
    "home_crest_url",
    "away_crest_url",
    "match_link",
    "match_status",
]

_MATCH_RESULTS_ONLY = [
    "home_score",
    "away_score",
    "winner",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  DataContract Class
# ═══════════════════════════════════════════════════════════════════════════════

class DataContract:
    """Strict data contract validation for Flashscore enrichment."""

    @staticmethod
    def validate_league_metadata(data: Dict) -> Tuple[bool, List[str]]:
        """Validate league-level metadata. All fields are REQUIRED."""
        violations = []
        for field in _LEAGUE_REQUIRED_FIELDS:
            val = data.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                violations.append(f"league.{field} is missing or empty")
        return (len(violations) == 0, violations)

    @staticmethod
    def validate_match(match: Dict, tab: str) -> Tuple[bool, List[str]]:
        """Validate a single match against the strict data contract.
        
        Args:
            match: Raw match dict.
            tab: "results" or "fixtures".
        """
        violations = []

        for field in _MATCH_ALWAYS_REQUIRED:
            val = match.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                violations.append(f"match[{match.get('fixture_id', '?')}].{field}")

        if tab == "results":
            # Scores are only required for genuinely finished matches.
            status = (match.get("match_status") or "").lower()
            score_finished_statuses = ("finished", "ft", "aet", "pen", "after pen", "after et")
            if status in score_finished_statuses:
                for field in _MATCH_RESULTS_ONLY:
                    val = match.get(field)
                    if val is None or (isinstance(val, str) and not val.strip()):
                        violations.append(f"match[{match.get('fixture_id', '?')}].{field}")

        return (len(violations) == 0, violations)

    @staticmethod
    def validate_tab_extraction(scanned_count: int, matches: List[Dict], tab: str) -> Tuple[bool, str]:
        """Validate an entire tab extraction: row count + per-match contract."""
        extracted_count = len(matches)

        # Level 1: Row count parity
        if scanned_count != extracted_count:
            return (
                False,
                f"[{tab.upper()}] Row count mismatch: scanned={scanned_count}, extracted={extracted_count}",
            )

        # Level 2: Per-match atomic validation
        all_violations = []
        for match in matches:
            passed, violations = DataContract.validate_match(match, tab)
            if not passed:
                all_violations.extend(violations)

        if all_violations:
            summary = (
                f"[{tab.upper()}] {len(all_violations)} contract violation(s) in {extracted_count} matches:\n"
                + "\n".join(f"    • {v}" for v in all_violations[:20])
            )
            if len(all_violations) > 20:
                summary += f"\n    ... and {len(all_violations) - 20} more"
            return (False, summary)

        return (True, f"[{tab.upper()}] {extracted_count} matches — contract OK")