# extractor.py: Schedule scraper for Football.com.
# Part of LeoBook Modules — Football.com
#
# Functions: extract_league_matches(), validate_match_data()
#
# v1.2 (2026-03-26): _activate_and_wait_for_matches() now retries partial
#   hydration up to 2 times with scroll-reset + 2s wait before proceeding.
# v1.1 (2026-03-26): _recursive_scroll_cards() now delegates to _scroll_to_load()
#   from fs_league_hydration — adaptive micro-poll wait, bottom detection,
#   scroll reset, and consistent logging.
"""
Extractor Module
Handles extraction of leagues and matches from Football.com schedule pages.
"""

import asyncio
from typing import List, Dict

from playwright.async_api import Page

from Core.Intelligence.selector_manager import SelectorManager
from Core.Utils.constants import WAIT_FOR_LOAD_STATE_TIMEOUT
from Modules.Flashscore.fs_league_hydration import _scroll_to_load
from .navigator import hide_overlays
from Core.Intelligence.aigo_suite import AIGOSuite


async def _recursive_scroll_cards(page: Page, card_sel: str) -> int:
    """
    Scrolls the page until no new cards appear.
    Delegates to _scroll_to_load() from fs_league_hydration for adaptive
    micro-poll wait, bottom detection, scroll reset, and consistent logging.
    Returns: total count of cards found.
    """
    return await _scroll_to_load(
        page,
        row_selector=card_sel,
        max_steps=40,
        step_wait=0.8,
        no_new_rows_limit=3,
    )

async def _activate_and_wait_for_matches(
    page: Page,
    expected_count: int = 0,
) -> bool:
    """
    Hydrates a football.com tournament page and waits for match cards.
    Uses the proven stability-polling scroll from fs_league_hydration
    (RULEBOOK §2.16 — Reuse First) instead of fixed-time budgets.

    Returns True if cards found, False if page is genuinely empty.
    """
    # Recursive scroll defined locally below — no Flashscore import needed

    # ── FIX 5 (2026-03-17): networkidle wait before empty-check ──────────────────
    # Previously the NO_DATA_SELECTORS check ran immediately after domcontentloaded,
    # which fires before lazy-loaded match cards are injected. This caused the function
    # to return False ("no matches") during transient loading states.
    # Now we wait for networkidle (≤10s) so JS has finished fetching match data,
    # then dismiss any loading spinners, THEN check for empty-page indicators.
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        pass  # Timeout is acceptable — proceed with whatever is loaded

    # Dismiss loading spinners before checking for content
    SPINNER_SELECTORS = [
        "[data-loading]", "[class*='loading']", "[class*='spinner']",
        "[class*='skeleton']", "[aria-busy='true']",
    ]
    for spinner_sel in SPINNER_SELECTORS:
        try:
            await page.wait_for_selector(
                f":not({spinner_sel})", timeout=5000
            )
            break
        except Exception:
            pass

    # Phase 0: early exit only after page is fully loaded
    NO_DATA_SELECTORS = [
        ".match-card-error-message",
        ".flex-column.no-data",
        ".match-cards-wrapper-adaptor:has-text('no upcoming games')",
    ]
    for sel in NO_DATA_SELECTORS:
        try:
            if await page.locator(sel).count() > 0:
                print("    [Extractor] Info: League page indicates no upcoming matches.")
                return False
        except Exception:
            pass

    # Phase 1: tab switch — activate "All" tab if present
    try:
        tab_locators = page.locator("li.m-snap-nav-item")
        count = await tab_locators.count()
        for j in range(count):
            tab = tab_locators.nth(j)
            text = (await tab.inner_text()).lower()
            if any(x in text for x in ["all", "result", "finish"]):
                await tab.click(force=True)
                await asyncio.sleep(1.5)
                break
    except Exception:
        pass

    # Phase 2: stability-polling scroll with retry for partial hydration (BUG 4 FIX)
    CARD_SEL = (
        SelectorManager.get_selector("fb_schedule_page", "match_rows")
        or SelectorManager.get_selector("fb_schedule_page", "match_card")
        or SelectorManager.get_selector("fb_schedule_page", "league_section")
        or ".match-card-section.match-card, .match-card, .league-title-wrapper"
    )

    MAX_HYDRATION_RETRIES = 2
    found = 0
    for hydration_attempt in range(1 + MAX_HYDRATION_RETRIES):
        found = await _recursive_scroll_cards(page, CARD_SEL)

        # Check if we got enough cards
        if expected_count <= 0 or found >= expected_count:
            break  # Got all expected cards (or no expectation set)

        if found == 0:
            break  # Genuinely empty — no point retrying

        if hydration_attempt < MAX_HYDRATION_RETRIES:
            # Partial hydration — retry with extra wait for lazy-load
            print(
                f"    [Extractor] Partial hydration: "
                f"{found}/{expected_count} cards — retrying "
                f"({hydration_attempt + 1}/{MAX_HYDRATION_RETRIES})..."
            )
            await asyncio.sleep(2.0)  # Wait for lazy-loaded content
            # Scroll back to top and retry
            try:
                await page.evaluate("window.scrollTo(0, 0)")
                await asyncio.sleep(0.5)
            except Exception:
                pass

    # Phase 3: result
    if expected_count > 0 and found < expected_count and found > 0:
        print(
            f"    [Extractor] Partial hydration: "
            f"{found}/{expected_count} cards — proceeding (after retries)."
        )
    elif found == 0:
        # Re-check for "no games" message (may have loaded after scroll)
        for sel in NO_DATA_SELECTORS:
            try:
                if await page.locator(sel).count() > 0:
                    print("    [Extractor] Info: League page indicates no upcoming matches.")
                    return False
            except Exception:
                pass
        return False
    else:
        print(
            f"    [Extractor] {found}/{expected_count if expected_count else '?'} "
            f"cards hydrated."
        )
    return True


