# outcome_reviewer.py: Post-match results extraction (offline/DB layer).
# Part of LeoBook Data — Access Layer
#
# Core (non-browser): _load_schedule_db(), get_predictions_to_review(),
#   smart_parse_datetime(), save_single_outcome(), sync_schedules_to_predictions(),
#   process_review_task_offline()
# Browser functions: see outcome_reviewer_browser.py

"""
Outcome Reviewer Module
Core review processing and outcome analysis system.
All data persisted to leobook.db via league_db.py.
"""

import asyncio
import os
import re
import uuid
import pytz
import pandas as pd
from datetime import datetime as dt, timedelta
from typing import List, Dict, Any, Optional

from playwright.async_api import Playwright
from Core.Intelligence.aigo_suite import AIGOSuite

# --- CONFIGURATION ---
BATCH_SIZE = 10
LOOKBACK_LIMIT = 5000
ENRICHMENT_CONCURRENCY = 10
PRODUCTION_MODE = True
MAX_RETRIES = 3
HEALTH_CHECK_INTERVAL = 300
ERROR_THRESHOLD = 10
VERSION = "2.6.0"
COMPATIBLE_MODELS = ["2.5", "2.6"]

# --- IMPORTS ---
from .db_helpers import (
    save_team_entry, save_country_league_entry,
    evaluate_market_outcome, log_audit_event,
    get_all_schedules, update_prediction_status, _get_conn,
)
from Data.Access.league_db import (
    query_all, upsert_prediction, update_prediction,
    upsert_fb_match, upsert_accuracy_report,
)
from .sync_manager import SyncManager
from Core.Intelligence.selector_manager import SelectorManager
from Core.Intelligence.selector_db import log_selector_failure
from Core.Utils.constants import NAVIGATION_TIMEOUT


def _load_schedule_db() -> Dict[str, Dict]:
    """Loads fixtures from SQLite into a dict for quick lookups."""
    conn = _get_conn()
    rows = query_all(conn, 'schedules')
    return {r['fixture_id']: r for r in rows if r.get('fixture_id')}


def get_predictions_to_review() -> List[Dict]:
    """
    Reads predictions from SQLite and returns matches that are in the past
    (Africa/Lagos timezone) and still have a 'pending' status.
    """
    conn = _get_conn()
    rows = query_all(conn, 'predictions', "status = 'pending'")

    if not rows:
        return []

    # Convert to DataFrame for date filtering
    df = pd.DataFrame(rows).fillna('')

    def parse_dt_row(row):
        try:
            d_str = row.get('date') or row.get('Date')
            t_str = row.get('match_time')
            if not d_str or not t_str or t_str == 'N/A':
                return pd.NaT
            return dt.strptime(f"{d_str} {t_str}", "%d.%m.%Y %H:%M")
        except Exception:
            return pd.NaT

    df['scheduled_dt'] = df.apply(parse_dt_row, axis=1)
    df = df.dropna(subset=['scheduled_dt'])

    lagos_tz = pytz.timezone('Africa/Lagos')
    now_lagos = dt.now(lagos_tz)
    df['scheduled_dt'] = df['scheduled_dt'].apply(
        lambda x: lagos_tz.localize(x) if x.tzinfo is None else x
    )

    completion_cutoff = now_lagos - timedelta(hours=2, minutes=30)
    to_review_df = df[df['scheduled_dt'] < completion_cutoff]

    skipped = len(df[df['scheduled_dt'] < now_lagos]) - len(to_review_df)
    if skipped > 0:
        print(f"   [Filter] Skipped {skipped} matches still possibly in progress (<2.5h old).")

    if len(to_review_df) > LOOKBACK_LIMIT:
        to_review_df = to_review_df.tail(LOOKBACK_LIMIT)

    return to_review_df.to_dict('records')


def smart_parse_datetime(dt_str: str):
    """Attempts to parse date/time in various formats."""
    dt_str = dt_str.strip()
    if len(dt_str) > 10 and not dt_str[0].isdigit():
        dt_str = " ".join(dt_str.split()[1:])

    if len(dt_str) == 15 and dt_str[10].isdigit():
        dt_str = dt_str[:10] + " " + dt_str[10:]

    try:
        parts = dt_str.split()
        if len(parts) == 2:
            d_part, t_part = parts
            return d_part, t_part
    except Exception:
        pass
    return None, None


