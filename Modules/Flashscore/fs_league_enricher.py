# fs_league_enricher.py: Flashscore league enrichment — top-level orchestrator.
# Part of LeoBook Modules — Flashscore
# Entry point: main() — called by Leo.py as run_league_enricher
# Tab extraction and single-league logic: fs_league_tab.py

import asyncio
import argparse
import logging
import os
import sys
from typing import Dict, Optional, Set

from playwright.async_api import async_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from Data.Access.league_db import (
    init_db, get_unprocessed_leagues, get_stale_leagues,
    get_all_leagues, get_active_leagues,
)
from Data.Access.gap_scanner import GapScanner
from Scripts.db_purge import run_purge

from Modules.Flashscore.fs_league_images import executor
from Modules.Flashscore.fs_league_extractor import (
    seed_leagues_from_json, verify_league_gaps_closed,
)
from Modules.Flashscore.fs_league_tab import (
    enrich_single_league, extract_tab,  # re-exported for callers
)

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEAGUES_JSON = os.path.join(BASE_DIR, "Data", "Store", "leagues.json")
CRESTS_DIR = os.path.join("Data", "Store", "crests")
LEAGUE_CRESTS_DIR = os.path.join(CRESTS_DIR, "leagues")
TEAM_CRESTS_DIR  = os.path.join(CRESTS_DIR, "teams")

MAX_CONCURRENCY = 5


