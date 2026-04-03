# supervisor.py: Orchestrator for the LeoBook autonomous cycle.
# Part of LeoBook Core — System
#
# Classes: Supervisor
# Functions: run_cycle(), dispatch(), capture_state()
# Called by: Leo.py

import logging
import json
import asyncio
import subprocess
import sys
import uuid
import time
from datetime import datetime as dt
from typing import Type, Dict, Any, Optional

from Core.Utils.constants import now_ng
from Data.Access.league_db import init_db
from Core.System.worker_base import BaseWorker

logger = logging.getLogger(__name__)

class Supervisor:
    """
    Orchestrates the autonomous cycle and manages worker lifecycles.
    Handles timeout, retries, and state persistence.
    """
    
    def __init__(self, args=None):
        self.conn = init_db()
        self._ensure_table()
        self.args = args
        self.run_id = str(uuid.uuid4())[:8]
        self.last_streamer_spawn = 0 # Cooldown tracker
        self.state = {
            "cycle_count": 0,
            "error_log": [],
            "last_run": None,
            "status": "idle"
        }

    def _ensure_table(self):
        """Initialize the system_state SQLite table if it doesn't exist."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS system_state (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def capture_state(self, key: str, value: Any):
        """Persist a piece of state to the database."""
        self.conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            (key, json.dumps(value), now_ng().isoformat())
        )
        self.conn.commit()

    def get_state(self, key: str, default: Any = None) -> Any:
        """Retrieve a piece of state from the database."""
        row = self.conn.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
        if row:
            return json.loads(row[0])
        return default

    async def dispatch(self, worker_class: Type[BaseWorker], *args, timeout: int = 1800, max_retries: int = 2, **kwargs) -> bool:
        """
        Instantiates and executes a worker with timeout and retry logic.
        Handles playwright_instance requirement for specific workers.
        """
        # Handle workers that require playwright_instance in __init__
        p_instance = kwargs.get('playwright_instance')
        if p_instance and worker_class.__name__ in ('Chapter1Worker', 'Chapter2Worker'):
            worker = worker_class(p_instance)
            # Remove from kwargs to avoid double-passing to execute()
            del kwargs['playwright_instance']
        else:
            worker = worker_class()

        attempt = 0
        while attempt <= max_retries:
            try:
                logger.info(f"[Supervisor] Dispatching {worker.name} (Attempt {attempt+1}/{max_retries+1})")
                async with asyncio.timeout(timeout):
                    # Inject args if not already present
                    if 'args' not in kwargs:
                        kwargs['args'] = self.args
                    success = await worker.execute(*args, **kwargs)
                    if success:
                        return True
                    else:
                        logger.warning(f"[Supervisor] Worker {worker.name} returned False.")
            except asyncio.TimeoutError:
                logger.error(f"[Supervisor] Worker {worker.name} timed out after {timeout} seconds.")
            except Exception as e:
                await worker.on_failure(e)
            
            attempt += 1
            if attempt <= max_retries:
                wait_time = 5 * attempt
                logger.info(f"[Supervisor] Retrying {worker.name} in {wait_time}s...")
                await asyncio.sleep(wait_time)
        
        return False

    # ── Agentic sequencing helpers ────────────────────────────────────────────

    def _chapter_plan(self) -> dict:
        """
        Decide which chapters to run this cycle based on time-of-day and
        data availability.  Returns a dict with boolean flags:

            run_prologue   — always True (data gates are cheap)
            run_chapter1   — True if within the prediction window (06:00–20:00)
                             AND we haven't run Ch1 already today
            run_chapter2   — True if within the booking window (08:00–22:00)
                             AND booking is not already done today
                             AND Ch1 produced booking codes this session

        The plan is logged so operators can see why a chapter was skipped.
        """
        now = now_ng()
        hour = now.hour
        today = now.strftime("%Y-%m-%d")

        last_ch1_date = self.get_state("last_ch1_date")
        last_ch2_date = self.get_state("last_ch2_date")

        # Chapter 1: prediction pipeline — run once per day, 06:00–20:00
        ch1_window    = 6 <= hour < 20
        ch1_done_today = last_ch1_date == today
        run_ch1 = ch1_window and not ch1_done_today

        # Chapter 2: automated booking — run once per day, 08:00–22:00
        ch2_window    = 8 <= hour < 22
        ch2_done_today = last_ch2_date == today
        run_ch2 = ch2_window and not ch2_done_today

        plan = {
            "run_prologue": True,
            "run_chapter1": run_ch1,
            "run_chapter2": run_ch2,
            "hour": hour,
            "ch1_done_today": ch1_done_today,
            "ch2_done_today": ch2_done_today,
        }

        reasons = []
        if not run_ch1:
            if ch1_done_today:
                reasons.append("Ch1 already ran today")
            if not ch1_window:
                reasons.append(f"Ch1 outside window (hour={hour}, window=06-20)")
        if not run_ch2:
            if ch2_done_today:
                reasons.append("Ch2 already ran today")
            if not ch2_window:
                reasons.append(f"Ch2 outside window (hour={hour}, window=08-22)")

        if reasons:
            logger.info(f"[Supervisor] Agentic plan: {plan}  Skip reasons: {reasons}")
        else:
            logger.info(f"[Supervisor] Agentic plan: {plan}")

        return plan

    async def run_cycle(self, scheduler, p) -> bool:
        """
        Executes a sequence of chapters/workers as a single autonomous cycle.

        Chapter sequencing is agentic: time-of-day and prior-run state
        determine which chapters are attempted this cycle.
        """
        from Core.System.pipeline_workers import StartupWorker, PrologueWorker, Chapter1Worker, Chapter2Worker

        self.state["status"] = "running"
        self.capture_state("global_state", self.state)

        logger.info(f"=== Starting Autonomous Cycle #{self.state['cycle_count']} (ID: {self.run_id}) ===")

        # 1. Startup/Audit — always run
        if not await self.dispatch(StartupWorker):
            return False

        # ── Agentic decision: which chapters to run? ──────────────────────────
        plan = self._chapter_plan()
        today = now_ng().strftime("%Y-%m-%d")

        # 2. Data Readiness Gates — always run (cheap; guards Ch1/Ch2)
        if not await self.dispatch(PrologueWorker):
            logger.warning("[Supervisor] Prologue failed — skipping Chapter 1 & 2")
            self.state["status"] = "prologue_failed"
            self.state["last_run"] = now_ng().isoformat()
            self.capture_state("global_state", self.state)
            return False

        # 3. Prediction Pipeline
        ch1_success = False
        if plan["run_chapter1"]:
            ch1_success = await self.dispatch(Chapter1Worker, scheduler, playwright_instance=p)
            if ch1_success:
                self.capture_state("last_ch1_date", today)
                logger.info("[Supervisor] Chapter 1 complete — date checkpointed.")
            else:
                logger.warning("[Supervisor] Chapter 1 returned False.")
        else:
            logger.info("[Supervisor] Chapter 1 skipped (agentic plan).")

        # 4. Betting Automation
        # Gate: Ch2 runs if plan allows AND either Ch1 ran this cycle (fresh codes)
        # or codes already exist from a prior successful Ch1 today.
        ch1_ran_today = ch1_success or plan["ch1_done_today"]
        if plan["run_chapter2"] and ch1_ran_today:
            ch2_ok = await self.dispatch(Chapter2Worker, playwright_instance=p)
            if ch2_ok:
                self.capture_state("last_ch2_date", today)
                logger.info("[Supervisor] Chapter 2 complete — date checkpointed.")
        elif plan["run_chapter2"] and not ch1_ran_today:
            logger.warning("[Supervisor] Skipping Chapter 2 — no Ch1 data for today yet.")
        else:
            logger.info("[Supervisor] Chapter 2 skipped (agentic plan).")

        self.state["status"] = "completed"
        self.state["last_run"] = now_ng().isoformat()
        self.capture_state("global_state", self.state)
        logger.info(f"=== Cycle #{self.state['cycle_count']} Complete ===")
        return True

    async def run(self):
        """
        Main infinite loop orchestrator. 
        Manages browser lifecycle, scheduling, and autonomous heartbeats.
        """
        import os
        from playwright.async_api import async_playwright
        from Core.System.scheduler import TaskScheduler
        import tempfile
        import shutil
        from Leo import live_score_streamer, execute_scheduled_tasks, log_state, log_audit_event
        
        cycle_hours = int(os.getenv('LEO_CYCLE_WAIT_HOURS', '6'))
        scheduler = TaskScheduler()
        scheduler.schedule_weekly_enrichment()

        try:
            async with async_playwright() as p:
                while True:
                    self.state["cycle_count"] += 1
                    cycle_num = self.state["cycle_count"]
                    log_state(chapter="Cycle Start", action=f"Initiating Cycle #{cycle_num}")
                    log_audit_event("CYCLE_START", f"Cycle #{cycle_num} initiated.")

                    # --- Live Streamer Watchdog ---
                    # STREAMER WATCHDOG: Check liveness and respawn if needed
                    # Heartbeat check (using Modules.Flashscore.fs_live_streamer util)
                    from Modules.Flashscore.fs_live_streamer import is_streamer_alive
                    if not is_streamer_alive():
                        now_ts = time.time()
                        if now_ts - self.last_streamer_spawn < 60:
                            logger.warning(f"[Supervisor] Streamer is down but in 60s cooldown ({(60 - (now_ts - self.last_streamer_spawn)):.0f}s left).")
                        else:
                            logger.info("[Supervisor] Streamer dead/stale. Respawning...")
                            try:
                                proc = subprocess.Popen(
                                    [sys.executable, "-m", "Modules.Flashscore.fs_live_streamer"],
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE,
                                    stdin=subprocess.DEVNULL,
                                    start_new_session=True,
                                    text=True
                                )
                                self.last_streamer_spawn = time.time()
                                
                                # Startup check: wait 5s to see if it crashes immediately
                                await asyncio.sleep(5)
                                if proc.poll() is not None:
                                    _, stderr = proc.communicate()
                                    logger.error(f"[Supervisor] STREAMER_STARTUP_FAILURE: Streamer died within 5s. Stderr: {stderr}")
                                else:
                                    logger.info(f"[Supervisor] Streamer respawned successfully (PID: {proc.pid}).")
                            except Exception as e:
                                logger.error(f"[Supervisor] Failed to spawn streamer: {e}")

                    try:
                        # Maintenance
                        await execute_scheduled_tasks(scheduler, p)
                        
                        # Execute Cycle
                        await self.run_cycle(scheduler, p)

                    except Exception as e:
                        logger.error(f"[Supervisor] Unhandled cycle error: {e}")
                        self.state["error_log"].append(f"{now_ng().isoformat()}: {e}")
                        await asyncio.sleep(60)

                    # Post-cycle cleanup & sleep
                    scheduler.schedule_weekly_enrichment()
                    self.capture_state("global_state", self.state)

                    next_wake = scheduler.next_wake_time()
                    if next_wake:
                        sleep_secs = max(60, (next_wake - now_ng()).total_seconds())
                        if sleep_secs > cycle_hours * 3600:
                            sleep_secs = cycle_hours * 3600
                    else:
                        sleep_secs = cycle_hours * 3600

                    logger.info(f"[Supervisor] Cycle #{cycle_num} done. Sleeping {sleep_secs/3600:.1f}h...")
                    await asyncio.sleep(sleep_secs)

        except KeyboardInterrupt:
            logger.info("[Supervisor] Manual shutdown. Saving state...")
            self.state["status"] = "shutdown"
            self.capture_state("global_state", self.state)
            raise
