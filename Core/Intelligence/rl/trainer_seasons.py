# trainer_seasons.py: Season discovery and date-selection mixin for RLTrainer.
# Part of LeoBook Core — Intelligence (RL Engine)
#
# Classes: SeasonsMixin
# Mixed into RLTrainer via multiple inheritance.
#
# Encapsulates all season-scoping logic so trainer.py can focus on the
# gradient update loop. No instantiation — use only via RLTrainer.

"""
Season discovery and training date selection.

Supports four target_season modes:
  "current"   Per-league join against leagues.current_season (default).
  "all"       All available completed fixtures, oldest-first.
  int N       Past season by offset (1 = most recent past, 2 = two ago, …).
  str label   Explicit season label, e.g. "2024/2025" or "2025".

See _get_season_dates() docstring for detailed semantics.
"""

import re
from datetime import datetime
from typing import List, Tuple, Union


class SeasonsMixin:
    """Season discovery and date-selection methods for RLTrainer."""

    def _discover_seasons(self, conn) -> List[str]:
        """
        Return all distinct season labels found in schedules, most-recent-first.

        Sorts by the 4-digit start year embedded in the season string so both
        split-season ("2024/2025") and calendar-year ("2025") formats rank correctly.
        """
        rows = conn.execute(
            "SELECT DISTINCT season FROM schedules "
            "WHERE season IS NOT NULL AND season != ''"
        ).fetchall()
        seasons = [r[0] for r in rows]

        def _start_year(s: str) -> int:
            m = re.match(r'(\d{4})', s)
            return int(m.group(1)) if m else 0

        return sorted(seasons, key=_start_year, reverse=True)

    def _get_season_dates(
        self, conn, target_season: Union[str, int] = "current"
    ) -> Tuple[List[str], str]:
        """
        Build the ordered list of fixture-dates for training, filtered to the
        requested season scope.

        The model is fully season-aware: the primary path joins schedules against
        leagues.current_season per league, so each league's training window starts
        from its own actual season kickoff date — not a global cutoff.
        Split-season leagues (e.g. "2025/2026") and calendar-year leagues
        (e.g. "2025" or "2026") are both handled correctly via the season label
        stored in leagues.current_season.

        No date caps are applied to the primary path or the first fallback.
        A sanity check warns (but no longer aborts) if dates span >540 days.

        Args:
            target_season:
                "current"   — per-league join against leagues.current_season.
                "all"       — all available completed fixtures, oldest-first.
                int N       — past season by offset: 1 = most recent past.
                str label   — explicit season string, e.g. "2024/2025".

        Returns:
            (dates, label) — chronologically sorted date strings + human label.
        """
        today_str = datetime.now().strftime("%Y-%m-%d")

        # ── All seasons ──────────────────────────────────────────────────────
        if target_season == "all":
            rows = conn.execute("""
                SELECT DISTINCT date FROM schedules
                WHERE date IS NOT NULL
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
                  AND date <= ?
                ORDER BY date ASC
            """, (today_str,)).fetchall()
            return [r[0] for r in rows], "all seasons (oldest → newest)"

        # ── Past season by offset (int) ──────────────────────────────────────
        if isinstance(target_season, int) and target_season >= 1:
            seasons = self._discover_seasons(conn)
            if target_season >= len(seasons):
                print(f"  [TRAIN] Season offset {target_season} out of range "
                      f"({len(seasons)} seasons in DB). Falling back to current.")
            else:
                season_label = seasons[target_season]  # 1-indexed offset
                rows = conn.execute("""
                    SELECT DISTINCT date FROM schedules
                    WHERE season = ?
                      AND home_score IS NOT NULL AND away_score IS NOT NULL
                      AND date IS NOT NULL AND date <= ?
                    ORDER BY date ASC
                """, (season_label, today_str)).fetchall()
                if rows:
                    return [r[0] for r in rows], f"season {season_label} (past offset {target_season})"
                print(f"  [TRAIN] Season '{season_label}' has no completed fixtures. "
                      f"Falling back to current.")

        # ── Explicit season label (non-"current" string) ─────────────────────
        if isinstance(target_season, str) and target_season != "current":
            rows = conn.execute("""
                SELECT DISTINCT date FROM schedules
                WHERE season = ?
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
                  AND date IS NOT NULL AND date <= ?
                ORDER BY date ASC
            """, (target_season, today_str)).fetchall()
            if rows:
                return [r[0] for r in rows], f"season {target_season}"
            print(f"  [TRAIN] Season '{target_season}' not found or has no completed "
                  f"fixtures. Falling back to current.")

        # ── Current season (default) ─────────────────────────────────────────
        # Join schedules against leagues.current_season so training starts from
        # each league's actual season start date. No date cap applied here.
        rows = conn.execute("""
            SELECT DISTINCT s.date
            FROM schedules s
            INNER JOIN leagues l ON s.league_id = l.league_id
            WHERE s.season = l.current_season
              AND s.home_score IS NOT NULL AND s.away_score IS NOT NULL
              AND s.date IS NOT NULL AND s.date <= ?
            ORDER BY s.date ASC
        """, (today_str,)).fetchall()
        dates = [r[0] for r in rows]

        if dates:
            # Sanity check: no football season spans more than ~540 days.
            earliest = dates[0]
            days_back = (datetime.now() - datetime.strptime(earliest, "%Y-%m-%d")).days
            if days_back > 540:
                stale_leagues = conn.execute("""
                    SELECT DISTINCT l.league_id, l.name, l.current_season,
                           MIN(s.date) as earliest_date
                    FROM schedules s
                    INNER JOIN leagues l ON s.league_id = l.league_id
                    WHERE s.season = l.current_season
                      AND s.home_score IS NOT NULL AND s.away_score IS NOT NULL
                      AND s.date < date('now', '-540 days')
                    GROUP BY l.league_id
                    ORDER BY earliest_date ASC
                    LIMIT 10
                """).fetchall()
                print(
                    f"\n  [TRAIN] ! WARNING: Current-season join returned dates back to {earliest} "
                    f"({days_back} days ago).\n"
                    f"  [TRAIN]   No football season spans 540+ days. This may indicate stale metadata.\n"
                    f"  [TRAIN]   Iterating anyway as requested.\n"
                )
                for row in stale_leagues:
                    print(f"  [TRAIN]     {row[1] or row[0]:40s}  current_season={row[2]}  earliest={row[3]}")
                print("\n")

            return dates, "current season (per-league season join)"

        # ── First fallback: leagues.current_season not fully populated ────────
        seasons = self._discover_seasons(conn)
        if seasons:
            season_label = seasons[0]
            print(
                f"\n  [TRAIN] ⚠ WARNING: Current-season join returned no dates.\n"
                f"  [TRAIN]   leagues.current_season is not populated for enough leagues.\n"
                f"  [TRAIN]   Falling back to most recent season in DB: {season_label}\n"
                f"  [TRAIN]   → Run: python Leo.py --enrich-leagues\n"
                f"  [TRAIN]     to populate current_season and fix this properly.\n"
            )
            rows = conn.execute("""
                SELECT DISTINCT date FROM schedules
                WHERE season = ?
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
                  AND date IS NOT NULL AND date <= ?
                ORDER BY date ASC
            """, (season_label, today_str)).fetchall()
            dates = [r[0] for r in rows]
            if dates:
                return dates, (
                    f"season {season_label} "
                    f"(fallback — run --enrich-leagues to populate current_season)"
                )

        # ── Last resort: no season metadata — ABORT ───────────────────────────
        print(
            f"\n  [TRAIN] ✗ CRITICAL: No season metadata found in the database.\n"
            f"  [TRAIN]   Cannot determine current season boundaries for any league.\n"
            f"  [TRAIN]   Training aborted — this would span all available history.\n"
            f"\n"
            f"  [TRAIN]   Fix: python Leo.py --enrich-leagues\n"
            f"  [TRAIN]   Then retry: python Leo.py --train-rl\n"
            f"\n"
            f"  [TRAIN]   If you intentionally want to train on all history:\n"
            f"  [TRAIN]   Use: python Leo.py --train-rl --train-season all --cold\n"
        )
        return [], "aborted — no season metadata (run --enrich-leagues first)"


__all__ = ["SeasonsMixin"]
