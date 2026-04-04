# outcome_reviewer_browser.py: Browser-based outcome extraction and orchestration.
# Part of LeoBook Data — Access Layer
#
# Split from outcome_reviewer.py (v9.6.0) — Playwright-dependent functions only.
# Functions: process_review_task_browser(), get_league_url(), get_final_score(),
#            update_country_league_url(), run_review_process(), run_accuracy_generation()

"""
Outcome Reviewer Browser Module
Playwright-based score scraping, review orchestration, and accuracy report generation.
"""

import asyncio
import uuid
import pytz
import pandas as pd
from datetime import datetime as dt, timedelta
from typing import Dict, List, Optional

from playwright.async_api import Playwright
from Core.Intelligence.aigo_suite import AIGOSuite

from Data.Access.db_helpers import (
    save_country_league_entry, evaluate_market_outcome,
    log_audit_event, _get_conn,
)
from Data.Access.league_db import query_all, upsert_accuracy_report, update_prediction
from Data.Access.outcome_reviewer import (
    LOOKBACK_LIMIT,
    get_predictions_to_review, save_single_outcome, process_review_task_offline,
)
from Data.Access.sync_manager import SyncManager
from Core.Intelligence.selector_manager import SelectorManager
from Core.Intelligence.selector_db import log_selector_failure
from Core.Utils.constants import NAVIGATION_TIMEOUT


async def process_review_task_browser(page, match: Dict) -> Optional[Dict]:
    """Review a prediction by visiting the match page (Browser fallback)."""
    match_link = match.get('match_link')
    if not match_link:
        return None

    try:
        print(f"      [Fallback] Visiting {match.get('home_team')} vs {match.get('away_team')}...")
        await page.goto(match_link, timeout=NAVIGATION_TIMEOUT)
        await page.wait_for_load_state("networkidle")

        final_score = await get_final_score(page)
        if final_score and '-' in final_score:
            match['actual_score'] = final_score
            h_score, a_score = final_score.split('-')
            match['home_score'] = h_score
            match['away_score'] = a_score
            save_single_outcome(match, 'finished')
            print(f"    [Result-B] {match.get('home_team')} {final_score} {match.get('away_team')}")
            return match
        elif final_score == "Match_POSTPONED":
            save_single_outcome(match, 'match_postponed')
        elif final_score == "ARCHIVED":
            print(f"      [!] Match {match.get('fixture_id')} appears deleted or archived. Flagging.")
            save_single_outcome(match, 'manual_review_needed')
    except Exception as e:
        print(f"      [Fallback Error] {e}")

    return None


async def get_league_url(page):
    """Extracts the league URL from the match page."""
    try:
        league_link_sel = "a[href*='/football/'][href$='/']"
        league_link = page.locator(league_link_sel).first
        LEAGUE_TIMEOUT = 10000
        href = await league_link.get_attribute('href', timeout=LEAGUE_TIMEOUT)
        if href:
            return href
    except Exception:
        pass
    return ""


