# pipeline.py: Leo page functions — the async operations called by Leo.py dispatch.
# Part of LeoBook Core — System
# Extracted from Leo.py (P11). Each function is a self-contained async chapter/page.
# Imported by: Leo.py

from typing import Optional
from Core.System.lifecycle import log_state, state
from Core.System.scheduler import TaskScheduler, TASK_WEEKLY_ENRICHMENT, TASK_DAY_BEFORE_PREDICT, TASK_RL_TRAINING
from Core.System.data_readiness import check_leagues_ready
from Core.System.prologue_extraction import (
    run_flashscore_prologue_refresh,
    run_football_com_prologue_phase0,
)
from Core.Intelligence.aigo_suite import AIGOSuite
from Data.Access.db_helpers import init_csvs, log_audit_event
from Data.Access.sync_manager import SyncManager, run_full_sync
from Data.Access.league_db import init_db
from Modules.Flashscore.fs_live_streamer import live_score_streamer
from Modules.FootballCom.fb_manager import run_odds_harvesting, run_automated_booking
from Modules.FootballCom.fb_basketball_booker import run_basketball_odds_harvesting
from Scripts.recommend_bets import get_recommendations
from Core.Intelligence.unified_prediction_pipeline import run_all_predictions, patch_standings_cache
# Individual pipelines kept for backward-compat imports from other modules
from Core.Intelligence.prediction_pipeline import run_predictions
from Core.Intelligence.basketball_prediction_pipeline import run_basketball_predictions
from Modules.Flashscore.fs_league_enricher import main as run_league_enricher
from Data.Access.asset_manager import sync_team_assets, sync_league_assets, sync_region_flags


# ============================================================
# STARTUP
# ============================================================

async def run_startup_sync():
    """Startup: Ensure local DB exists, then push-only sync.
    Auto-bootstraps from Supabase if local DB is missing or empty."""
    log_state(chapter="Startup", action="DB Initialization & Push-Only Sync")
    try:
        print("\n" + "=" * 60)
        print("  STARTUP: Database Initialization & Push-Only Sync")
        print("=" * 60)

        init_csvs()
        conn = init_db()

        try:
            sched_count = conn.execute("SELECT COUNT(*) FROM schedules").fetchone()[0]
        except Exception:
            sched_count = 0

        if sched_count == 0:
            print("     [!] Local DB empty - will bootstrap from Supabase automatically")

        sync_mgr = SyncManager()
        await sync_mgr.sync_on_startup()

        log_audit_event("STARTUP", "DB initialized and push-only sync completed.", status="success")
        print("  [Startup] Complete")
        return True
    except Exception as e:
        print(f"  [Error] Startup sync failed: {e}")
        log_audit_event("STARTUP", f"Failed: {e}", status="failed")
        return False


# ============================================================
# PROLOGUE — Data Readiness Gates
# ============================================================

async def run_prologue_p1(args=None):
    """Prologue P1: Verify leagues >= 90% of leagues.json AND teams >= 5 per league."""
    log_state(chapter="Prologue P1", action="Data Readiness: Leagues & Teams")
    try:
        print("\n" + "=" * 60)
        print("  PROLOGUE P1: Data Readiness - Leagues & Teams")
        print("=" * 60)
 
        ready, stats = check_leagues_ready()
        if not ready:
            print(
                "  [Prologue P1] Gates not satisfied. Run explicit enrichment, e.g.\n"
                "      python Leo.py --enrich-leagues [--refresh] [--seasons N]\n"
                "  Auto-remediation is disabled (All-or-Nothing — operator-driven enrichment only)."
            )
            opt_in = bool(
                args is not None and getattr(args, "prologue_p1_enrich", False)
            )
            if opt_in:
                print(
                    "  [Prologue P1] --prologue-p1-enrich: running one active-window enrichment pass..."
                )
                await run_league_enricher(
                    refresh=True,
                    active_window_days=14,
                    priority_fb_mapped_first=True,
                )
                ready, stats = check_leagues_ready()
                if ready:
                    print("  [Prologue P1] Readiness gates satisfied after enrichment.")
                else:
                    print(
                        "  [Prologue P1] Gates still not satisfied after enrichment. "
                        "Run a broader pass: python Leo.py --enrich-leagues ..."
                    )

        log_audit_event("PROLOGUE_P1",
                        f"Leagues: {stats['actual_leagues']}/{stats['expected_leagues']}, "
                        f"Teams: {stats['team_count']}",
                        status="success" if ready else "partial_failure")
    except Exception as e:
        print(f"  [Error] Prologue P1 failed: {e}")
        log_audit_event("PROLOGUE_P1", f"Failed: {e}", status="failed")


