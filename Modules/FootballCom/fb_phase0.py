# fb_phase0.py: Phase 0 fixture discovery for Football.com odds harvesting.
# Part of LeoBook Modules — Football.com
#
# Functions: run_league_calendar_fixtures_sync()
# Called by: fb_manager.run_odds_harvesting()
#
# Phase 0 performs a multi-league calendar sync to discover upcoming fixtures
# and flag confirmed-empty leagues before the main batch extraction begins.

"""
Football.com Phase 0 — League Calendar Fixture Discovery
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from playwright.async_api import Playwright

from Core.Utils.constants import FB_MOBILE_USER_AGENT, FB_MOBILE_VIEWPORT
from .extractor import extract_league_matches, validate_match_data
from Data.Access.db_helpers import save_site_matches


def _load_fb_league_lookup(leagues_json_path: str) -> Dict[str, dict]:
    """Load leagues.json and return {league_id: entry} for entries with fb_url."""
    try:
        with open(leagues_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {l['league_id']: l for l in data if l.get('fb_url')}
    except Exception as e:
        print(f"  [Error] Failed to load leagues.json: {e}")
        return {}


async def run_league_calendar_fixtures_sync(
    playwright: Playwright,
    leagues_json_path: str,
    league_ids: Optional[List[str]] = None,
) -> set:
    """
    Phase 0: Fixture Discovery — primary via schedule extractor, calendar fallback.

    v2 (2026-03-26): Reordered — extract_league_matches (fast, proven) is now
    the primary path. extract_league_calendar is fallback only when primary
    returns 0 matches.

    Returns: set of fb_urls that confirmed NO fixtures (empty leagues).
    """
    print("\n--- Running League Calendar Fixture Sync (Phase 0) ---")

    fb_lookup = _load_fb_league_lookup(leagues_json_path)
    if not fb_lookup:
        print("  [Warning] No fb_url mappings found. Skipping calendar sync.")
        return set()

    to_sync = {lid: entry for lid, entry in fb_lookup.items() if not league_ids or lid in league_ids}
    if not to_sync:
        print("  [Info] No leagues to sync calendar for.")
        return set()

    print(f"  [Calendar] Syncing {len(to_sync)} league hub calendars...")

    is_headless = os.getenv("CODESPACES") == "true" or (os.name != "nt" and not os.environ.get("DISPLAY"))

    async with await playwright.chromium.launch(headless=is_headless) as browser:
        context = await browser.new_context(
            user_agent=FB_MOBILE_USER_AGENT,
            viewport=FB_MOBILE_VIEWPORT
        )
        page = await context.new_page()

        total_discovered = 0
        empty_urls: set = set()

        for lid, entry in to_sync.items():
            country = entry.get('fb_country')
            league_name = entry.get('fb_league_name')
            fb_url = entry.get('fb_url')

            if not country or not league_name:
                continue

            matches = []
            source = "none"
            was_crash = False

            if fb_url:
                try:
                    raw = await extract_league_matches(
                        page,
                        target_league_name=league_name,
                        fb_url=fb_url,
                    )
                    if raw:
                        raw = await validate_match_data(raw)
                    if raw:
                        matches = raw
                        source = "schedule"
                except Exception as e:
                    err_lower = str(e).lower()
                    was_crash = "crashed" in err_lower or "target closed" in err_lower
                    if was_crash:
                        print(f"    [Primary] {league_name}: browser crashed — recreating page...")
                        try:
                            await page.close()
                        except Exception:
                            pass
                        page = await context.new_page()
                    else:
                        print(f"    [Primary] {league_name}: extract failed: {e}")

            if matches:
                normalized = [{
                    'home': m.get('home', ''),
                    'away': m.get('away', ''),
                    'date': m.get('date', 'Unknown'),
                    'time': m.get('time', 'Unknown'),
                    'league': league_name,
                    'url': m.get('url', ''),
                    'status': m.get('status', ''),
                    'score': 'N/A',
                } for m in matches]

                save_site_matches(normalized)
                total_discovered += len(normalized)
                print(f"    ✓ {league_name}: {len(normalized)} fixtures saved (via {source}).")
            else:
                print(f"    ! {league_name}: No fixtures found.")
                if fb_url and not was_crash:
                    empty_urls.add(fb_url)

        await context.close()

    print(f"  [Calendar] Sync complete. Total fixtures discovered: {total_discovered}, empty leagues: {len(empty_urls)}")
    return empty_urls
