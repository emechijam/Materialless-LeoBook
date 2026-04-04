# data_provider.py: IDataProvider interface for LeoBook data access.
# Part of LeoBook Core — Data
#
# Defines the contract that all data-access implementations must satisfy.
# Concrete implementations: SqliteDataProvider (wraps league_db + db_helpers).

"""
IDataProvider Interface
Abstract data-access contract for LeoBook prediction/schedule/standings data.

All Core modules should depend on this interface rather than importing
league_db or db_helpers directly — this makes unit testing and future
data-source swaps (e.g. Supabase direct, API) trivial.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IDataProvider(ABC):
    """Abstract interface for all LeoBook data-access operations."""

    # ─── Predictions ───

    @abstractmethod
    def get_predictions(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Return all predictions, optionally filtered by column equality."""

    @abstractmethod
    def save_prediction(self, match_data: Dict[str, Any], prediction_result: Dict[str, Any]) -> None:
        """Persist a new or updated prediction."""

    @abstractmethod
    def update_prediction_status(self, fixture_id: str, new_status: str, **kwargs) -> None:
        """Update status (and optional fields) for a single prediction."""

    # ─── Schedules / Fixtures ───

    @abstractmethod
    def get_schedules(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all fixtures, optionally filtered by date (YYYY-MM-DD)."""

    @abstractmethod
    def save_schedule(self, match_info: Dict[str, Any]) -> None:
        """Persist a schedule entry."""

    # ─── Standings ───

    @abstractmethod
    def get_standings(self, country_league: str) -> List[Dict[str, Any]]:
        """Return standings for a specific league."""

    @abstractmethod
    def save_standings(self, standings_data: List[Dict[str, Any]], country_league: str,
                       league_id: str = "") -> None:
        """Persist standings for a specific league."""

    # ─── Teams ───

    @abstractmethod
    def get_team_crest(self, team_id: str, team_name: str = "") -> str:
        """Return the crest URL for a team, or empty string if not found."""

    @abstractmethod
    def save_team(self, team_info: Dict[str, Any]) -> None:
        """Persist a team entry."""

    # ─── Leagues ───

    @abstractmethod
    def save_league(self, league_info: Dict[str, Any]) -> None:
        """Persist a league/region entry."""

    # ─── Accuracy Reports ───

    @abstractmethod
    def save_accuracy_report(self, report: Dict[str, Any]) -> None:
        """Persist an accuracy/ROI report row."""


class SqliteDataProvider(IDataProvider):
    """Concrete implementation backed by leobook.db via league_db + db_helpers."""

    def get_predictions(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        from Data.Access.db_helpers import _get_conn
        from Data.Access.league_db import query_all
        conn = _get_conn()
        if filters:
            where = " AND ".join([f"{k} = ?" for k in filters])
            params = tuple(filters.values())
            return query_all(conn, 'predictions', where, params)
        return query_all(conn, 'predictions')

    def save_prediction(self, match_data: Dict[str, Any], prediction_result: Dict[str, Any]) -> None:
        from Data.Access.db_helpers import save_prediction as _save
        _save(match_data, prediction_result)

    def update_prediction_status(self, fixture_id: str, new_status: str, **kwargs) -> None:
        from Data.Access.db_helpers import update_prediction_status as _upd
        _upd(fixture_id, '', new_status, **kwargs)

    def get_schedules(self, date: Optional[str] = None) -> List[Dict[str, Any]]:
        from Data.Access.db_helpers import _get_conn
        from Data.Access.league_db import query_all
        conn = _get_conn()
        if date:
            return query_all(conn, 'schedules', 'date = ?', (date,))
        return query_all(conn, 'schedules')

    def save_schedule(self, match_info: Dict[str, Any]) -> None:
        from Data.Access.db_helpers import save_schedule_entry
        save_schedule_entry(match_info)

    def get_standings(self, country_league: str) -> List[Dict[str, Any]]:
        from Data.Access.db_helpers import get_standings as _get
        return _get(country_league)

    def save_standings(self, standings_data: List[Dict[str, Any]], country_league: str,
                       league_id: str = "") -> None:
        from Data.Access.db_helpers import save_standings as _save
        _save(standings_data, country_league, league_id)

    def get_team_crest(self, team_id: str, team_name: str = "") -> str:
        from Data.Access.db_helpers import get_team_crest
        return get_team_crest(team_id, team_name)

    def save_team(self, team_info: Dict[str, Any]) -> None:
        from Data.Access.db_helpers import save_team_entry
        save_team_entry(team_info)

    def save_league(self, league_info: Dict[str, Any]) -> None:
        from Data.Access.db_helpers import save_country_league_entry
        save_country_league_entry(league_info)

    def save_accuracy_report(self, report: Dict[str, Any]) -> None:
        from Data.Access.db_helpers import _get_conn
        from Data.Access.league_db import upsert_accuracy_report
        upsert_accuracy_report(_get_conn(), report)