async def run_prologue_p2(args=None):
    """Prologue P2: Flashscore extraction — active window refresh, fb-mapped leagues first (gated on P1)."""
    log_state(chapter="Prologue P2", action="Flashscore active-window extraction")
    try:
        print("\n" + "=" * 60)
        print("  PROLOGUE P2: Flashscore — Active Window Extraction")
        print("=" * 60)

        ready, stats = check_leagues_ready()
        if not ready:
            print(
                "  [Prologue P2] BLOCKED until Prologue P1 passes. "
                "Fix league/team readiness, then re-run Prologue.\n"
                "  Hint: python Leo.py --enrich-leagues"
            )
            log_audit_event(
                "PROLOGUE_P2",
                f"Blocked: P1 not ready ({stats.get('actual_leagues', '?')} leagues)",
                status="blocked",
            )
            return

        await run_flashscore_prologue_refresh(
            active_window_days=14,
            priority_fb_mapped_first=True,
        )
        log_audit_event("PROLOGUE_P2", "Flashscore prologue refresh completed.", status="success")
    except Exception as e:
        print(f"  [Error] Prologue P2 failed: {e}")
        log_audit_event("PROLOGUE_P2", f"Failed: {e}", status="failed")


async def run_prologue_p3(args=None):
    """Prologue P3: football.com Phase 0 — fixture/calendar sync for mapped leagues (gated on P1)."""
    log_state(chapter="Prologue P3", action="football.com Phase 0 calendar sync")
    try:
        print("\n" + "=" * 60)
        print("  PROLOGUE P3: football.com — Phase 0 Calendar / Fixture Discovery")
        print("=" * 60)

        ready, stats = check_leagues_ready()
        if not ready:
            print(
                "  [Prologue P3] BLOCKED until Prologue P1 passes. "
                "Fix league/team readiness first.\n"
                "  Hint: python Leo.py --enrich-leagues"
            )
            log_audit_event(
                "PROLOGUE_P3",
                f"Blocked: P1 not ready ({stats.get('actual_leagues', '?')} leagues)",
                status="blocked",
            )
            return

        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            await run_football_com_prologue_phase0(p)

        log_audit_event("PROLOGUE_P3", "football.com Phase 0 sync completed.", status="success")
    except Exception as e:
        print(f"  [Error] Prologue P3 failed: {e}")
        log_audit_event("PROLOGUE_P3", f"Failed: {e}", status="failed")


# ============================================================
# CHAPTER 1 — Prediction Pipeline
# ============================================================

@AIGOSuite.aigo_retry(max_retries=2, delay=3.0)
async def run_chapter_1_p1(p):
    """Chapter 1 Page 1: URL Resolution & Odds Harvesting."""
    log_state(chapter="Ch1 P1", action="URL Resolution & Odds Harvesting")
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 1 PAGE 1: URL Resolution & Odds Harvesting")
        print("=" * 60)

        await run_odds_harvesting(p)
        try:
            await run_basketball_odds_harvesting(p)
        except Exception as bb_e:
            print(f"  [Ch1 P1] Basketball odds harvesting failed (non-fatal): {bb_e}")

        log_audit_event(
            "CH1_P1",
            "Football + basketball odds harvesting completed.",
            status="success",
        )
        return True
    except Exception as e:
        print(f"  [Error] Chapter 1 Page 1 failed: {e}")
        log_audit_event("CH1_P1", f"Failed: {e}", status="failed")
        return False