async def main(
    limit: Optional[int] = None,
    offset: int = 0,
    reset: bool = False,
    reload: bool = False,
    num_seasons: int = 0,
    all_seasons: bool = False,
    weekly: bool = False,
    target_season: Optional[int] = None,
    refresh: bool = False,
    scan_only: bool = False,
    min_severity: str = "important",
    drain_queue: bool = False,
    purge: bool = False,
) -> None:
    print("\n" + "=" * 60)
    print("  FLASHSCORE LEAGUE ENRICHMENT -> SQLite")
    print("=" * 60)

    conn = init_db()
    print(f"  [DB] {os.path.abspath(conn.execute('PRAGMA database_list').fetchone()[2])}")

    if purge:
        print("  [Purge] Running orphan data purge pass...")
        run_purge()

    if reset:
        conn.execute("UPDATE leagues SET processed = 0")
        conn.commit()
        print("  [DB] Reset all leagues to unprocessed")
        
        # Clear batch checkpoint on reset
        checkpoint_path = os.path.join(BASE_DIR, "Data", "Logs", "batch_checkpoint.json")
        if os.path.exists(checkpoint_path):
            try:
                os.remove(checkpoint_path)
                print(f"  [Reset] Cleared checkpoint: {checkpoint_path}")
            except Exception as e:
                print(f"  [Reset] Warning: Could not clear checkpoint: {e}")

    seed_leagues_from_json(conn, LEAGUES_JSON)

    scan_mode = ""
    gap_targets_by_id: Dict[str, Dict] = {}

    if reset:
        leagues   = get_unprocessed_leagues(conn)
        scan_mode = "FULL RESET"

    elif reload:
        leagues   = get_all_leagues(conn)
        scan_mode = "FULL RELOAD (all leagues)"

    elif refresh or weekly:
        leagues   = get_active_leagues(conn, days=7)
        scan_mode = f"ACTIVE REFRESH (fixtures ±7 days, {len(leagues) if 'leagues' in dir() else '?'} leagues)"

    else:
        scan_mode = "COLUMN GAP SCAN"
        print(f"\n  [GapScan] Scanning leagues, teams, schedules for missing data...")
        report = GapScanner(conn).scan()
        report.print_report()

        if scan_only:
            print("  [scan-only] Exiting without enrichment.")
            conn.close()
            return

        if not report.has_gaps:
            print("  [Done] All columns fully enriched. Nothing to do.")
            conn.close()
            return

        raw_targets = report.leagues_needing_enrichment(min_severity=min_severity)
        gap_targets_by_id = {t["league_id"]: t for t in raw_targets}

        leagues = [{
            "league_id":    t["league_id"], "name": t["name"],
            "url":          t["url"],       "country_code": t["country_code"],
            "continent":    t["continent"],
        } for t in raw_targets]

        if num_seasons > 0 or target_season is not None or all_seasons:
            try:
                from Data.Access.league_db import get_leagues_missing_seasons
                min_needed = num_seasons if num_seasons > 0 else 2
                if target_season is not None:
                    min_needed = max(min_needed, target_season + 1)
                history_leagues = get_leagues_missing_seasons(conn, min_seasons=min_needed)
                existing_ids = {lg["league_id"] for lg in leagues}
                added = sum(1 for lg in history_leagues
                            if lg["league_id"] not in existing_ids
                            and not leagues.append(lg))
                if added:
                    print(f"  [Scan] +{added} leagues missing {min_needed}+ historical seasons")
            except Exception:
                pass

    if offset > 0:
        leagues = leagues[offset:]
    if limit:
        leagues = leagues[:limit]

    if not leagues:
        print(f"\n  [Done] No leagues need enrichment ({scan_mode}).")
        conn.close()
        return

    total = len(leagues)
    sync_interval    = max(1, total // 20)
    sync_checkpoints = set(range(sync_interval, total + 1, sync_interval))

    print(f"\n  [Enrich] {total} leagues ({scan_mode}, concurrency={MAX_CONCURRENCY})")
    print(f"  [Sync]   Checkpoints at: {sorted(sync_checkpoints)}")

    os.makedirs(os.path.join(BASE_DIR, LEAGUE_CRESTS_DIR), exist_ok=True)
    os.makedirs(os.path.join(BASE_DIR, TEAM_CRESTS_DIR), exist_ok=True)

    sync_mgr = None
    try:
        from Data.Access.sync_manager import SyncManager
        sync_mgr = SyncManager(conn=conn)
    except Exception:
        pass

    completed_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            timezone_id="Africa/Lagos",
        )

        sem           = asyncio.Semaphore(MAX_CONCURRENCY)
        db_lock       = asyncio.Lock()  # Serialize DB transactions (shared conn)
        crash_counter = 0
        failed_leagues: list = []
        LEAGUE_MAX_RETRIES = 2

        async def _worker(league: Dict, idx: int) -> None:
            nonlocal completed_count, ctx, browser, crash_counter
            async with sem:
                league_id   = league["league_id"]
                league_name = league.get("name", league_id)
                gap_target  = gap_targets_by_id.get(league_id, {})
                before_gaps = gap_target.get("gap_summary", {}).get("total", 0)
                s_with_gaps         = gap_target.get("seasons_with_gaps") or []
                g_columns: Set[str] = set(gap_target.get("gap_summary", {}).get("by_column", {}).keys())
                needs_full          = gap_target.get("needs_full_re_enrich", False)

                last_error = None
                for attempt in range(1, LEAGUE_MAX_RETRIES + 1):
                    try:
                        # ── Transaction BEGIN ─────────────────────────
                        async with db_lock:
                            conn.execute("BEGIN")

                            await enrich_single_league(
                                context=ctx, league=league, conn=conn,
                                idx=idx, total=total, num_seasons=num_seasons,
                                all_seasons=all_seasons, target_season=target_season,
                                seasons_with_gaps=s_with_gaps or None,
                                gap_columns=g_columns or None,
                                needs_full_re_enrich=needs_full,
                            )

                            # ── Transaction COMMIT ────────────────────────
                            conn.commit()
                        crash_counter = 0
                        last_error = None

                        if before_gaps > 0:
                            verify_league_gaps_closed(conn, league_id, before_gaps, idx, total)
                        break  # Success — exit retry loop

                    except Exception as e:
                        # ── Transaction ROLLBACK ──────────────────────
                        try:
                            conn.rollback()
                        except Exception:
                            pass

                        last_error = e
                        err = str(e).lower()

                        # Browser crash recovery
                        if "crashed" in err or "target closed" in err:
                            crash_counter += 1
                            if crash_counter >= 2:
                                print(f"\n  [Recovery] Browser crashed {crash_counter}x — recycling...")
                                try: await ctx.close()
                                except Exception: pass
                                try: await browser.close()
                                except Exception: pass
                                browser = await p.chromium.launch(headless=True)
                                ctx = await browser.new_context(
                                    user_agent=(
                                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                                    ),
                                    viewport={"width": 1920, "height": 1080},
                                    timezone_id="Africa/Lagos",
                                )
                                crash_counter = 0
                                print("  [Recovery] Fresh browser ready.")

                        if attempt < LEAGUE_MAX_RETRIES:
                            print(f"  [{idx}/{total}] [RETRY {attempt}/{LEAGUE_MAX_RETRIES}] "
                                  f"{league_name}: {e}")
                            await asyncio.sleep(3)
                        else:
                            print(f"\n  [{idx}/{total}] [FAILED] {league_name} "
                                  f"after {LEAGUE_MAX_RETRIES} attempts: {e}")
                            failed_leagues.append({
                                "league_id": league_id,
                                "name": league_name,
                                "error": str(e),
                            })

                completed_count += 1
                if completed_count in sync_checkpoints:
                    pct = int((completed_count / total) * 100)
                    print(f"\n  [Checkpoint] {pct}% ({completed_count}/{total})")
                    try:
                        from Data.Access.db_helpers import propagate_crest_urls, fill_all_country_codes
                        propagate_crest_urls()
                        fill_all_country_codes(conn)
                    except Exception as e:
                        print(f"  [Crests] Propagation failed: {e}")
                    if sync_mgr and sync_mgr.supabase:
                        for sync_attempt in range(3):
                            try:
                                from Data.Access.sync_manager import TABLE_CONFIG
                                for tkey in ("schedules", "teams", "leagues"):
                                    cfg = TABLE_CONFIG.get(tkey)
                                    if cfg:
                                        await sync_mgr._sync_table(tkey, cfg)
                                print(f"  [Sync] Done at {pct}%")
                                break
                            except Exception as e:
                                if 'database is locked' in str(e).lower() and sync_attempt < 2:
                                    print(f"  [Sync] Locked — retry {sync_attempt+1}/3 in 3s...")
                                    await asyncio.sleep(3)
                                else:
                                    print(f"  [Sync] Failed: {e}")

        await asyncio.gather(*[_worker(lg, i) for i, lg in enumerate(leagues, 1)])
        await ctx.close()
        await browser.close()

    # ── Failed leagues summary ────────────────────────────────────────────
    if failed_leagues:
        print(f"\n{'='*60}")
        print(f"  [CONTRACT] {len(failed_leagues)} league(s) FAILED — no data persisted:")
        for fl in failed_leagues:
            print(f"    ✗ {fl['name']} ({fl['league_id']}): {fl['error'][:120]}")
        print(f"{'='*60}")
    else:
        print(f"\n  [CONTRACT] All {total} league(s) passed — data committed.")

    # ── Final passes ──────────────────────────────────────────────────────
    try:
        from Core.System.gap_resolver import GapResolver
        GapResolver.resolve_immediate()
    except Exception as e:
        print(f"  [GapResolver] {e}")

    try:
        from Data.Access.season_completeness import SeasonCompletenessTracker
        SeasonCompletenessTracker.bulk_compute_all()
    except Exception as e:
        print(f"  [Completeness] {e}")

    try:
        from Data.Access.db_helpers import propagate_crest_urls, fill_all_country_codes
        propagate_crest_urls()
        print("  [Crests] Final URL propagation done")
        total_cc = fill_all_country_codes(conn)
        if total_cc:
            print(f"  [CC] Final country_code fill: {total_cc} rows resolved")
    except Exception as e:
        print(f"  [Crests] Final propagation failed: {e}")

    if sync_mgr and sync_mgr.supabase:
        try:
            from Data.Access.sync_manager import TABLE_CONFIG
            print("  [Sync] Final push to Supabase...")
            for tkey in ("schedules", "teams", "leagues"):
                cfg = TABLE_CONFIG.get(tkey)
                if cfg:
                    await sync_mgr._sync_table(tkey, cfg)
            print("  [Sync] Final sync complete")
        except Exception as e:
            print(f"  [Sync] Final sync failed: {e}")

    print(f"\n  [GapScan] Post-enrichment verification...")
    final_report = GapScanner(conn).scan()
    final_report.print_report()
    if final_report.has_gaps:
        print(f"  [!] {final_report.total_gaps} gaps remain "
              f"({final_report.critical_gap_count} critical). Re-run to continue.")

    league_count  = conn.execute("SELECT COUNT(*) FROM leagues").fetchone()[0]
    fixture_count = conn.execute("SELECT COUNT(*) FROM schedules").fetchone()[0]
    team_count    = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    processed     = conn.execute("SELECT COUNT(*) FROM leagues WHERE processed=1").fetchone()[0]

    print(f"\n{'='*60}\n  ENRICHMENT COMPLETE\n{'='*60}")
    print(f"  Leagues:  {league_count} total, {processed} processed")
    print(f"  Fixtures: {fixture_count}\n  Teams:    {team_count}")
    print(f"  Remaining gaps: {final_report.total_gaps}\n{'='*60}\n")

    conn.close()
    executor.shutdown(wait=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Enrich Flashscore leagues -> SQLite (column-level gap scan by default)"
    )
    parser.add_argument("--limit",       type=str, default=None, metavar="N or START-END")
    parser.add_argument("--reset",       action="store_true")
    parser.add_argument("--reload",      action="store_true",
                        help="Re-enrich ALL leagues regardless of gap scan")
    parser.add_argument("--refresh",     action="store_true",
                        help="Re-enrich leagues with fixtures in the last/next 7 days")
    parser.add_argument("--seasons",     type=int, default=0, metavar="N")
    parser.add_argument("--season",      type=int, default=None, metavar="N")
    parser.add_argument("--all-seasons", action="store_true")
    parser.add_argument("--scan-only",   action="store_true")
    parser.add_argument("--min-severity", default="important",
                        choices=["critical", "important", "enrichable"])
    parser.add_argument("--drain-queue",  action="store_true")
    parser.add_argument("--purge",        action="store_true",
                        help="Purge orphan leagues before starting enrichment")
    args = parser.parse_args()

    limit_count = None
    offset      = 0
    if args.limit:
        if "-" in args.limit:
            start, end  = args.limit.split("-", 1)
            offset      = int(start.strip()) - 1
            limit_count = int(end.strip()) - offset
        else:
            limit_count = int(args.limit)

    asyncio.run(main(
        limit=limit_count, offset=offset, reset=args.reset,
        reload=args.reload,
        num_seasons=args.seasons, all_seasons=args.all_seasons,
        target_season=args.season, refresh=args.refresh,
        scan_only=args.scan_only, min_severity=args.min_severity,
        drain_queue=args.drain_queue, purge=args.purge,
    ))
