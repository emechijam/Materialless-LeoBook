# fb_basketball_booker.py: Basketball odds harvesting + booking orchestrator.
# Part of LeoBook Modules — FootballCom
# Sport: basketball
#
# Functions: run_basketball_odds_harvesting(), run_basketball_booking()
# Called by: Leo.py (Chapter 1 / Chapter 2 — basketball variant)
#
# Flow mirrors fb_manager.py but is basketball-specific:
#   Phase 0 — Discover basketball leagues via extract_basketball_leagues_fb()
#   Phase 1 — Per-match odds extraction via extract_basketball_match_odds()
#   Phase 2 — Save results to SQLite → sync to Supabase
#   Booking  — Semaphore-bounded placement using stairway stake rules

"""
Basketball Orchestrator — Football.com
Handles both the odds-harvesting pipeline (Chapter 1 equivalent for basketball)
and the automated booking pipeline (Chapter 2 equivalent for basketball).
"""

import asyncio
import os
import time
from typing import Dict, List, Optional

from playwright.async_api import Playwright

from Core.Utils.constants import (
    MAX_CONCURRENCY,
    FB_MOBILE_USER_AGENT,
    FB_MOBILE_VIEWPORT,
    ODDS_PAGE_TIMEOUT_MS,
    ODDS_PAGE_LOAD_DELAY,
    now_ng,
)
from Core.Utils.utils import log_error_state
from Core.System.lifecycle import log_state
from Core.Intelligence.aigo_suite import AIGOSuite
from .fb_session import launch_browser_with_retry
from .navigator import load_or_create_session, extract_balance, hide_overlays
from .fb_basketball_odds import (
    extract_basketball_leagues_fb,
    extract_basketball_match_odds,
)
from Data.Access.db_helpers import log_audit_event


# ── Constants ───────────────────────────────────────────────────────────────

_BB_STAIRWAY_ODDS_MIN = 1.20
_BB_STAIRWAY_ODDS_MAX = 4.00
_BB_STAIRWAY_MAX_LEGS = 4    # max accumulator legs for basketball


# ── Session helpers (mirrors fb_manager) ────────────────────────────────────

async def _create_bb_session_no_login(playwright: Playwright):
    """Lightweight unauthenticated session for odds scraping."""
    is_headless = (
        os.getenv("CODESPACES") == "true"
        or (os.name != "nt" and not os.environ.get("DISPLAY"))
    )
    browser = await playwright.chromium.launch(
        headless=is_headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
        ],
    )
    context = await browser.new_context(
        viewport=FB_MOBILE_VIEWPORT,
        user_agent=FB_MOBILE_USER_AGENT,
    )
    page = await context.new_page()
    context._browser_ref = browser
    return context, page


async def _create_bb_session(playwright: Playwright):
    """Full authenticated session for bet placement."""
    from pathlib import Path

    user_data_dir = Path("Data/Auth/ChromeData_v3").absolute()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    context = await launch_browser_with_retry(playwright, user_data_dir)
    _, page = await load_or_create_session(context)
    current_balance = await extract_balance(page)
    from Core.Utils.constants import CURRENCY_SYMBOL
    print(f"  [BB Balance] Current: {CURRENCY_SYMBOL}{current_balance:.2f}")
    return context, page, current_balance


# ── Per-match odds worker ────────────────────────────────────────────────────

async def _bb_match_odds_worker(
    sem: asyncio.Semaphore,
    context,
    match_url: str,
    site_match_id: str,
) -> Optional[Dict]:
    """
    Semaphore-bounded worker: opens a new page, extracts basketball odds,
    closes the page.  Returns the raw result dict from extract_basketball_match_odds,
    or None on failure.
    """
    async with sem:
        page = None
        try:
            page = await context.new_page()
            await page.set_viewport_size({"width": 500, "height": 640})

            result = await extract_basketball_match_odds(page, match_url)
            return result

        except Exception as e:
            print(f"  [BB Odds Worker] {site_match_id or match_url}: {e}")
            return None
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass


# ── Internal: save basketball odds to SQLite ─────────────────────────────────

def _persist_bb_result(conn, result: Dict) -> int:
    """
    Persist one basketball match result to `basketball_match_odds` table.
    The table is created if absent (graceful bootstrap).

    Returns the number of market rows inserted.
    """
    if not result or not result.get("markets"):
        return 0

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS basketball_match_odds (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            site_match_id   TEXT    NOT NULL,
            home_team       TEXT,
            away_team       TEXT,
            sport           TEXT    DEFAULT 'basketball',
            market_id       TEXT,
            market_type     TEXT,
            base_market     TEXT,
            line            TEXT,
            over_odds       REAL,
            under_odds      REAL,
            home_odds       REAL,
            away_odds       REAL,
            outcome         TEXT,
            odds_value      REAL,
            extracted_at    TEXT,
            UNIQUE(site_match_id, market_id, market_type, line, outcome)
        )
        """
    )

    inserted = 0
    for market in result["markets"]:
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO basketball_match_odds
                    (site_match_id, home_team, away_team, sport,
                     market_id, market_type, base_market, line,
                     over_odds, under_odds, home_odds, away_odds,
                     outcome, odds_value, extracted_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    result.get("site_match_id", ""),
                    result.get("home_team", ""),
                    result.get("away_team", ""),
                    "basketball",
                    market.get("market_id", ""),
                    market.get("market_type", ""),
                    market.get("base_market", ""),
                    market.get("line"),
                    market.get("over_odds"),
                    market.get("under_odds"),
                    market.get("home_odds"),
                    market.get("away_odds"),
                    market.get("outcome"),
                    market.get("odds_value"),
                    result.get("extracted_at", now_ng().isoformat()),
                ),
            )
            inserted += 1
        except Exception as e:
            print(f"  [BB Persist] Insert failed for {result.get('site_match_id')}: {e}")

    return inserted


# ── CHAPTER 1 VARIANT — Basketball Odds Harvesting ──────────────────────────

@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_basketball_odds_harvesting(playwright: Playwright) -> None:
    """
    Basketball Chapter 1 Equivalent.

    Flow:
    1. Discover all basketball leagues via extract_basketball_leagues_fb()
    2. For each match URL in each league, extract odds concurrently
       (semaphore-bounded, MAX_CONCURRENCY pages)
    3. Persist to SQLite basketball_match_odds table
    4. Sync basketball_match_odds to Supabase

    The league discovery page lists matches directly — we use the league
    schedule URL to find match links without a separate fixture DB lookup.
    """
    print("\n--- Running Basketball Odds Harvesting (football.com) ---")

    from Core.System.guardrails import is_dry_run

    context, nav_page = await _create_bb_session_no_login(playwright)
    total_markets_saved = 0
    all_match_urls: List[str] = []

    try:
        # ── Phase 0: League Discovery ────────────────────────────────────────
        leagues = await extract_basketball_leagues_fb(nav_page)
        if not leagues:
            print("  [BB] No basketball leagues found. Aborting.")
            return

        print(f"  [BB] {len(leagues)} leagues discovered.")

        # ── Phase 1: Collect match URLs from each league page ────────────────
        # Re-use the same nav_page sequentially (one league at a time) to
        # collect anchor hrefs pointing to individual match pages.
        _BASE_URL = "https://www.football.com"
        MATCH_LINK_SEL = "a[href*='sr:match:']"

        for league in leagues:
            league_url = league.get("url", "")
            if not league_url:
                continue
            try:
                await nav_page.goto(
                    league_url,
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                await asyncio.sleep(1.5)

                hrefs = await nav_page.evaluate(
                    f"""() => {{
                        const links = document.querySelectorAll('{MATCH_LINK_SEL}');
                        return Array.from(links).map(a => a.href).filter(Boolean);
                    }}"""
                )
                for href in hrefs:
                    url = href if href.startswith("http") else f"{_BASE_URL}{href}"
                    if url not in all_match_urls:
                        all_match_urls.append(url)

            except Exception as e:
                print(f"  [BB] League page failed ({league.get('name')}): {e}")
                continue

        print(f"  [BB] {len(all_match_urls)} unique match URLs queued.")

        if not all_match_urls:
            print("  [BB] No match URLs found. Exiting harvesting.")
            return

        if is_dry_run():
            print("  [DRY-RUN] Basketball odds harvesting skipped (dry-run mode).")
            return

        # ── Phase 2: Concurrent odds extraction ──────────────────────────────
        from Data.Access.league_db import init_db
        conn = init_db()

        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        tasks = [
            _bb_match_odds_worker(sem, context, url, "")
            for url in all_match_urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        conn.execute("BEGIN")
        try:
            for res in results:
                if isinstance(res, dict):
                    saved = _persist_bb_result(conn, res)
                    total_markets_saved += saved
                elif isinstance(res, Exception):
                    print(f"  [BB Odds] Worker exception: {res}")
            conn.execute("COMMIT")
        except Exception as e:
            conn.execute("ROLLBACK")
            print(f"  [BB] DB commit failed: {e}")

        print(f"  [BB] {total_markets_saved} basketball market rows saved.")

        # ── Phase 3: Supabase sync ────────────────────────────────────────────
        if total_markets_saved > 0:
            try:
                from Data.Access.sync_manager import SyncManager, TABLE_CONFIG
                manager = SyncManager()
                if "basketball_match_odds" in TABLE_CONFIG:
                    await manager._sync_table(
                        "basketball_match_odds",
                        TABLE_CONFIG["basketball_match_odds"],
                    )
                    print("  [BB] Supabase sync complete.")
                else:
                    print("  [BB] basketball_match_odds not in TABLE_CONFIG — skipping sync.")
            except Exception as e:
                print(f"  [BB] Supabase sync failed (non-fatal): {e}")

    finally:
        try:
            await nav_page.close()
            await context.close()
            if hasattr(context, "_browser_ref"):
                await context._browser_ref.close()
        except Exception:
            pass

    print(
        f"\n  [BB Harvest] Complete — {len(all_match_urls)} matches processed, "
        f"{total_markets_saved} market rows saved.\n"
    )


# ── CHAPTER 2 VARIANT — Basketball Automated Booking ────────────────────────

@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_basketball_booking(playwright: Playwright) -> None:
    """
    Basketball Chapter 2 Equivalent — Automated Booking.

    Reads basketball predictions from the `predictions` table where
    sport='basketball', booking_code IS NOT NULL, and applies Stairway
    accumulator rules before placing.

    Booking is skipped in dry-run mode or when the kill switch is active.
    """
    from Core.System.guardrails import check_kill_switch, is_dry_run

    if check_kill_switch():
        print("  [KILL SWITCH] Aborting basketball booking.")
        return
    if is_dry_run():
        print("  [DRY-RUN] Basketball booking skipped.")
        return

    print("\n--- Running Basketball Automated Booking (Chapter 2B) ---")

    from Data.Access.league_db import init_db

    conn = init_db()
    today = __import__("datetime").date.today().strftime("%d.%m.%Y")

    # ── Load basketball booking candidates ────────────────────────────────────
    try:
        rows = conn.execute(
            """
            SELECT fixture_id, home_team, away_team, prediction,
                   confidence, booking_code, booking_odds, booking_url, date
            FROM predictions
            WHERE sport = 'basketball'
              AND booking_code IS NOT NULL
              AND booking_odds BETWEEN ? AND ?
              AND date = ?
            ORDER BY
                CASE confidence
                    WHEN 'Very High' THEN 1
                    WHEN 'High'      THEN 2
                    WHEN 'Medium'    THEN 3
                    ELSE 4
                END ASC,
                recommendation_score DESC NULLS LAST
            """,
            (_BB_STAIRWAY_ODDS_MIN, _BB_STAIRWAY_ODDS_MAX, today),
        ).fetchall()
    except Exception as e:
        print(f"  [BB Booking] DB query failed: {e}")
        return

    if not rows:
        print(f"  [BB Booking] No basketball booking codes available for {today}.")
        log_audit_event("BB_BOOKING_SKIP", f"No candidates for {today}", status="skipped")
        return

    columns = [
        "fixture_id", "home_team", "away_team", "prediction",
        "confidence", "booking_code", "booking_odds", "booking_url", "date",
    ]
    candidates = [dict(zip(columns, r)) for r in rows]
    print(f"  [BB Booking] {len(candidates)} basketball candidates loaded.")

    # ── Greedy accumulator selection ─────────────────────────────────────────
    seen_fixtures: set = set()
    accumulator: List[Dict] = []
    total_odds = 1.0

    for c in candidates:
        if len(accumulator) >= _BB_STAIRWAY_MAX_LEGS:
            break
        fid = c.get("fixture_id", "")
        if fid in seen_fixtures:
            continue
        odds = float(c.get("booking_odds") or 0)
        if not (_BB_STAIRWAY_ODDS_MIN <= odds <= _BB_STAIRWAY_ODDS_MAX):
            continue
        seen_fixtures.add(fid)
        accumulator.append(c)
        total_odds *= odds

    if not accumulator:
        print("  [BB Booking] Accumulator is empty after filtering.")
        log_audit_event("BB_BOOKING_SKIP", "Accumulator empty after odds filter", status="skipped")
        return

    print(
        f"  [BB Booking] Accumulator: {len(accumulator)} legs, "
        f"combined odds {total_odds:.3f}"
    )

    # ── Launch session + place ────────────────────────────────────────────────
    max_restarts = 3
    restarts = 0

    while restarts <= max_restarts:
        context = None
        try:
            context, page, current_balance = await _create_bb_session(playwright)
            log_state(chapter="Chapter 2B", action="Basketball booking")

            from Core.System.guardrails import run_all_pre_bet_checks, StaircaseTracker
            ok, reason = run_all_pre_bet_checks(balance=current_balance)
            if not ok:
                print(f"  [BB GUARDRAIL] Blocked: {reason}")
                log_audit_event("BB_GUARDRAIL_BLOCK", reason, status="blocked")
                return

            stake = StaircaseTracker().get_current_step_stake()
            print(f"  [BB Booking] Stairway stake: {stake}")

            # Share-code accumulator: navigate to each booking URL + place
            from .booker.placement import place_bets_for_matches

            matched_urls = {c["fixture_id"]: c["booking_url"] for c in accumulator}
            await place_bets_for_matches(page, matched_urls, accumulator, today)

            log_state(chapter="Chapter 2B", action="Basketball booking complete")
            log_audit_event(
                "BB_BOOKING_DONE",
                f"{len(accumulator)} legs, combined odds {total_odds:.3f}, stake {stake}",
                status="placed",
            )
            break

        except Exception as e:
            is_fatal = "FatalSessionError" in str(type(e)) or "dirty" in str(e).lower()
            if is_fatal and restarts < max_restarts:
                print(f"  [BB Booking] FATAL: {e}  — restarting ({restarts + 1}/{max_restarts})")
                restarts += 1
                if context:
                    try:
                        await context.close()
                    except Exception:
                        pass
                await asyncio.sleep(5)
                continue
            else:
                await log_error_state(None, "bb_booking_fatal", e)
                print(f"  [BB Booking] CRITICAL: {e}")
                break
        finally:
            if context:
                try:
                    await context.close()
                    if hasattr(context, "_browser_ref"):
                        await context._browser_ref.close()
                except Exception:
                    pass