@AIGOSuite.aigo_retry(max_retries=2, delay=3.0)
async def run_chapter_1_p2(p=None, scheduler: TaskScheduler = None,
                           refresh: bool = False, target_dates: Optional[list] = None):
    """Chapter 1 Page 2: Predictions (Rule Engine + RL Ensemble) — all sports."""
    log_state(chapter="Ch1 P2", action="Predictions")
    conn = init_db()
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 1 PAGE 2: Predictions (Pure DB — Football + Basketball)")
        print("=" * 60)

        # Activate standings cache for this run (P3 optimisation)
        patch_standings_cache()

        # --- START TRANSACTION: All-or-Nothing for Page 2 ---
        conn.execute("BEGIN")

        # Unified dispatcher: runs football then basketball in one call
        all_results = await run_all_predictions(
            conn=conn,
            sports=["football", "basketball"],
        )
        fb_count = len(all_results.get("football", []))
        bb_count = len(all_results.get("basketball", []))
        total    = fb_count + bb_count

        # --- COMMIT TRANSACTION ---
        conn.execute("COMMIT")
        print(f"    ✓ [Ch1 P2] Atomic commit: {fb_count} football + {bb_count} basketball predictions.")
        log_audit_event(
            "CH1_P2",
            f"Predictions completed: {total} total ({fb_count} football, {bb_count} basketball).",
            status="success",
        )
    except Exception as e:
        # --- ROLLBACK TRANSACTION ---
        conn.execute("ROLLBACK")
        print(f"    ⚠ [Ch1 P2] PAGE FAILED -> ROLLED BACK. Error: {e}")
        log_audit_event("CH1_P2", f"Failed: {e}", status="failed")


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0)
async def run_chapter_1_p3(p=None):
    """Chapter 1 Page 3: Recommendations, Booking Code Harvest & Final Sync."""
    log_state(chapter="Ch1 P3", action="Recommendations, Booking Harvest & Final Sync")
    conn = init_db()
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 1 PAGE 3: Recommendations & Booking Code Harvest")
        print("=" * 60)

        # --- START TRANSACTION: All-or-Nothing for Page 3 ---
        conn.execute("BEGIN")
        
        try:
            # 1. Generate recommendations — sorted by score DESC per date
            result = await get_recommendations(save_to_file=True)
            recommendations = result.get("recommendations", []) if result else []

            # 2. Booking code harvest — top 20% per date, no-login session
            if recommendations and p is not None:
                from Modules.FootballCom.booker.booking_harvester import (
                    harvest_booking_codes_for_recommendations,
                )
                codes_harvested = await harvest_booking_codes_for_recommendations(
                    page=p,
                    recommendations=recommendations,
                    conn=conn,
                )
                print(f"    [Ch1 P3] Booking codes harvested: {codes_harvested}")
            else:
                if p is None:
                    print("  [Ch1 P3] No browser page available — skipping booking harvest.")
                if not recommendations:
                    print("  [Ch1 P3] No recommendations — skipping booking harvest.")

            # --- COMMIT TRANSACTION ---
            conn.execute("COMMIT")
            print("    ✓ [Ch1 P3] Atomic commit successful.")
            log_audit_event("CH1_P3", "Recommendations and booking harvest completed.", status="success")
            
        except Exception as e:
            # --- ROLLBACK TRANSACTION ---
            conn.execute("ROLLBACK")
            print(f"    ⚠ [Ch1 P3] PAGE FAILED -> ROLLED BACK. Error: {e}")
            log_audit_event("CH1_P3", f"Internal Failure: {e}", status="failed")
            raise  # Re-raise for retry decorator

        # 3. Final sync (Outside transaction to avoid long locks during network IO)
        sync_ok = await run_full_sync(session_name="Chapter 1 Final")
        if not sync_ok:
            print("  [AIGO] Sync parity issues detected. Logged for review.")
            log_audit_event("CH1_P3_SYNC", "Sync parity issues detected.", status="partial_failure")

    except Exception as e:
        print(f"  [Error] Chapter 1 Page 3 failed: {e}")
        log_audit_event("CH1_P3", f"Critical Failure: {e}", status="failed")




