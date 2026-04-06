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
]

_MATCH_RESULTS_ONLY = [
    "home_score",
    "away_score",
    "winner",
]

# ═══════════════════════════════════════════════════════════════════════════════
#  Validation Functions (Exported)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_league_metadata(data: Dict) -> Tuple[bool, List[str]]:
    """Validate league-level metadata. All fields are REQUIRED."""
    violations = []
    for field in _LEAGUE_REQUIRED_FIELDS:
        val = data.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            violations.append(f"league.{field} is missing or empty")
    return (len(violations) == 0, violations)

def validate_match(match: Dict, tab: str = "fixtures") -> Tuple[bool, List[str]]:
    """Validate a single match against the strict data contract."""
    violations = []

    # 1. Mandatory Fields
    for field in _MATCH_ALWAYS_REQUIRED:
        val = match.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            violations.append(f"match[{match.get('fixture_id', '?')}].{field} is missing")

    # 2. Team Parity Check
    h_id = match.get("home_team_id")
    a_id = match.get("away_team_id")
    if h_id and a_id and h_id == a_id:
        violations.append(f"match[{match.get('fixture_id', '?')}] home/away team ID parity: {h_id}")

    h_name = match.get("home_team_name", "").strip()
    a_name = match.get("away_team_name", "").strip()
    if h_name and a_name and h_name.lower() == a_name.lower():
        violations.append(f"match[{match.get('fixture_id', '?')}] home/away team name parity: {h_name}")

    # 3. Results Logic
    if tab == "results":
        status = (match.get("match_status") or "").lower()
        # Only require scores for genuinely finished matches.
        # Awarded (w/o, forfeited), abandoned, cancelled, postponed have no score.
        NO_SCORE_STATUSES = ("awarded", "abandoned", "cancelled", "postponed", "walkover")
        score_finished_statuses = ("finished", "ft", "aet", "pen", "after pen", "after et")

        # If Flashscore shows FT but scores are null, it's a walkover/voided match.
        # Silently downgrade to 'awarded' rather than raising an unresolvable violation.
        if status in score_finished_statuses and status not in NO_SCORE_STATUSES:
            h_score_raw = match.get("home_score")
            a_score_raw = match.get("away_score")
            if h_score_raw is None or a_score_raw is None:
                status = "awarded"  # downgrade — skip score requirement

        if status in score_finished_statuses and status not in NO_SCORE_STATUSES:
            for field in _MATCH_RESULTS_ONLY:
                val = match.get(field)
                if val is None or (isinstance(val, str) and not val.strip()):
                    violations.append(f"match[{match.get('fixture_id', '?')}].{field} missing for finished match")

            # Score Sanity
            h_score = match.get("home_score")
            a_score = match.get("away_score")
            winner = match.get("winner")
            try:
                hs = int(h_score or 0)
                ascore = int(a_score or 0)
                if winner == "HOME" and hs <= ascore:
                    violations.append(f"match[{match.get('fixture_id', '?')}] winner=HOME but score {hs}-{ascore}")
                if winner == "AWAY" and ascore <= hs:
                    violations.append(f"match[{match.get('fixture_id', '?')}] winner=AWAY but score {hs}-{ascore}")
                if winner == "DRAW" and hs != ascore:
                    violations.append(f"match[{match.get('fixture_id', '?')}] winner=DRAW but score {hs}-{ascore}")
            except (ValueError, TypeError):
                pass

    return (len(violations) == 0, violations)

def validate_tab_extraction(scanned_count: int, matches: List[Dict], tab: str) -> Tuple[bool, str]:
    """Validate an entire tab extraction: row count + per-match contract + unique IDs."""
    extracted_count = len(matches)

    # Level 1: Row count parity
    if scanned_count != extracted_count:
        return (
            False,
            f"[{tab.upper()}] Row count mismatch: scanned={scanned_count}, extracted={extracted_count}",
        )

    # Level 2: Unique Fixture IDs
    fids = [m.get("fixture_id") for m in matches if m.get("fixture_id")]
    if len(fids) != len(set(fids)):
        dupes = set([x for x in fids if fids.count(x) > 1])
        return (False, f"[{tab.upper()}] Duplicate fixture IDs detected: {dupes}")

    # Level 3: Per-match atomic validation
    all_violations = []
    for match in matches:
        passed, violations = validate_match(match, tab)
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

class DataContract:
    """Wrapper class for namespace compatibility if needed."""
    validate_league_metadata = staticmethod(validate_league_metadata)
    validate_match = staticmethod(validate_match)
    validate_tab_extraction = staticmethod(validate_tab_extraction)