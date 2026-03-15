# gap_models.py: Data models for the LeoBook gap scanning system.
# Part of LeoBook Data — Access Layer
# Used by: gap_scanner.py, enrich_leagues.py

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Column specification ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class ColumnSpec:
    """Describes a single required column and how to validate it."""
    name: str
    severity: str                   # "critical" | "important" | "enrichable"
    url_column: bool = False        # if True: value must start with "http"
    nullable_when: str = ""        # e.g. "match_status=scheduled" — skip gap for these rows
    description: str = ""


# ── Required column definitions per table ────────────────────────────────────

REQUIRED_COLUMNS: Dict[str, List[ColumnSpec]] = {
    "leagues": [
        ColumnSpec("league_id",      "critical",   description="Flashscore league slug"),
        ColumnSpec("name",           "critical",   description="League display name"),
        ColumnSpec("url",            "critical",   description="Flashscore league URL"),
        ColumnSpec("country_code",   "critical",   description="ISO country code"),
        ColumnSpec("fs_league_id",   "important",  description="Flashscore internal tournament ID"),
        ColumnSpec("region",         "important",  description="Human-readable region/country name"),
        ColumnSpec("region_url",     "enrichable", description="Region landing page URL"),
        ColumnSpec("crest",          "important",  url_column=True, description="League crest — must be Supabase URL"),
        ColumnSpec("current_season", "important",  description="E.g. '2024/2025' or '2024'"),
    ],
    "teams": [
        ColumnSpec("name",         "critical",   description="Team display name"),
        ColumnSpec("country_code", "critical",   description="ISO country code"),
        ColumnSpec("team_id",      "important",  description="Flashscore team ID"),
        ColumnSpec("crest",        "important",  url_column=True, description="Team crest — must be Supabase URL"),
        ColumnSpec("url",          "enrichable", description="Flashscore team page URL"),
    ],
    "schedules": [
        ColumnSpec("fixture_id",     "critical",   description="Flashscore fixture ID"),
        ColumnSpec("date",           "critical",   description="Match date YYYY-MM-DD"),
        ColumnSpec("league_id",      "critical",   description="Parent league slug"),
        ColumnSpec("season",         "critical",   description="Season string"),
        ColumnSpec("home_team_name", "critical",   description="Home team name"),
        ColumnSpec("away_team_name", "critical",   description="Away team name"),
        ColumnSpec("match_status",   "important",  description="finished/scheduled/live/etc."),
        ColumnSpec("home_team_id",   "important",  description="Home team Flashscore ID"),
        ColumnSpec("away_team_id",   "important",  description="Away team Flashscore ID"),
        ColumnSpec("home_crest",     "important",  url_column=True, description="Home team crest — must be Supabase URL"),
        ColumnSpec("away_crest",     "important",  url_column=True, description="Away team crest — must be Supabase URL"),
        ColumnSpec("time",           "enrichable", description="Match kick-off time HH:MM"),
        ColumnSpec("league_stage",   "enrichable", description="Round/group label"),
    ],
}

# Severity order for sorting (lower = more urgent)
_SEVERITY_ORDER = {"critical": 0, "important": 1, "enrichable": 2}


# ── Gap record ────────────────────────────────────────────────────────────────

@dataclass
class ColumnGap:
    """A single missing or invalid cell detected during scanning."""
    table: str
    column: str
    severity: str
    row_id: int                       # SQLite rowid
    league_id: str                    # parent league_id (resolved for teams)
    season: Optional[str]             # None for league-level gaps
    current_value: Optional[str]      # what is actually stored (for context)
    extra: Dict = field(default_factory=dict)  # e.g. fixture_id, team_name

    @property
    def is_critical(self) -> bool:
        return self.severity == "critical"

    @property
    def is_url_gap(self) -> bool:
        """True if the column has a value but it's a local path, not a URL."""
        return (
            self.current_value is not None
            and self.current_value != ""
            and not self.current_value.startswith("http")
        )


# ── Per-league summary ────────────────────────────────────────────────────────