async def get_final_score(page):
    """Extracts the final score. Returns 'Error' if not found."""
    try:
        status_selector = SelectorManager.get_selector("fs_match_page", "meta_match_status") or "div.fixedHeaderDuel__detailStatus"
        try:
            status_text = await page.locator(status_selector).first.inner_text(timeout=30000)
            ERROR_PAGE_SEL = "div.errorMessage"
            if await page.locator(ERROR_PAGE_SEL).is_visible():
                return "ARCHIVED"

            error_header = page.get_by_text("Error:", exact=True)
            error_message = page.get_by_text("The requested page can't be displayed. Please try again later.")

            if "postponed" in status_text.lower():
                return "Match_POSTPONED"

            if (await error_header.is_visible()) and (await error_message.is_visible()):
                return "ARCHIVED"

        except Exception:
            status_text = "finished"

        if ("finished" not in status_text.lower() and "aet" not in status_text.lower()
                and "pen" not in status_text.lower() and "fro" not in status_text.lower()):
            return "NOT_FINISHED"

        # Tier 1: data-testid + class selectors
        try:
            home_score_t = await page.locator('.detailScore__home, [data-testid="wcl-matchRowScore"][data-side="1"]').first.inner_text(timeout=2000)
            away_score_t = await page.locator('.detailScore__away, [data-testid="wcl-matchRowScore"][data-side="2"]').first.inner_text(timeout=2000)
            tier1_score = f"{home_score_t.strip()}-{away_score_t.strip()}"
            if tier1_score.replace('-', '').isdigit():
                return tier1_score
        except Exception:
            pass

        # Tier 2: Legacy CSS selectors
        home_score_sel = SelectorManager.get_selector("fs_match_page", "header_score_home") or "div.detailScore__wrapper > span:nth-child(1)"
        away_score_sel = SelectorManager.get_selector("fs_match_page", "header_score_away") or "div.detailScore__wrapper > span:nth-child(3)"
        try:
            home_score = await page.locator(home_score_sel).first.inner_text(timeout=3000)
            away_score = await page.locator(away_score_sel).first.inner_text(timeout=3000)
            final_score = f"{home_score.strip() if home_score else ''}-{away_score.strip() if away_score else ''}"
            if '-' in final_score and final_score.replace('-', '').isdigit():
                return final_score
        except Exception as sel_fail:
            failed_key = "header_score_away" if "nth-child(3)" in str(sel_fail) or "away" in str(sel_fail).lower() else "header_score_home"
            log_selector_failure("fs_match_page", failed_key, str(sel_fail))

        # Tier 3: JS heuristic
        try:
            heuristic_score = await page.evaluate("""() => {
                const home = document.querySelector('.detailScore__home, [data-testid="wcl-matchRowScore"][data-side="1"]');
                const away = document.querySelector('.detailScore__away, [data-testid="wcl-matchRowScore"][data-side="2"]');
                if (home && away) return home.innerText.trim() + '-' + away.innerText.trim();
                const spans = Array.from(document.querySelectorAll('span, div'));
                const scorePattern = /^(\\d+)\\s*-\\s*(\\d+)$/;
                for (const s of spans) {
                    if (scorePattern.test(s.innerText.trim())) return s.innerText.trim();
                }
                return null;
            }""")
            if heuristic_score:
                print(f"      [AIGO HEALED] Extracted score via heuristics: {heuristic_score}")
                return heuristic_score
        except Exception:
            pass

        return "Error"

    except Exception as e:
        print(f"    [Health] score_extraction_error (medium): Failed to extract score: {e}")
        return "Error"


def update_country_league_url(country_league: str, url: str):
    """Updates the url for a country_league."""
    if not country_league or not url or " - " not in country_league:
        return

    if url.startswith('/'):
        url = f"https://www.flashscore.com{url}"

    region, league_name = country_league.split(" - ", 1)

    save_country_league_entry({
        'league_id': f"{region}_{league_name}".replace(' ', '_').replace('-', '_').upper(),
        'region': region.strip(),
        'league': league_name.strip(),
        'league_url': url,
    })