# ============================================================
# CHAPTER 2 — Betting Automation
# ============================================================

@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_chapter_2_p1(p):
    """Chapter 2 Page 1: Automated Booking on Football.com."""
    log_state(chapter="Ch2 P1", action="Automated Booking (Football.com)")
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 2 PAGE 1: Automated Booking")
        print("=" * 60)
        await run_automated_booking(p)
        await run_full_sync(session_name="Ch2 P1 Booking")
        log_audit_event("CH2_P1", "Automated booking phase completed.", status="success")
    except Exception as e:
        print(f"  [Error] Chapter 2 Page 1 failed: {e}")
        log_audit_event("CH2_P1", f"Failed: {e}", status="failed")


@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_chapter_2_p2(p):
    """Chapter 2 Page 2: Funds Balance & Withdrawal Check."""
    log_state(chapter="Ch2 P2", action="Funds & Withdrawal Check")
    try:
        print("\n" + "=" * 60)
        print("  CHAPTER 2 PAGE 2: Funds & Withdrawal Check")
        print("=" * 60)
        from Core.System.withdrawal_checker import (
            check_triggers, propose_withdrawal, calculate_proposed_amount,
            get_latest_win, check_withdrawal_approval, execute_withdrawal
        )
        async with await p.chromium.launch(headless=True) as check_browser:
            from Modules.FootballCom.navigator import extract_balance
            check_page = await check_browser.new_page()
            state["current_balance"] = await extract_balance(check_page)

        if await check_triggers():
            proposed_amount = calculate_proposed_amount(state["current_balance"], get_latest_win())
            await propose_withdrawal(proposed_amount)

        if await check_withdrawal_approval():
            from Core.System.withdrawal_checker import pending_withdrawal
            await execute_withdrawal(
                pending_withdrawal["amount"],
                user_id=state.get("user_id") or None,
            )

        log_audit_event("CH2_P2",
                        f"Withdrawal check completed. Balance: {state.get('current_balance', 'N/A')}",
                        status="success")
        try:
            from Data.Access.user_supabase_sync import push_fb_balance_snapshot

            uid = state.get("user_id") or ""
            bal = state.get("current_balance")
            if uid and bal is not None:
                push_fb_balance_snapshot(uid, float(bal), source="ch2_p2")
        except Exception:
            pass
        await run_full_sync(session_name="Ch2 P2 Withdrawal")
    except Exception as e:
        print(f"  [Warning] Chapter 2 Page 2 failed: {e}")
        log_audit_event("CH2_P2", f"Failed: {e}", status="failed")


# ============================================================
# SCHEDULED TASK EXECUTOR
# ============================================================

async def execute_scheduled_tasks(scheduler: TaskScheduler, p=None):
    """Execute all pending scheduled tasks."""
    pending = scheduler.get_pending_tasks()
    if not pending:
        return

    print(f"\n  [Scheduler] Executing {len(pending)} pending task(s)...")

    for task in pending:
        try:
            if task.task_type == TASK_WEEKLY_ENRICHMENT:
                print(f"  [Scheduler] Running weekly enrichment (task: {task.task_id})")
                await run_league_enricher(weekly=True, active_window_days=14)
                scheduler.complete_task(task.task_id)

            elif task.task_type == TASK_DAY_BEFORE_PREDICT:
                fid = task.params.get('fixture_id')
                print(f"  [Scheduler] Day-before prediction for fixture {fid}")
                await run_predictions(scheduler=scheduler)
                scheduler.complete_task(task.task_id)

            elif task.task_type == TASK_RL_TRAINING:
                print(f"  [Scheduler] Running RL training (task: {task.task_id})")
                from Core.Intelligence.rl.trainer import RLTrainer

                trainer = RLTrainer()
                trainer.train_from_fixtures()
                scheduler.complete_task(task.task_id)

        except Exception as e:
            print(f"  [Scheduler] Task {task.task_id} failed: {e}")
            scheduler.complete_task(task.task_id, status="failed")

    scheduler.cleanup_old(days=7)


