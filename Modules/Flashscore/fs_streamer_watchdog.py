# fs_streamer_watchdog.py: Watchdog and catch-up recovery for the LeoBook live streamer.
# Part of LeoBook Modules — Flashscore
#
# Split from fs_live_streamer.py (v9.6.0)
# Functions: is_streamer_alive(), _get_catch_up_start_date(),
#            _catch_up_from_live_stream(), navigation helpers.

"""
Streamer Watchdog Module
Provides liveness checks (heartbeat file) and catch-up/recovery logic
for the Flashscore live score streamer.
"""

import asyncio
import os
import subprocess
import sys
from datetime import datetime as dt, date, timedelta

import psutil

from Core.Utils.constants import now_ng

# Shared constant — must match fs_live_streamer._STREAMER_HEARTBEAT_FILE
_STREAMER_HEARTBEAT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', '..', 'Data', 'Store', '.streamer_heartbeat'
)


# ─── Liveness Check ───

def is_streamer_alive() -> bool:
    """Check if the streamer process is alive via PID existence + heartbeat age."""
    try:
        if os.path.exists(_STREAMER_HEARTBEAT_FILE):
            import json
            with open(_STREAMER_HEARTBEAT_FILE, 'r') as f:
                data = json.load(f)

            pid = data.get("pid")
            timestamp_str = data.get("timestamp")

            if not pid or not timestamp_str:
                return False

            if not psutil.pid_exists(pid):
                return False

            mtime = dt.fromisoformat(timestamp_str)
            now = now_ng().replace(tzinfo=None)
            if (now - mtime) > timedelta(minutes=15):
                return False

            return True
    except Exception:
        pass
    return False


# ─── Day Navigation Helpers ───

async def _navigate_to_next_day(page) -> bool:
    """Click the next-day arrow on the Flashscore calendar bar."""
    from Core.Intelligence.selector_manager import SelectorManager
    try:
        sel = SelectorManager.get_selector("fs_home_page", "next_day_button")
        if not sel:
            sel = 'button[data-day-picker-arrow="next"]'
        await page.click(sel, timeout=5000)
        await asyncio.sleep(2)
        return True
    except Exception as e:
        print(f"   [Watchdog] Failed to navigate to next day: {e}")
        return False


async def _navigate_to_prev_day(page) -> bool:
    """Click the prev-day arrow on the Flashscore calendar bar."""
    from Core.Intelligence.selector_manager import SelectorManager
    try:
        sel = SelectorManager.get_selector("fs_home_page", "prev_day_button")
        if not sel:
            sel = 'button[data-day-picker-arrow="prev"]'
        await page.click(sel, timeout=5000)
        await asyncio.sleep(2)
        return True
    except Exception as e:
        print(f"   [Watchdog] Failed to navigate to prev day: {e}")
        return False


# ─── Catch-Up / Recovery ───

def _get_catch_up_start_date() -> date | None:
    """Determine the earliest date that needs catch-up.

    Checks two persistent sources (schedules + predictions) for evidence
    that the streamer was down and matches went unresolved:
      1. schedules with match_status='live' (stale live matches)
      2. predictions with status='pending' for dates in the last 7 days

    Returns the earliest date needing resolution, or None if nothing is stale.
    """
    from Data.Access.db_helpers import _get_conn
    conn = _get_conn()
    today = date.today()
    week_ago = (today - timedelta(days=7)).isoformat()

    earliest = None

    rows = conn.execute(
        "SELECT date FROM schedules WHERE match_status = 'live' AND date >= ? ORDER BY date ASC LIMIT 1",
        (week_ago,)
    ).fetchone()
    if rows and rows[0]:
        try:
            candidate = date.fromisoformat(rows[0])
            if candidate < today and (earliest is None or candidate < earliest):
                earliest = candidate
        except ValueError:
            pass

    rows2 = conn.execute(
        "SELECT date FROM predictions WHERE status = 'pending' AND date >= ? AND date < ? ORDER BY date ASC LIMIT 1",
        (week_ago, today.isoformat())
    ).fetchone()
    if rows2 and rows2[0]:
        try:
            candidate = date.fromisoformat(rows2[0])
            if earliest is None or candidate < earliest:
                earliest = candidate
        except ValueError:
            pass

    return earliest