@dataclass
class LeagueSeasonGapSummary:
    """Aggregated gap information for a single (league_id) across all its seasons."""
    league_id: str
    league_name: str
    league_url: str
    country_code: str
    continent: str

    # Seasons that need targeted re-enrichment (from schedules/teams gaps)
    seasons_with_gaps: List[str] = field(default_factory=list)

    # Column-level counts: {column_name: gap_count}
    gap_counts_by_column: Dict[str, int] = field(default_factory=dict)

    # Severity totals: {severity: count}
    severity_counts: Dict[str, int] = field(default_factory=lambda: {
        "critical": 0, "important": 0, "enrichable": 0
    })

    total_gaps: int = 0
    has_league_level_gaps: bool = False   # gaps in leagues table itself
    has_team_gaps: bool = False
    has_schedule_gaps: bool = False
    needs_full_re_enrich: bool = False    # True if league-level critical gaps found

    def add_gap(self, gap: ColumnGap) -> None:
        col_key = f"{gap.table}.{gap.column}"
        self.gap_counts_by_column[col_key] = self.gap_counts_by_column.get(col_key, 0) + 1
        self.severity_counts[gap.severity] = self.severity_counts.get(gap.severity, 0) + 1
        self.total_gaps += 1

        if gap.table == "leagues":
            self.has_league_level_gaps = True
            if gap.is_critical:
                self.needs_full_re_enrich = True
        elif gap.table == "teams":
            self.has_team_gaps = True
        elif gap.table == "schedules":
            self.has_schedule_gaps = True
            if gap.season and gap.season not in self.seasons_with_gaps:
                self.seasons_with_gaps.append(gap.season)

    def to_enrichment_target(self) -> Dict:
        """Return a dict consumable by enrich_leagues.enrich_single_league()."""
        return {
            "league_id":          self.league_id,
            "name":               self.league_name,
            "url":                self.league_url,
            "country_code":       self.country_code,
            "continent":          self.continent,
            "seasons_with_gaps":  sorted(set(self.seasons_with_gaps)),
            "needs_full_re_enrich": self.needs_full_re_enrich,
            "gap_summary": {
                "total":          self.total_gaps,
                "critical":       self.severity_counts.get("critical", 0),
                "important":      self.severity_counts.get("important", 0),
                "enrichable":     self.severity_counts.get("enrichable", 0),
                "by_column":      self.gap_counts_by_column,
                "has_league_gaps":   self.has_league_level_gaps,
                "has_team_gaps":     self.has_team_gaps,
                "has_schedule_gaps": self.has_schedule_gaps,
            },
        }


# ── Gap report ────────────────────────────────────────────────────────────────