# ============================================================
# DISPATCH — Routes CLI args to the appropriate functions
# ============================================================

async def dispatch(args):
    """Route CLI arguments to the correct execution path."""
    import os, sys
    from playwright.async_api import async_playwright

    # ── Single-instance guard for chapter runs ────────────────────────────────
    # Prevents two simultaneous `--chapter 1` processes from racing on SQLite.
    # The main Leo.py supervisor loop has its own lock; this guard covers
    # granular invocations (python Leo.py --chapter 1 --page 1).
    LOCK_FILE = "leo_chapter.lock"
    if args.chapter is not None:
        if os.path.exists(LOCK_FILE):
            try:
                with open(LOCK_FILE) as _lf:
                    old_pid = int(_lf.read().strip())
                import psutil
                if psutil.pid_exists(old_pid):
                    print(
                        f"  [LOCK] Another chapter run is already active (PID {old_pid}). "
                        f"Aborting to prevent SQLite contention. "
                        f"Kill that process or delete '{LOCK_FILE}' to proceed."
                    )
                    sys.exit(1)
            except Exception:
                pass  # stale lock — proceed
        with open(LOCK_FILE, "w") as _lf:
            _lf.write(str(os.getpid()))

    init_csvs()

    try:
        await _dispatch_inner(args)
    finally:
        if args.chapter is not None and os.path.exists(LOCK_FILE):
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass


async def _dispatch_inner(args):
    """Inner dispatch — runs after lock is acquired."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        if args.prologue:
            if args.page == 1:
                await run_prologue_p1(args)
            elif args.page == 2:
                await run_prologue_p2()
            elif args.page == 3:
                await run_prologue_p3()
            else:
                await run_prologue_p1(args)
                await run_prologue_p2()
                await run_prologue_p3()
            return

        if args.chapter == 1:
            if args.page == 1:
                await run_chapter_1_p1(p)
            elif args.page == 2:
                await run_chapter_1_p2(p)  # ISSUE 1 FIX: removed dead refresh/target_dates params
            elif args.page == 3:
                await run_chapter_1_p3(p)  # ISSUE 4 FIX: pass p so booking harvest works standalone
            else:
                await run_chapter_1_p1(p)
                await run_chapter_1_p2(p)
                await run_chapter_1_p3(p)  # ISSUE 4 FIX: pass p for booking harvest
            return

        if args.chapter == 2:
            from Core.System.guardrails import run_all_pre_bet_checks, is_dry_run
            from Data.Access.league_db import get_connection
            conn = get_connection()
            # ISSUE 5 FIX: pass None when balance not yet fetched so balance_sanity
            # check is skipped — actual balance is checked inside run_automated_booking
            balance = state.get("current_balance") or None
            ok, reason = run_all_pre_bet_checks(conn, balance)
            if not ok:
                print(f"  [GUARDRAIL] Chapter 2 BLOCKED: {reason}")
                log_audit_event("GUARDRAIL_BLOCK", reason, status="blocked")
                return
            if args.page == 1:
                await run_chapter_2_p1(p)
            elif args.page == 2:
                await run_chapter_2_p2(p)
            else:
                await run_chapter_2_p1(p)
                await run_chapter_2_p2(p)
            return

    print("[ERROR] Unknown dispatch target.")


__all__ = [
    "run_startup_sync",
    "run_prologue_p1", "run_prologue_p2", "run_prologue_p3",
    "run_chapter_1_p1", "run_chapter_1_p2", "run_chapter_1_p3",
    "run_chapter_2_p1", "run_chapter_2_p2",
    "execute_scheduled_tasks", "dispatch",
]
