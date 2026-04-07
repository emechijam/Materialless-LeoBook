# basketball_tag_generator.py: Analytical tag generation for basketball insights.
# Part of LeoBook Core — Intelligence (AI Engine) — Basketball Rule Engine
#
# Classes: BasketballTagGenerator
# Markets: Total O/U, Team O/U (home/away), Halves O/U, Quarters O/U

from typing import List, Dict, Tuple


class BasketballTagGenerator:
    """
    Generates analysis tags for basketball form, H2H, and standings.

    Tag naming convention:
        {TEAM_SLUG}_FORM_{SIGNAL}       — from rolling form (last 10 matches)
        H2H_{SIGNAL}                    — from head-to-head history
        {TEAM_SLUG}_{SIGNAL}            — from standings (league tables)

    Unlike football (goals), basketball uses POINTS. Thresholds are calibrated
    for international / NBA-style competition (~220 pt total per game baseline).
    """

    # Scoring thresholds (per team, per full game)
    TEAM_HIGH_SCORE = 115    # Team regularly scoring high
    TEAM_LOW_SCORE  = 105    # Team regularly scoring low
    ELITE_OFFENSE   = 118    # Elite offensive output (standings)
    ELITE_DEFENSE   = 105    # Elite defensive output (standings, points AGAINST)

    # H2H total thresholds
    H2H_TOTAL_HIGH  = 220
    H2H_TOTAL_LOW   = 210

    # Pace thresholds (vs league avg)
    PACE_HIGH_DELTA = 15     # +15 above league avg → HIGH_PACE
    PACE_LOW_DELTA  = 15     # -15 below league avg → LOW_PACE

    @staticmethod
    def check_threshold(count: int, total: int, rule_type: str) -> bool:
        """True if count meets the threshold rule within total samples."""
        if total == 0:
            return False
        if rule_type == "majority":
            return count >= (total // 2 + 1)
        elif rule_type == "third":
            return count >= max(2, total // 3)
        elif rule_type == "quarter":
            return count >= max(2, total // 4)
        return False

    @staticmethod
    def _parse_match_scores(match: Dict) -> Tuple[int, int]:
        """Extract (home_pts, away_pts) from a match dict. Returns (0, 0) on failure."""
        if not match:
            return 0, 0
        try:
            ph = int(match.get("home_score", 0) or 0)
            pa = int(match.get("away_score", 0) or 0)
        except (ValueError, TypeError):
            # Fallback: try "score" key in "X-Y" format (legacy)
            score = match.get("score", "0-0")
            try:
                parts = score.replace(" ", "").split("-")
                ph, pa = int(parts[0]), int(parts[1])
            except Exception:
                ph = pa = 0
        return ph, pa

    # ─────────────────────────────────────────────────────────────
    # Form Tags
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def generate_form_tags(
        last_10_matches: List[Dict],
        team_name: str,
        is_home: bool = True,
        league_avg_total: float = 220.0,
    ) -> List[str]:
        """
        Generate rolling-form tags for a team's last N matches.

        Tags emitted (with team_slug prefix):
            _FORM_HIGH_SCORING    — team averaged ≥ TEAM_HIGH_SCORE in majority of games
            _FORM_LOW_SCORING     — team averaged ≤ TEAM_LOW_SCORE in majority of games
            _FORM_STRONG_DEFENSE  — opponent ≤ TEAM_LOW_SCORE in majority of games
            _FORM_WEAK_DEFENSE    — opponent ≥ TEAM_HIGH_SCORE in majority of games
            _FORM_HIGH_PACE       — avg total pts > league_avg + PACE_HIGH_DELTA
            _FORM_LOW_PACE        — avg total pts < league_avg - PACE_LOW_DELTA
            _FORM_WIN_STREAK      — majority of last 5 matches won
        """
        matches = [m for m in last_10_matches if m]
        N = len(matches)
        if N < 3:
            return []

        team_slug = team_name.replace(" ", "_").upper()
        counts = {
            "HIGH_SCORING": 0, "LOW_SCORING": 0,
            "STRONG_DEFENSE": 0, "WEAK_DEFENSE": 0,
        }
        win_count = 0
        totals_list = []

        for m in matches:
            ph, pa = BasketballTagGenerator._parse_match_scores(m)
            total = ph + pa
            totals_list.append(total)

            is_home_match = m.get("home", "") == team_name
            team_pts = ph if is_home_match else pa
            opp_pts  = pa if is_home_match else ph

            if team_pts >= BasketballTagGenerator.TEAM_HIGH_SCORE:
                counts["HIGH_SCORING"] += 1
            if team_pts <= BasketballTagGenerator.TEAM_LOW_SCORE:
                counts["LOW_SCORING"]  += 1
            if opp_pts  <= BasketballTagGenerator.TEAM_LOW_SCORE:
                counts["STRONG_DEFENSE"] += 1
            if opp_pts  >= BasketballTagGenerator.TEAM_HIGH_SCORE:
                counts["WEAK_DEFENSE"]   += 1

            # Win check
            if (is_home_match and ph > pa) or (not is_home_match and pa > ph):
                win_count += 1

        tags = []
        for signal, cnt in counts.items():
            if BasketballTagGenerator.check_threshold(cnt, N, "majority"):
                tags.append(f"{team_slug}_FORM_{signal}")
            elif BasketballTagGenerator.check_threshold(cnt, N, "third"):
                tags.append(f"{team_slug}_FORM_{signal}")

        # Win streak signal (from last 5)
        recent_5 = matches[:5]
        recent_wins = sum(
            1 for m in recent_5
            if (m.get("home", "") == team_name and BasketballTagGenerator._parse_match_scores(m)[0] > BasketballTagGenerator._parse_match_scores(m)[1])
            or (m.get("home", "") != team_name and BasketballTagGenerator._parse_match_scores(m)[1] > BasketballTagGenerator._parse_match_scores(m)[0])
        )
        if recent_wins >= 3:
            tags.append(f"{team_slug}_FORM_WIN_STREAK")

        # Pace signals (vs league average)
        if totals_list:
            avg_total = sum(totals_list) / len(totals_list)
            if avg_total > league_avg_total + BasketballTagGenerator.PACE_HIGH_DELTA:
                tags.append(f"{team_slug}_FORM_HIGH_PACE")
            elif avg_total < league_avg_total - BasketballTagGenerator.PACE_LOW_DELTA:
                tags.append(f"{team_slug}_FORM_LOW_PACE")

        return list(set(tags))

    # ─────────────────────────────────────────────────────────────
    # H2H Tags
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def generate_h2h_tags(
        h2h_list: List[Dict],
        home_team: str,
        away_team: str,
    ) -> List[str]:
        """
        Generate head-to-head tags.

        Tags emitted:
            H2H_TOTAL_OVER_220   — majority of meetings had totals > 220
            H2H_TOTAL_UNDER_210  — majority of meetings had totals < 210
            {HOME_SLUG}_H2H_DOM  — home team won majority of H2H matchups
            {AWAY_SLUG}_H2H_DOM  — away team won majority of H2H matchups
        """
        matches = [m for m in h2h_list if m]
        N = len(matches)
        if N < 2:
            return []

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        home_wins = 0
        away_wins = 0
        over_220_cnt = 0
        under_210_cnt = 0

        for m in matches:
            ph, pa = BasketballTagGenerator._parse_match_scores(m)
            total  = ph + pa

            if total > BasketballTagGenerator.H2H_TOTAL_HIGH:
                over_220_cnt  += 1
            if total < BasketballTagGenerator.H2H_TOTAL_LOW:
                under_210_cnt += 1

            # Determine winner relative to current fixture orientation
            is_home = m.get("home", "") == home_team
            home_g  = ph if is_home else pa
            away_g  = pa if is_home else ph
            if home_g > away_g:
                home_wins += 1
            elif away_g > home_g:
                away_wins += 1

        tags = []
        if BasketballTagGenerator.check_threshold(over_220_cnt, N, "majority"):
            tags.append("H2H_TOTAL_OVER_220")
        if BasketballTagGenerator.check_threshold(under_210_cnt, N, "majority"):
            tags.append("H2H_TOTAL_UNDER_210")
        if BasketballTagGenerator.check_threshold(home_wins, N, "majority"):
            tags.append(f"{home_slug}_H2H_DOM")
        if BasketballTagGenerator.check_threshold(away_wins, N, "majority"):
            tags.append(f"{away_slug}_H2H_DOM")

        return list(set(tags))

    # ─────────────────────────────────────────────────────────────
    # Standings Tags
    # ─────────────────────────────────────────────────────────────

    @staticmethod
    def generate_standings_tags(
        standings: List[Dict],
        home_team: str,
        away_team: str,
    ) -> List[str]:
        """
        Generate standings-based tags.

        Basketball standings use points_for / points_against,
        not goals. Falls back to points if pf/pa unavailable.

        Tags emitted:
            {SLUG}_TOP3           — team ranked in top 3
            {SLUG}_BOTTOM5        — team ranked in bottom 5
            {SLUG}_ELITE_OFFENSE  — avg points_for >= ELITE_OFFENSE threshold
            {SLUG}_ELITE_DEFENSE  — avg points_against <= ELITE_DEFENSE threshold
            {SLUG}_TABLE_ADV8+    — team has 8+ position advantage
        """
        if not standings:
            return []

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        league_size = len(standings)
        stats = {}
        for row in standings:
            name = row.get("team_name", row.get("team", ""))
            stats[name] = {
                "pos":   int(row.get("position", row.get("rank", 99))),
                "pf":    float(row.get("points_for",     row.get("goals_for",     0)) or 0),
                "pa":    float(row.get("points_against", row.get("goals_against", 0)) or 0),
            }

        tags = []
        for team_name, slug in [(home_team, home_slug), (away_team, away_slug)]:
            s = stats.get(team_name)
            if not s:
                continue
            pos = s["pos"]
            pf  = s["pf"]
            pa  = s["pa"]

            if pos <= 3:
                tags.append(f"{slug}_TOP3")
            if pos > league_size - 5:
                tags.append(f"{slug}_BOTTOM5")
            if pf >= BasketballTagGenerator.ELITE_OFFENSE:
                tags.append(f"{slug}_ELITE_OFFENSE")
            if 0 < pa <= BasketballTagGenerator.ELITE_DEFENSE:
                tags.append(f"{slug}_ELITE_DEFENSE")

        # Table advantage
        h_pos = stats.get(home_team, {}).get("pos", 99)
        a_pos = stats.get(away_team, {}).get("pos", 99)
        if h_pos < a_pos - 8:
            tags.append(f"{home_slug}_TABLE_ADV8+")
        if a_pos < h_pos - 8:
            tags.append(f"{away_slug}_TABLE_ADV8+")

        return list(set(tags))