async def dismiss_overlays(page: Page) -> int:
    """Attempts to dismiss common overlays on football.com."""
    dismissed = 0
    OVERLAY_SELECTORS = [
        "button[id*='accept']", "button[class*='accept']", "button[class*='cookie']",
        ".overlay-close", ".popup-close", "button[class*='close']"
    ]
    for selector in OVERLAY_SELECTORS:
        try:
            el = await page.query_selector(selector)
            if el and await el.is_visible():
                await el.click(timeout=1000)
                dismissed += 1
                await asyncio.sleep(0.2)
        except Exception: pass
    return dismissed


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_schedule_page", element_key="league_section")
async def extract_league_matches(page: Page, target_date: str = None, target_league_name: str = None, fb_url: str = None, expected_count: int = 0) -> List[Dict]:
    """Iterates leagues and extracts matches with AIGO protection and hydration support."""
    if fb_url:
        print(f"    [Extractor] Navigating to {fb_url}...")
        await page.goto(fb_url, wait_until='domcontentloaded', timeout=30000)
    
    current_url = page.url
    print(f"  [Harvest] Sequence for {target_league_name or 'league'} -> {current_url}")

    is_tournament_page = "sr:tournament:" in current_url or "/sport/football/sr:category:" in current_url

    # Selectors
    league_section_sel = SelectorManager.get_selector_strict("fb_schedule_page", "league_section")
    match_card_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_rows")
    match_url_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_url")
    league_title_sel = SelectorManager.get_selector_strict("fb_schedule_page", "league_title_link")
    home_team_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_row_home_team_name")
    away_team_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_row_away_team_name")
    time_sel = SelectorManager.get_selector_strict("fb_schedule_page", "match_row_time")
    collapsed_icon_sel = SelectorManager.get_selector_strict("fb_schedule_page", "league_expand_icon_collapsed")

    all_matches = []
    
    if is_tournament_page:
        print(f"    [Mode] Direct Tournament Page")
        await dismiss_overlays(page)
        content_ready = await _activate_and_wait_for_matches(
            page, expected_count=expected_count
        )

        if not content_ready:
            return []

        # Use flexible common selectors for cards
        MATCH_CARD_SELECTORS = ["section.match-card", "div.match-card", "[class*='match-card']", "[data-match-id]"]
        discovered_selector = None
        for sel in MATCH_CARD_SELECTORS:
            if await page.locator(sel).count() > 0:
                discovered_selector = sel
                break
        
        if discovered_selector:
            all_matches = await _extract_matches_from_container(
                page, discovered_selector, home_team_sel, away_team_sel,
                time_sel, match_url_sel, target_league_name or "Tournament Matches", target_date
            )
            
    else:
        print(f"    [Mode] Global Schedule Page")
        await dismiss_overlays(page)
        content_ready = await _activate_and_wait_for_matches(
            page, expected_count=expected_count
        )
        
        if not content_ready:
            return []

        league_headers = await page.locator(league_section_sel).all()
        if league_headers:
            for i, header_locator in enumerate(league_headers):
                league_element = header_locator.locator(league_title_sel).first
                league_text = (await league_element.inner_text()).strip().replace('\n', ' - ') if await league_element.count() > 0 else f"Unknown {i+1}"

                if league_text.startswith("Simulated Reality"): continue
                if target_league_name and target_league_name.lower() not in league_text.lower(): continue

                if await header_locator.locator(collapsed_icon_sel).count() > 0:
                    await header_locator.click(force=True)
                    await asyncio.sleep(1.0)

                matches_container = await header_locator.evaluate_handle('(el) => el.nextElementSibling')
                if matches_container:
                    matches_in_section = await _extract_matches_from_container(
                        matches_container, match_card_sel, home_team_sel, away_team_sel,
                        time_sel, match_url_sel, league_text, target_date
                    )
                    if matches_in_section: all_matches.extend(matches_in_section)
        
        if not all_matches:
            # Fallback direct scan
            all_matches = await _extract_matches_from_container(
                page, match_card_sel, home_team_sel, away_team_sel,
                time_sel, match_url_sel, target_league_name or "Unknown League", target_date
            )

    print(f"  [Harvest] Total: {len(all_matches)}")
    return all_matches