async def _catch_up_from_live_stream(page, sync):
    """Catch-up logic on startup/restart.

    Checks schedules/predictions for unresolved matches, then navigates
    day-by-day from the earliest stale date to today, extracting and
    propagating each day.
    """
    from Data.Access.db_helpers import _get_conn, log_audit_event
    from Modules.Flashscore.fs_extractor import extract_all_matches, expand_all_leagues as ensure_content_expanded
    from Modules.Flashscore.fs_live_streamer import _propagate_status_updates, _review_pending_backlog, _click_all_tab

    earliest = _get_catch_up_start_date()
    today = date.today()

    if earliest is None:
        print("   [Watchdog] No stale matches found — no catch-up needed.")
        return

    days_behind = (today - earliest).days
    if days_behind <= 0:
        print("   [Watchdog] All matches current — no catch-up needed.")
        return

    print(f"   [Watchdog] Catch-up needed: {days_behind} day(s) behind (earliest: {earliest}).")
    log_audit_event("STREAMER_CATCHUP_START", f"Catching up {days_behind} days from {earliest}.")

    if days_behind > 7:
        print(f"   [Watchdog] Gap > 7 days — falling back to --enrich-leagues --refresh.")
        log_audit_event("STREAMER_CATCHUP_REFRESH", f"Gap {days_behind}d > 7d, using refresh fallback.")
        try:
            leo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'Leo.py')
            subprocess.run(
                [sys.executable, leo_path, '--enrich-leagues', '--refresh'],
                cwd=os.path.dirname(leo_path), timeout=3600
            )
            subprocess.run(
                [sys.executable, leo_path, '--predictions'],
                cwd=os.path.dirname(leo_path), timeout=1800
            )
        except Exception as e:
            print(f"   [Watchdog] Refresh fallback error: {e}")

        conn = _get_conn()
        conn.execute("DELETE FROM live_scores")
        conn.commit()
        print("   [Watchdog] Cleared stale live_scores after refresh fallback.")
        return

    # ≤7 days: Navigate day-by-day from earliest to today
    print(f"   [Watchdog] Navigating back {days_behind} day(s) to {earliest}...")
    for _ in range(days_behind):
        if not await _navigate_to_prev_day(page):
            print("   [Watchdog] Could not navigate backward. Aborting catch-up.")
            return

    for day_offset in range(days_behind + 1):
        current_date = earliest + timedelta(days=day_offset)
        is_today = (current_date == today)
        print(f"   [Watchdog] Catch-up day {day_offset+1}/{days_behind+1}: {current_date}")

        await _click_all_tab(page)
        await ensure_content_expanded(page)
        all_matches = await extract_all_matches(page, label="CatchUp")

        LIVE_STATUSES = {'live', 'halftime', 'break', 'extra_time'}
        RESOLVED_STATUSES = {'finished', 'cancelled', 'postponed', 'fro', 'abandoned', 'interrupted'}

        live = [m for m in all_matches if m.get('status') in LIVE_STATUSES]
        resolved = [m for m in all_matches if m.get('status') in RESOLVED_STATUSES]

        if live or resolved:
            sched_upd, pred_upd = _propagate_status_updates(live, resolved)
            print(f"   [Watchdog] Catch-up {current_date}: {len(live)} live, {len(resolved)} resolved "
                  f"→ {len(sched_upd)} fixtures, {len(pred_upd)} predictions.")

            if sync.supabase:
                if pred_upd:
                    await sync.batch_upsert('predictions', pred_upd)
                if sched_upd:
                    await sync.batch_upsert('schedules', sched_upd)
        else:
            print(f"   [Watchdog] Catch-up {current_date}: 0 matches (off-day or no data).")

        if not is_today:
            await _navigate_to_next_day(page)

    conn = _get_conn()
    conn.execute("DELETE FROM live_scores")
    conn.commit()
    print("   [Watchdog] Cleared old live_scores. Current live data will populate on first cycle.")

    backlog = _review_pending_backlog()
    if backlog and sync.supabase:
        await sync.batch_upsert('predictions', backlog)

    log_audit_event("STREAMER_CATCHUP_DONE", f"Catch-up complete. Processed {days_behind+1} days.")
    print(f"   [Watchdog] Catch-up complete. Resuming normal streaming.")
