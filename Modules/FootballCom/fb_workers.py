# fb_workers.py: Semaphore-bounded async workers for odds extraction and league processing.
# Part of LeoBook Modules — Football.com
#
# Functions: _odds_worker(), _league_worker()
# Called by: fb_manager.py (run_odds_harvesting)

"""
Football.com concurrency workers.
Each worker is semaphore-bounded so at most N pages run concurrently.
"""

import asyncio
import sqlite3
import time
from typing import Dict, List, Optional

from Core.Utils.constants import ODDS_PAGE_TIMEOUT_MS, ODDS_PAGE_LOAD_DELAY
from .odds_extractor import OddsExtractor, OddsResult
from .extractor import extract_league_matches, validate_match_data
from .fb_contract import FBDataContract, DataContractViolation
from Data.Access.db_helpers import save_site_matches, update_site_match_status


async def _odds_worker(
    sem: asyncio.Semaphore,
    context,
    match_row: Dict,
    conn,
) -> Optional[OddsResult]:
    """
    Semaphore-bounded odds extractor worker.
    Opens its own page, extracts, closes page.

    v5.0 (2026-03-17): Handles context-closed errors gracefully,
    takes debug screenshot on 0 outcomes after final retry.
    """
    async with sem:
        odds_page = None
        try:
            odds_page = await context.new_page()
            await odds_page.set_viewport_size({"width": 500, "height": 640})

            match_url  = match_row.get("url", "")
            fixture_id = match_row.get("fixture_id", "")
            site_id    = match_row.get("site_match_id", "")

            if not match_url:
                return None

            await odds_page.goto(
                match_url,
                wait_until="domcontentloaded",
                timeout=ODDS_PAGE_TIMEOUT_MS,
            )
            await asyncio.sleep(ODDS_PAGE_LOAD_DELAY)

            result: Optional[OddsResult] = None
            for attempt in range(3):
                extractor = OddsExtractor(odds_page, conn)
                result = await extractor.extract(fixture_id, site_id)

                if result.outcomes_extracted > 0:
                    break

                if attempt < 2:
                    delay = 2 * (attempt + 1)  # 2s, 4s
                    print(
                        f"    [Odds] {fixture_id}: 0 outcomes on attempt {attempt + 1}/3. "
                        f"Reloading page in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    try:
                        await odds_page.reload(
                            wait_until="domcontentloaded", timeout=ODDS_PAGE_TIMEOUT_MS
                        )
                        await asyncio.sleep(ODDS_PAGE_LOAD_DELAY)
                    except Exception as reload_err:
                        print(f"    [Odds] {fixture_id}: reload failed: {reload_err}")
                        break

            if result and result.outcomes_extracted == 0:
                try:
                    ss_name = f"debug_odds_final_{fixture_id}_{int(time.time())}.png"
                    await odds_page.screenshot(path=ss_name)
                    print(f"    [Debug] Final 0-outcome screenshot: {ss_name}")
                except Exception:
                    pass

            print(
                f"    [Odds] {fixture_id} -> "
                f"{result.markets_found} markets, "
                f"{result.outcomes_extracted} outcomes "
                f"({result.duration_ms}ms)"
            )

            if result.match_date or result.match_time:
                try:
                    update_kwargs = {}
                    if result.match_date:
                        update_kwargs["date"] = result.match_date
                    if result.match_time:
                        update_kwargs["match_time"] = result.match_time
                    if site_id and update_kwargs:
                        update_site_match_status(
                            site_id, "odds_extracted",
                            fixture_id=fixture_id,
                            commit=False,
                            **update_kwargs,
                        )
                        print(f"    [Odds] {fixture_id}: saved date={result.match_date} time={result.match_time}")
                except Exception as dt_save_err:
                    print(f"    [Odds] {fixture_id}: date/time save skipped: {dt_save_err}")

            return result

        except Exception as e:
            err_str = str(e)
            is_closed = "closed" in err_str.lower()
            if is_closed:
                print(f"    [Odds] {match_row.get('fixture_id')}: context/page closed — skipping gracefully")
            else:
                print(f"    [Odds] ERROR {match_row.get('fixture_id')}: {e}")
            if odds_page:
                try:
                    ss_name = f"debug_odds_crash_{match_row.get('fixture_id', 'unknown')}_{int(time.time())}.png"
                    await odds_page.screenshot(path=ss_name)
                except Exception:
                    pass
            return OddsResult(
                fixture_id=match_row.get("fixture_id", ""),
                site_match_id=match_row.get("site_match_id", ""),
                markets_found=0, outcomes_extracted=0,
                duration_ms=0, error=str(e),
            )
        finally:
            if odds_page:
                try:
                    await odds_page.close()
                except Exception:
                    pass


async def _league_worker(
    semaphore: asyncio.Semaphore,
    browser_context,
    league_id: str,
    league_name: str,
    fs_fixtures: List[Dict],
    fb_url: str,
    conn: sqlite3.Connection,
    matcher,
) -> List[Dict]:
    """
    Semaphore-bounded worker: one league → one page.
    EXTRACTION ONLY — opens a fresh page, extracts all matches from
    football.com, pairs each FS fixture with its candidate fb matches,
    then closes the page and returns the pairs.

    Resolution runs in a dedicated sequential phase AFTER all leagues
    have been extracted, so browser pages are closed before LLM quota
    is consumed.

    Returns: list of resolved match dicts with fixture_id linkage.
    """
    async with semaphore:
        page = None
        try:
            page = await browser_context.new_page()
            await page.set_viewport_size({"width": 500, "height": 640})

            print(f"\n  [League] {league_name} ({len(fs_fixtures)} fixtures) → {fb_url}")

            first_date = fs_fixtures[0].get('date', '') if fs_fixtures else ''
            all_page_matches = await extract_league_matches(
                page,
                first_date,
                target_league_name=league_name,
                fb_url=fb_url,
                expected_count=len(fs_fixtures),
            )

            if not all_page_matches:
                print(f"  [League] {league_name}: no matches on page")
                return []

            all_page_matches = await validate_match_data(all_page_matches)

            resolved_matches = []
            for fs_fix in fs_fixtures:
                match_row, score, method = await matcher.resolve_deterministic(
                    fs_fix, all_page_matches
                )

                if match_row:
                    try:
                        match_row['home'] = match_row.get('home', match_row.get('home_team'))
                        match_row['away'] = match_row.get('away', match_row.get('away_team'))
                        FBDataContract.validate_match(match_row)
                    except DataContractViolation as dcv:
                        print(f"    [Contract] {league_name}: skipping fixture due to violation: {dcv}")
                        continue

                    match_row["fixture_id"] = fs_fix.get("fixture_id", "")
                    match_row["home_id"] = fs_fix.get("home_team_id") or fs_fix.get("home_id")
                    match_row["away_id"] = fs_fix.get("away_team_id") or fs_fix.get("away_id")
                    match_row["resolution_method"] = method

                    save_site_matches([match_row], commit=False)
                    resolved_matches.append(match_row)

            if resolved_matches:
                print(f"    ✓ {league_name}: {len(resolved_matches)}/{len(fs_fixtures)} fixtures resolved and saved.")
            else:
                print(f"    ! {league_name}: 0/{len(fs_fixtures)} fixtures resolved.")

            return resolved_matches

        except Exception as e:
            print(f"  [League] ERROR {league_name}: {e}")
            return []
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