async def _extract_matches_from_container(container, match_card_sel, home_team_sel, away_team_sel, time_sel, match_url_sel, league_text, target_date):
    """Internal helper to JS-scrape matches from a container.

    FIX: The original evaluate() call used `document.querySelectorAll` unconditionally,
    meaning the JS function always queried the full page document rather than the
    scoped container element. In the Global Schedule path, this caused matches from
    other league sections to bleed into every section's results.

    The fix passes a scoped root reference into the JS:
    - For a Playwright Page object: root = document (correct, page-wide query is intentional).
    - For a Playwright JSHandle (nextElementSibling result): root = the handle element itself,
      so querySelectorAll is scoped to that section only.
    """
    if not hasattr(container, 'evaluate'):
        return []

    # Determine if container is a Page (use document) or an ElementHandle/JSHandle (use element).
    # Page objects have a .url attribute; ElementHandles do not.
    is_page = hasattr(container, 'url')

    if is_page:
        # Tournament / full-page path: query the entire document.
        return await container.evaluate(r"""(args) => {
            const { selectors, leagueText, targetDate } = args;
            const MONTHS = {jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
            function parseDateFromTimeStr(raw) {
                // "10 Apr, 20:00" → { date: "2026-04-10", time: "20:00" }
                // "20:00"         → { date: null,         time: "20:00" }
                if (!raw) return { date: null, time: null };
                const m = raw.match(/(\d{1,2})\s+([A-Za-z]{3}),?\s*(\d{2}:\d{2})/);
                if (m) {
                    const day = m[1].padStart(2, '0');
                    const mon = MONTHS[m[2].toLowerCase()];
                    if (mon) {
                        const monStr = String(mon).padStart(2, '0');
                        const now = new Date();
                        let year = now.getFullYear();
                        return { date: `${year}-${monStr}-${day}`, time: m[3] };
                    }
                }
                // Fallback: just a time like "20:00"
                const t = raw.match(/(\d{1,2}:\d{2})/);
                return { date: null, time: t ? t[1].padStart(5, '0') : raw };
            }

            const results = [];
            const cards = document.querySelectorAll(selectors.match_card_sel);
            cards.forEach(card => {
                const homeEl = card.querySelector(selectors.home_team_sel);
                const awayEl = card.querySelector(selectors.away_team_sel);
                const timeEl = card.querySelector(selectors.time_sel)
                    || card.querySelector('.match-time')
                    || card.querySelector('.ko-time')
                    || card.querySelector('.fixture-time')
                    || card.querySelector('.start-time')
                    || card.querySelector('.time')
                    || card.querySelector('.match-card-header-info-time')
                    || card.querySelector('[class*="time"]:not([class*="team"]):not([class*="overtime"])')
                    || card.querySelector('[data-time]');

                const linkEl = card.querySelector(selectors.match_url_sel) || card.closest('a');
                if (homeEl && awayEl) {
                    const rawTime = timeEl ? timeEl.innerText.trim() : null;
                    const parsed = parseDateFromTimeStr(rawTime);
                    // Date priority: parsed from time string > dedicated date element > targetDate
                    let cardDate = parsed.date;
                    if (!cardDate) {
                        const dateEl = card.querySelector(
                            '[data-date], [class*="match-date"], '
                            + '[class*="event-date"], [class*="matchdate"], '
                            + '[class*="date-label"]'
                        );
                        cardDate = dateEl
                            ? (dateEl.dataset.date || dateEl.innerText.trim())
                            : null;
                        if (cardDate && !/^\d{4}-\d{2}-\d{2}$/.test(cardDate)) {
                            cardDate = null;
                        }
                    }
                    if (!cardDate) cardDate = targetDate;
                    results.push({
                        home: homeEl.innerText.trim(),
                        away: awayEl.innerText.trim(),
                        time: parsed.time,
                        league: leagueText,
                        url: linkEl ? linkEl.href : "",
                        date: cardDate
                    });
                }
            });
            return results;
        }""", {
            "selectors": {
                "match_card_sel": match_card_sel, "match_url_sel": match_url_sel,
                "home_team_sel": home_team_sel, "away_team_sel": away_team_sel, "time_sel": time_sel
            },
            "leagueText": league_text,
            "targetDate": target_date
        })
    else:
        # Global schedule path: container is a JSHandle for a specific league section.
        # FIX: evaluate() on a JSHandle passes the element as the first JS argument.
        # Use `element.querySelectorAll` to scope to this section only, preventing
        # cross-section bleed.
        return await container.evaluate(r"""(element, args) => {
            const { selectors, leagueText, targetDate } = args;
            const MONTHS = {jan:1,feb:2,mar:3,apr:4,may:5,jun:6,jul:7,aug:8,sep:9,oct:10,nov:11,dec:12};
            function parseDateFromTimeStr(raw) {
                if (!raw) return { date: null, time: null };
                const m = raw.match(/(\d{1,2})\s+([A-Za-z]{3}),?\s*(\d{2}:\d{2})/);
                if (m) {
                    const day = m[1].padStart(2, '0');
                    const mon = MONTHS[m[2].toLowerCase()];
                    if (mon) {
                        const monStr = String(mon).padStart(2, '0');
                        const year = new Date().getFullYear();
                        return { date: `${year}-${monStr}-${day}`, time: m[3] };
                    }
                }
                const t = raw.match(/(\d{1,2}:\d{2})/);
                return { date: null, time: t ? t[1].padStart(5, '0') : raw };
            }

            const results = [];
            const cards = element.querySelectorAll(selectors.match_card_sel);
            cards.forEach(card => {
                const homeEl = card.querySelector(selectors.home_team_sel);
                const awayEl = card.querySelector(selectors.away_team_sel);
                const timeEl = card.querySelector(selectors.time_sel)
                    || card.querySelector('.match-time')
                    || card.querySelector('.ko-time')
                    || card.querySelector('.fixture-time')
                    || card.querySelector('.start-time')
                    || card.querySelector('.time')
                    || card.querySelector('.match-card-header-info-time')
                    || card.querySelector('[class*="time"]:not([class*="team"]):not([class*="overtime"])')
                    || card.querySelector('[data-time]');

                const linkEl = card.querySelector(selectors.match_url_sel) || card.closest('a');
                if (homeEl && awayEl) {
                    const rawTime = timeEl ? timeEl.innerText.trim() : null;
                    const parsed = parseDateFromTimeStr(rawTime);
                    let cardDate = parsed.date;
                    if (!cardDate) {
                        const dateEl = card.querySelector(
                            '[data-date], [class*="match-date"], '
                            + '[class*="event-date"], [class*="matchdate"], '
                            + '[class*="date-label"]'
                        );
                        cardDate = dateEl
                            ? (dateEl.dataset.date || dateEl.innerText.trim())
                            : null;
                        if (cardDate && !/^\d{4}-\d{2}-\d{2}$/.test(cardDate)) {
                            cardDate = null;
                        }
                    }
                    if (!cardDate) cardDate = targetDate;
                    results.push({
                        home: homeEl.innerText.trim(),
                        away: awayEl.innerText.trim(),
                        time: parsed.time,
                        league: leagueText,
                        url: linkEl ? linkEl.href : "",
                        date: cardDate
                    });
                }
            });
            return results;
        }""", {
            "selectors": {
                "match_card_sel": match_card_sel, "match_url_sel": match_url_sel,
                "home_team_sel": home_team_sel, "away_team_sel": away_team_sel, "time_sel": time_sel
            },
            "leagueText": league_text,
            "targetDate": target_date
        })


async def validate_match_data(matches: List[Dict]) -> List[Dict]:
    """Validate and clean extracted match data.
    Only requires home+away team names — url is optional (needed for odds
    extraction but not for resolution pairing; many cards on tournament pages
    have no href at the list level).

    BUG2 FIX: Normalise time field — strip literal 'N/A' and empty strings to None.
    Emit a warning log if significant portion of cards have no time element.
    """
    valid_matches = []
    missing_time = 0
    for match in matches:
        if match.get('home') and match.get('away'):
            # Normalise time: N/A / empty string → None so downstream can distinguish
            raw_time = match.get('time')
            if not raw_time or str(raw_time).strip().upper() in ('N/A', 'NONE', '-', ''):
                match['time'] = None
                missing_time += 1
            valid_matches.append(match)
    print(f"  [Validation] {len(valid_matches)}/{len(matches)} valid.")
    if missing_time:
        print(
            f"  [Time] WARNING: {missing_time}/{len(valid_matches)} cards have no time element "
            f"— selector chain exhausted. Check .header .time on current football.com build."
        )
    return valid_matches