def save_single_outcome(match_data: Dict, new_status: str):
    """Atomic update of a prediction outcome in SQLite."""
    conn = _get_conn()
    row_id_key = 'ID' if 'ID' in match_data else 'fixture_id'
    target_id = match_data.get(row_id_key)

    if not target_id:
        return

    try:
        updates = {
            'status': new_status,
            'actual_score': match_data.get('actual_score', ''),
            'last_updated': dt.now().isoformat(),
        }

        if 'home_score' in match_data and 'away_score' in match_data:
            updates['actual_score'] = f"{match_data['home_score']}-{match_data['away_score']}"
            updates['home_score'] = match_data['home_score']
            updates['away_score'] = match_data['away_score']

        if new_status in ['reviewed', 'finished']:
            # Look up the prediction to evaluate outcome
            row = conn.execute(
                "SELECT prediction, home_team, away_team FROM predictions WHERE fixture_id = ?",
                (target_id,)
            ).fetchone()

            if row:
                prediction = row['prediction']
                home_team = row['home_team']
                away_team = row['away_team']
                actual_score = updates.get('actual_score', '')
                # Get match_status from schedule for AET/Pen detection
                sched = conn.execute(
                    "SELECT match_status FROM schedules WHERE fixture_id = ?", (target_id,)
                ).fetchone()
                match_status = (sched['match_status'] if sched else '') or match_data.get('match_status', '') or new_status

                score_match = re.match(r'(\d+)\s*-\s*(\d+)', actual_score or '')
                if score_match:
                    h_core, a_core = score_match.group(1), score_match.group(2)
                    res = evaluate_market_outcome(prediction, h_core, a_core, home_team, away_team,
                                                  match_status=match_status)
                    updates['outcome_correct'] = res if res else '0'

                    # Immediate cloud sync
                    print(f"      [Cloud] Immediate sync for {target_id}...")
                    full_row = dict(conn.execute(
                        "SELECT * FROM predictions WHERE fixture_id = ?", (target_id,)
                    ).fetchone())
                    full_row.update(updates)
                    asyncio.create_task(SyncManager().batch_upsert('predictions', [full_row]))
                else:
                    print(f"      [Eval Skip] Cannot parse score '{actual_score}' for {target_id}")

        update_prediction(conn, target_id, updates)

        if new_status == 'reviewed' and target_id:
            _sync_outcome_to_site_registry(target_id, match_data)




    except Exception as e:
        print(f"    [Health] save_error (high): Failed to save outcome: {e}")


def sync_schedules_to_predictions():
    """Ensures all entries in fixtures exist in predictions."""
    conn = _get_conn()
    schedules = query_all(conn, 'schedules')
    pred_ids = {r['fixture_id'] for r in query_all(conn, 'predictions') if r.get('fixture_id')}

    added_count = 0
    for s in schedules:
        fid = s.get('fixture_id')
        if fid and fid not in pred_ids:
            new_pred = {
                'fixture_id': fid,
                'date': s.get('date'),
                'match_time': s.get('time', s.get('match_time')),
                'country_league': s.get('country_league'),
                'home_team': s.get('home_team_name', s.get('home_team')),
                'away_team': s.get('away_team_name', s.get('away_team')),
                'home_team_id': s.get('home_team_id'),
                'away_team_id': s.get('away_team_id'),
                'prediction': 'PENDING',
                'confidence': 'Low',
                'status': s.get('match_status', 'pending'),
                'match_link': s.get('match_link', s.get('url')),
                'actual_score': f"{s.get('home_score', '')}-{s.get('away_score', '')}" if s.get('home_score') else 'N/A',
            }
            upsert_prediction(conn, new_pred)
            added_count += 1

    if added_count > 0:
        print(f"  [Sync] Added {added_count} missing entries from schedules to predictions.")


def _sync_outcome_to_site_registry(fixture_id: str, match_data: Dict):
    """Updates fb_matches when a prediction is reviewed."""
    conn = _get_conn()
    try:
        actual_score = match_data.get('actual_score', '')
        prediction = match_data.get('prediction', '')
        home_team = match_data.get('home_team', '')
        away_team = match_data.get('away_team', '')

        score_match = re.match(r'(\d+)\s*-\s*(\d+)', actual_score or '')
        if not score_match:
            return

        res = evaluate_market_outcome(prediction, score_match.group(1), score_match.group(2), home_team, away_team)
        if not res:
            return

        outcome_status = "WON" if res == '1' else "LOST"

        updated = conn.execute(
            "UPDATE fb_matches SET status = ?, last_updated = ? WHERE fixture_id = ?",
            (outcome_status, dt.now().isoformat(), str(fixture_id))
        ).rowcount
        conn.commit()

        if updated > 0:
            print(f"    [Sync] Updated {updated} records in fb_matches to {outcome_status}")

    except Exception as e:
        print(f"    [Sync Error] Failed to sync outcome: {e}")


def process_review_task_offline(match: Dict) -> Optional[Dict]:
    """Review a prediction by reading its result from fixtures (no browser)."""
    schedule_db = _load_schedule_db()
    fixture_id = match.get('fixture_id')
    schedule = schedule_db.get(fixture_id, {})

    match_status = str(schedule.get('match_status', '')).upper()
    home_score = str(schedule.get('home_score', '')).strip()
    away_score = str(schedule.get('away_score', '')).strip()

    has_valid_scores = home_score.isdigit() and away_score.isdigit()

    if match_status in ('FINISHED', 'AET', 'PEN') and has_valid_scores:
        match['home_score'] = home_score
        match['away_score'] = away_score
        match['actual_score'] = f"{home_score}-{away_score}"
        save_single_outcome(match, 'finished')
        print(f"    [Result] {match.get('home_team')} {match['actual_score']} {match.get('away_team')}")
        return match
    elif match_status == 'POSTPONED':
        save_single_outcome(match, 'match_postponed')
        return None
    elif match_status == 'CANCELED':
        save_single_outcome(match, 'canceled')
        return None
    return None



# ─── Re-exports from outcome_reviewer_browser (backward compat) ───
from Data.Access.outcome_reviewer_browser import (  # noqa
    process_review_task_browser, get_league_url, get_final_score,
    update_country_league_url, run_review_process, run_accuracy_generation,
)
