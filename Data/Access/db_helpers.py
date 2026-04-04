# db_helpers.py: High-level database access layer for LeoBook.
# Part of LeoBook Data — Access Layer
#
# Thin facade over league_db.py (the SQLite source of truth).
# Delegates to db_helpers_import.py (predictions/schedules/standings/teams)
# and db_helpers_audit.py (country codes/FB registry/odds/legacy stubs).
# All function signatures are preserved for backward compatibility.

"""
Database Helpers Module
Thin re-export facade for backward compatibility.
See db_helpers_import.py and db_helpers_audit.py for the implementations.
"""

import os
import logging
import uuid
import asyncio
from datetime import datetime as dt
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from Data.Access.league_db import (
    init_db, get_connection, DB_PATH,
    log_audit_event as _log_audit_db,
    get_fb_url_for_league,
)

# ─── Re-exports from db_helpers_import ───
from Data.Access.db_helpers_import import (
    save_prediction, update_prediction_status, backfill_prediction_entry,
    get_last_processed_info,
    save_schedule_entry, transform_streamer_match_to_schedule,
    save_schedule_batch, get_all_schedules,
    save_live_score_entry,
    save_standings, get_standings,
    _standardize_url,
    save_country_league_entry,
    save_team_entry, get_team_crest, propagate_crest_urls,
)

# ─── Re-exports from db_helpers_audit ───
from Data.Access.db_helpers_audit import (
    fill_national_team_country_codes, fill_club_team_country_codes,
    fill_all_country_codes,
    get_site_match_id, save_site_matches, save_match_odds, get_match_odds,
    load_site_matches, load_harvested_site_matches, update_site_match_status,
    _read_csv, _write_csv, _append_to_csv, upsert_entry, batch_upsert,
    append_to_csv, CSV_LOCK, files_and_headers,
)

# ─── Re-export from market_evaluator ───
from Data.Access.market_evaluator import evaluate_market_outcome  # noqa

# ─── Re-exports from rl_config_crud ───
from Data.Access.rl_config_crud import (
    get_rl_config, save_rl_config, update_rl_config_field,
    delete_rl_config, list_rl_configs, apply_rl_config_to_pipeline,
)  # noqa


# ─── Module-level connection (lazy init) ───

_conn = None

def _get_conn():
    global _conn
    if _conn is None:
        _conn = init_db()
    return _conn


# ─── Initialization ───

def init_csvs():
    """Initialize the database. Legacy name preserved for compatibility."""
    print("     Initializing databases...")
    conn = _get_conn()
    init_readiness_cache_table(conn)

def init_readiness_cache_table(conn=None):
    """Initialize the readiness_cache table (Section 2 - Scalability)."""
    conn = conn or _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readiness_cache (
            gate_id TEXT PRIMARY KEY,
            is_ready INTEGER,
            details TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    print("     [Cache] Readiness cache table initialized.")


# ─── Audit Log ───

def log_audit_event(event_type: str, description: str, balance_before: Optional[float] = None,
                    balance_after: Optional[float] = None, stake: Optional[float] = None,
                    status: str = 'success'):
    """Logs a financial or system event to audit_log."""
    _log_audit_db(_get_conn(), {
        'id': str(uuid.uuid4()),
        'timestamp': dt.now().strftime("%Y-%m-%d %H:%M:%S"),
        'event_type': event_type,
        'description': description,
        'balance_before': balance_before,
        'balance_after': balance_after,
        'stake': stake,
        'status': status,
    })