@AIGOSuite.aigo_retry(max_retries=2, delay=5.0)
async def run_review_process(p: Optional[Playwright] = None):
    """Orchestrates the outcome review process."""
    print("\n   [Prologue] Starting Prediction Review Engine...")
    try:
        to_review = get_predictions_to_review()
        if not to_review:
            print("   [Info] No pending predictions found for review.")
            return

        print(f"   [Info] Processing {len(to_review)} predictions for outcome review...")
        to_review = to_review[:LOOKBACK_LIMIT]

        processed_matches = []
        needs_browser = []

        for m in to_review:
            result = process_review_task_offline(m)
            if result:
                processed_matches.append(result)
            else:
                needs_browser.append(m)

        if needs_browser and p:
            now = dt.now()
            eligible = []
            for m in needs_browser:
                try:
                    d_str = m.get('date', '')
                    t_str = m.get('match_time', '') or m.get('time', '')
                    if '.' in d_str:
                        parts = d_str.split('.')
                        d_str = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    ko = dt.strptime(f"{d_str} {t_str}", "%Y-%m-%d %H:%M")
                    if now - ko >= timedelta(hours=2):
                        eligible.append(m)
                except Exception:
                    eligible.append(m)

            skipped = len(needs_browser) - len(eligible)
            if skipped:
                print(f"   [Info] Skipped {skipped} future/in-progress matches from browser fallback.")

            if eligible:
                print(f"   [Info] Triggering Browser Fallback for {len(eligible)} unresolved reviews...")
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                for m in eligible:
                    result = await process_review_task_browser(page, m)
                    if result:
                        processed_matches.append(result)

                await browser.close()

        if processed_matches:
            print(f"\n   [SUCCESS] Reviewed {len(processed_matches)} match outcomes.")
            try:
                from Core.Intelligence.learning_engine import LearningEngine
                updated_weights = LearningEngine.update_weights()
                print(f"   [Learning] Updated weights for {len(updated_weights)-1} leagues.")
            except Exception as le:
                print(f"   [Learning] Weight update skipped: {le}")
        else:
            print("\n   [Info] All predictions still pending.")

    except Exception as e:
        print(f"   [CRITICAL] Outcome review failed: {e}")


async def run_accuracy_generation():
    """Aggregates performance metrics from predictions for the last 24h."""
    conn = _get_conn()

    print("\n   [ACCURACY] Generating performance metrics (Last 24h)...")
    try:
        rows = query_all(conn, 'predictions')
        if not rows:
            print("   [ACCURACY] No predictions found.")
            return

        df = pd.DataFrame(rows).fillna('')
        if df.empty:
            return

        lagos_tz = pytz.timezone('Africa/Lagos')
        now_lagos = dt.now(lagos_tz)
        yesterday_lagos = now_lagos - timedelta(days=1)

        def parse_updated(ts):
            try:
                dt_obj = pd.to_datetime(ts)
                if dt_obj.tzinfo is None:
                    return lagos_tz.localize(dt_obj)
                return dt_obj.astimezone(lagos_tz)
            except Exception:
                return pd.NaT

        df['updated_dt'] = df['last_updated'].apply(parse_updated)
        df_24h = df[(df['updated_dt'] >= yesterday_lagos) & (df['status'].isin(['reviewed', 'finished']))].copy()

        if df_24h.empty:
            print("   [ACCURACY] No predictions reviewed in the last 24h.")
            return

        volume = len(df_24h)
        correct_count = (df_24h['outcome_correct'] == '1').sum()
        win_rate = (correct_count / volume) * 100 if volume > 0 else 0

        total_return = 0
        for _, row in df_24h.iterrows():
            try:
                odds = float(row.get('odds', 0))
                if odds <= 0:
                    odds = 2.0
                if row['outcome_correct'] == '1':
                    total_return += (odds - 1)
                else:
                    total_return -= 1
            except Exception:
                pass

        return_pct = (total_return / volume) * 100 if volume > 0 else 0

        report_row = {
            'report_id': str(uuid.uuid4())[:8],
            'timestamp': now_lagos.isoformat(),
            'volume': volume,
            'win_rate': round(win_rate, 2),
            'return_pct': round(return_pct, 2),
            'period': 'last_24h',
        }

        upsert_accuracy_report(conn, report_row)
        log_audit_event('ACCURACY_REPORT', f"Metrics: Vol={volume}, WR={win_rate:.1f}%, ROI={return_pct:.1f}%")

        sync = SyncManager()
        if sync.supabase:
            await sync.batch_upsert('accuracy_reports', [report_row])

    except Exception as e:
        print(f"   [ACCURACY ERROR] {e}")