@dataclass
class GapReport:
    """Full scan result. All gaps across leagues, teams, and schedules tables."""
    scanned_at: datetime
    summary_by_league: Dict[str, LeagueSeasonGapSummary]  # keyed by league_id
    all_gaps: List[ColumnGap]
    total_gaps: int
    scan_duration_ms: int

    # Quick-access breakdowns
    gaps_by_table: Dict[str, int] = field(default_factory=dict)
    gaps_by_severity: Dict[str, int] = field(default_factory=dict)
    gaps_by_column: Dict[str, int] = field(default_factory=dict)

    @property
    def has_gaps(self) -> bool:
        return self.total_gaps > 0

    @property
    def critical_gap_count(self) -> int:
        return self.gaps_by_severity.get("critical", 0)

    def leagues_needing_enrichment(
        self,
        min_severity: str = "important",
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """Return enrichment targets sorted by severity urgency."""
        severity_threshold = _SEVERITY_ORDER.get(min_severity, 1)

        targets = []
        for league_id, summary in self.summary_by_league.items():
            max_sev = min(
                _SEVERITY_ORDER.get(s, 9)
                for s, cnt in summary.severity_counts.items()
                if cnt > 0
            ) if summary.total_gaps > 0 else 9

            if max_sev <= severity_threshold:
                targets.append(summary.to_enrichment_target())

        targets.sort(
            key=lambda t: (
                0 if t["gap_summary"]["critical"] > 0 else 1,
                -t["gap_summary"]["total"],
            )
        )

        if limit:
            targets = targets[:limit]

        return targets

    def gaps_for_league_season(
        self, league_id: str, season: Optional[str] = None
    ) -> List[ColumnGap]:
        """Return all gaps for a specific league (and optionally season)."""
        return [
            g for g in self.all_gaps
            if g.league_id == league_id
            and (season is None or g.season == season)
        ]

    def print_report(self, show_row_details: bool = False) -> None:
        """Print a structured CLI gap report."""
        border = "=" * 70
        print(f"\n{border}")
        print(f"  GAP SCAN REPORT  —  {self.scanned_at.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Scan duration: {self.scan_duration_ms}ms")
        print(border)

        if not self.has_gaps:
            print("  [✓] All columns fully enriched. No gaps found.")
            print(f"{border}\n")
            return

        print(f"  Total gaps: {self.total_gaps:,}")
        print(f"  ├─ Critical:   {self.gaps_by_severity.get('critical',   0):>6,}")
        print(f"  ├─ Important:  {self.gaps_by_severity.get('important',  0):>6,}")
        print(f"  └─ Enrichable: {self.gaps_by_severity.get('enrichable', 0):>6,}")

        print(f"\n  By table:")
        for table in ("leagues", "teams", "schedules"):
            cnt = self.gaps_by_table.get(table, 0)
            if cnt:
                print(f"  ├─ {table:<12} {cnt:>6,} gaps")

        print(f"\n  By column (top 15):")
        sorted_cols = sorted(self.gaps_by_column.items(), key=lambda x: -x[1])
        for col, cnt in sorted_cols[:15]:
            bar = "█" * min(40, max(1, cnt * 40 // max(self.gaps_by_column.values())))
            print(f"  ├─ {col:<35} {cnt:>6,}  {bar}")

        print(f"\n  Leagues with gaps ({len(self.summary_by_league)}):")
        sorted_leagues = sorted(
            self.summary_by_league.values(),
            key=lambda s: (
                0 if s.severity_counts.get("critical", 0) > 0 else 1,
                -s.total_gaps,
            )
        )

        for s in sorted_leagues[:50]:
            crit  = s.severity_counts.get("critical", 0)
            imp   = s.severity_counts.get("important", 0)
            enr   = s.severity_counts.get("enrichable", 0)
            flags = []
            if s.has_league_level_gaps:  flags.append("LEAGUE")
            if s.has_team_gaps:          flags.append("TEAMS")
            if s.has_schedule_gaps:      flags.append(f"SCHED({len(s.seasons_with_gaps)}s)")
            flag_str = " ".join(flags)

            sev_str = ""
            if crit:  sev_str += f" C:{crit}"
            if imp:   sev_str += f" I:{imp}"
            if enr:   sev_str += f" E:{enr}"

            print(f"  ├─ {s.league_id:<30} [{sev_str.strip():>15}]  {flag_str}")
            if s.seasons_with_gaps:
                seasons_str = ", ".join(s.seasons_with_gaps[:5])
                if len(s.seasons_with_gaps) > 5:
                    seasons_str += f" (+{len(s.seasons_with_gaps)-5} more)"
                print(f"  │   seasons: {seasons_str}")

        if len(sorted_leagues) > 50:
            print(f"  └─ ... and {len(sorted_leagues) - 50} more leagues")

        if show_row_details:
            print(f"\n  Sample gaps (first 20):")
            for gap in self.all_gaps[:20]:
                val_str = repr(gap.current_value)[:40] if gap.current_value else "NULL"
                print(f"  ├─ [{gap.severity.upper():<10}] {gap.table}.{gap.column:<25} "
                      f"row={gap.row_id}  val={val_str}")

        print(f"{border}\n")

    def to_dict(self) -> Dict:
        """JSON-serialisable representation for audit logging."""
        return {
            "scanned_at":       self.scanned_at.isoformat(),
            "scan_duration_ms": self.scan_duration_ms,
            "total_gaps":       self.total_gaps,
            "gaps_by_table":    self.gaps_by_table,
            "gaps_by_severity": self.gaps_by_severity,
            "gaps_by_column":   self.gaps_by_column,
            "leagues_with_gaps": [
                s.to_enrichment_target()
                for s in self.summary_by_league.values()
            ],
        }


__all__ = [
    "ColumnSpec",
    "ColumnGap",
    "LeagueSeasonGapSummary",
    "GapReport",
    "REQUIRED_COLUMNS",
    "_SEVERITY_ORDER",
]
