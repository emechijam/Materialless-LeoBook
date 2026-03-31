# fb_contract.py: Strict data contract for Football.com extracted data.
# Part of LeoBook Modules — Football.com v9.5.7

from typing import Dict, Any, List

class DataContractViolation(Exception):
    """Raised when extracted data fails strict quality requirements."""
    pass

class FBDataContract:
    """
    Enforces "Perfect or Gone" philosophy for Football.com data.
    Ensures mandatory fields exist and are reasonably populated.
    """

    MANDATORY_MATCH_FIELDS = ['home', 'away', 'time', 'league', 'url']

    @staticmethod
    def validate_match(match: Dict[str, Any]):
        """
        Validates a single match entry extracted from Football.com.
        
        Rules:
        1. All MANDATORY_MATCH_FIELDS must exist and not be empty/N/A.
        2. Home and Away teams must be different.
        """
        for field in FBDataContract.MANDATORY_MATCH_FIELDS:
            val = match.get(field)
            if not val or str(val).strip().upper() in ('', 'N/A', 'UNKNOWN', 'NONE'):
                raise DataContractViolation(f"Missing mandatory field '{field}' for match: {match.get('home')} v {match.get('away')}")

        if match['home'].lower().strip() == match['away'].lower().strip():
            raise DataContractViolation(f"Identical home/away teams detected: {match['home']}")

    @staticmethod
    def validate_odds_batch(odds_list: List[Dict[str, Any]]):
        """
        Validates a batch of odds for a single fixture.
        
        Rules:
        1. Must not be empty.
        2. Every entry must have fixture_id and odds_value > 1.0.
        """
        if not odds_list:
            raise DataContractViolation("Odds batch is empty.")

        for odds in odds_list:
            if not odds.get('fixture_id'):
                raise DataContractViolation("Odds entry missing fixture_id.")
            
            try:
                val = float(odds.get('odds_value', 0))
                if val <= 1.0:
                    raise DataContractViolation(f"Invalid odds value: {val}")
            except (ValueError, TypeError):
                raise DataContractViolation(f"Non-numeric odds value: {odds.get('odds_value')}")
