# market_evaluator.py: Unified market outcome evaluator for LeoBook.
# Part of LeoBook Data — Access Layer
# Pure function — no I/O, no DB access.
# Imported by: db_helpers.py, outcome_reviewer.py, paper_trade_helpers.py

import re
from typing import Optional


def evaluate_market_outcome(prediction: str, home_score: str, away_score: str,
                            home_team: str = "", away_team: str = "",
                            match_status: str = "") -> Optional[str]:
    """
    Unified First-Principles Outcome Evaluator (v5.0).
    Returns '1' (Correct), '0' (Incorrect), or '' (Unknown/Void).

    Settlement is based on 90min + stoppage time (regulation FT) ONLY.
    If match_status is 'aet'/'pen'/'after pen', the match was a DRAW at FT,
    so any draw-component prediction (1X, X2, draw) wins immediately.

    Handles: 1X2, Double Chance, DNB, Over/Under, BTTS, Team Over/Under,
             Winner & BTTS, Clean Sheet, and team-specific predictions.
    """
    try:
        h = int(home_score)
        a = int(away_score)
        total = h + a
    except (ValueError, TypeError):
        return ''

    p = (prediction or '').strip().lower()
    h_lower = (home_team or '').strip().lower()
    a_lower = (away_team or '').strip().lower()
    status = (match_status or '').strip().lower()

    # AET/Pen detection: match went beyond 90min = it was a DRAW at regulation FT.
    is_regulation_draw = status in ('aet', 'pen', 'after pen', 'after extra time',
                                    'after penalties', 'ap', 'finished aet',
                                    'finished ap', 'finished pen')
    if is_regulation_draw:
        _draw_markets = ('draw', 'x', '1x', 'x2', 'home or draw', 'home_or_draw',
                         'away or draw', 'away_or_draw', 'draw or away',
                         'double chance 1x', 'double chance x2')
        if p in _draw_markets or ' or draw' in p or 'draw or ' in p:
            return '1'
        if p in ('home win', 'home_win', '1', 'away win', 'away_win', '2'):
            return '0'
        if p.endswith(' to win') and 'btts' not in p:
            return '0'
        if '(dnb)' in p:
            return ''

    def _team_matches(candidate: str, reference: str) -> bool:
        if not candidate or not reference:
            return False
        return candidate == reference or reference.startswith(candidate) or candidate.startswith(reference)

    def _is_home(team_str: str) -> bool:
        return _team_matches(team_str, h_lower)

    def _is_away(team_str: str) -> bool:
        return _team_matches(team_str, a_lower)

    # 0. Winner & BTTS
    btts_win_match = re.match(r'^(.+?)\s+to\s+win\s*&\s*btts\s+yes$', p)
    if btts_win_match:
        team = btts_win_match.group(1).strip()
        btts = h > 0 and a > 0
        if _is_home(team): return '1' if h > a and btts else '0'
        if _is_away(team): return '1' if a > h and btts else '0'

    # 1. Standard Markets
    if p in ("over 2.5", "over 2_5", "over_2.5", "over_2_5"): return '1' if total > 2.5 else '0'
    if p in ("under 2.5", "under 2_5", "under_2.5", "under_2_5"): return '1' if total < 2.5 else '0'
    if p in ("over 1.5", "over 1_5", "over_1.5", "over_1_5"): return '1' if total > 1.5 else '0'
    if p in ("under 1.5", "under 1_5", "under_1.5", "under_1_5"): return '1' if total < 1.5 else '0'
    if p in ("btts yes", "btts_yes", "both teams to score yes", "both teams to score"): return '1' if h > 0 and a > 0 else '0'
    if p in ("btts no", "btts_no", "both teams to score no"): return '1' if h == 0 or a == 0 else '0'
    if p in ("home win", "home_win", "1"): return '1' if h > a else '0'
    if p in ("away win", "away_win", "2"): return '1' if a > h else '0'
    if p in ("draw", "x"): return '1' if h == a else '0'

    # 1a. Double Chance
    if p in ("home or away", "12", "1 2", "double chance 12"): return '1' if h != a else '0'
    if p in ("1x", "home or draw", "home_or_draw", "double chance 1x"): return '1' if h >= a else '0'
    if p in ("x2", "away or draw", "away_or_draw", "draw or away", "double chance x2"): return '1' if a >= h else '0'

    # 2. "Team to win"
    if p.endswith(" to win"):
        team = p.replace(" to win", "").strip()
        if _is_home(team): return '1' if h > a else '0'
        if _is_away(team): return '1' if a > h else '0'

    # 3. "Team or Draw" / Double Chance (team-name based)
    if " or draw" in p:
        team = p.replace(" or draw", "").strip()
        if _is_home(team): return '1' if h >= a else '0'
        if _is_away(team): return '1' if a >= h else '0'
    if "draw or " in p:
        team = p.replace("draw or ", "").strip()
        if _is_home(team): return '1' if h >= a else '0'
        if _is_away(team): return '1' if a >= h else '0'

    or_match = re.match(r'^(.+?)\s+or\s+(.+?)$', p)
    if or_match and "draw" not in p:
        t1 = or_match.group(1).strip()
        t2 = or_match.group(2).strip()
        if (_is_home(t1) and _is_away(t2)) or (_is_away(t1) and _is_home(t2)):
            return '1' if h != a else '0'

    # 4. Draw No Bet
    if p.endswith(" (dnb)"):
        team = p.replace(" to win (dnb)", "").replace(" (dnb)", "").strip()
        if h == a: return ''
        if _is_home(team): return '1' if h > a else '0'
        if _is_away(team): return '1' if a > h else '0'

    # 5. Dynamic Over/Under
    over_match = re.search(r'over\s+([\d.]+)', p)
    if over_match:
        threshold = float(over_match.group(1))
        team_part = p[:over_match.start()].strip()
        if team_part:
            if _is_home(team_part): return '1' if h > threshold else '0'
            if _is_away(team_part): return '1' if a > threshold else '0'
        if "away" in p: return '1' if a > threshold else '0'
        if "home" in p: return '1' if h > threshold else '0'
        return '1' if total > threshold else '0'

    under_match = re.search(r'under\s+([\d.]+)', p)
    if under_match:
        threshold = float(under_match.group(1))
        team_part = p[:under_match.start()].strip()
        if team_part:
            if _is_home(team_part): return '1' if h < threshold else '0'
            if _is_away(team_part): return '1' if a < threshold else '0'
        if "away" in p: return '1' if a < threshold else '0'
        if "home" in p: return '1' if h < threshold else '0'
        return '1' if total < threshold else '0'

    # 6. Clean Sheet
    if "clean sheet" in p:
        team = p.replace(" clean sheet", "").strip()
        if _is_home(team): return '1' if a == 0 else '0'
        if _is_away(team): return '1' if h == 0 else '0'

    return ''


__all__ = ["evaluate_market_outcome"]
