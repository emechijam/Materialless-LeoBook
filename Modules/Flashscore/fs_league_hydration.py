# fs_league_hydration.py: Page hydration, scroll-to-load, Show More helpers.
# Part of LeoBook Modules — Flashscore
# REUSE THIS for any Flashscore or Football.com lazy-loading page.

import asyncio
import time
from typing import Optional

from playwright.async_api import Page

# ── Hydration & scroll tuning ─────────────────────────────────────────────────
HYDRATION_STABLE_FOR: float = 2.0
HYDRATION_MAX_WAIT: float = 30.0
SHOW_MORE_ROW_WAIT: float = 8.0
HYDRATION_POLL_INTERVAL: float = 0.4
SCROLL_MAX_STEPS: int = 40
SCROLL_STEP_WAIT: float = 0.6
SCROLL_NO_NEW_ROWS_LIMIT: int = 3


async def _wait_for_rows_stable(
    page: Page, row_selector: str,
    stable_for: float = HYDRATION_STABLE_FOR,
    max_wait: float = HYDRATION_MAX_WAIT,
) -> int:
    deadline = time.monotonic() + max_wait
    last_count = -1
    stable_since: Optional[float] = None
    while time.monotonic() < deadline:
        try:
            count = await page.locator(row_selector).count()
        except Exception:
            count = 0
        now = time.monotonic()
        if count != last_count:
            last_count = count
            stable_since = now
        elif stable_since is not None and (now - stable_since) >= stable_for:
            return last_count
        await asyncio.sleep(HYDRATION_POLL_INTERVAL)
    return last_count


async def _wait_for_page_hydration(
    page: Page, selectors: dict,
    max_wait: float = HYDRATION_MAX_WAIT,
) -> int:
    container_sel = selectors.get("main_container", "")
    row_sel = selectors.get("match_row", ":is([id^='g_1_'], [id^='g_3_'])")
    phase1_budget = max_wait / 2.0
    phase1_start = time.monotonic()
    if container_sel:
        try:
            await page.wait_for_selector(container_sel, timeout=int(phase1_budget * 1000))
        except Exception:
            pass
    phase1_elapsed = time.monotonic() - phase1_start
    phase2_budget = max(2.0, max_wait - phase1_elapsed)
    return await _wait_for_rows_stable(page, row_sel,
                                       stable_for=HYDRATION_STABLE_FOR,
                                       max_wait=phase2_budget)


async def _scroll_to_load(
    page: Page, row_selector: str,
    max_steps: int = SCROLL_MAX_STEPS,
    step_wait: float = SCROLL_STEP_WAIT,
    no_new_rows_limit: int = SCROLL_NO_NEW_ROWS_LIMIT,
) -> int:
    scroll_js = """() => {
        const h = window.innerHeight || document.documentElement.clientHeight || 1080;
        window.scrollBy({ top: h, behavior: 'instant' });
        return { scrollY: window.scrollY, innerHeight: window.innerHeight,
                 bodyHeight: document.body.scrollHeight };
    }"""
    last_count = 0
    no_new_streak = 0
    total_scrolled = 0
    for _ in range(max_steps):
        before = await page.locator(row_selector).count()
        try:
            pos = await page.evaluate(scroll_js)
        except Exception:
            break
        total_scrolled += 1
        await asyncio.sleep(step_wait)
        deadline = time.monotonic() + step_wait
        after = before
        while time.monotonic() < deadline:
            try:
                after = await page.locator(row_selector).count()
            except Exception:
                break
            if after > before:
                break
            await asyncio.sleep(HYDRATION_POLL_INTERVAL)
        no_new_streak = 0 if after > before else no_new_streak + 1
        last_count = after
        at_bottom = (
            pos.get("scrollY", 0) + pos.get("innerHeight", 0)
            >= pos.get("bodyHeight", 1) - 50
        )
        if at_bottom or no_new_streak >= no_new_rows_limit:
            break
    try:
        await page.evaluate("() => window.scrollTo({ top: 0, behavior: 'instant' })")
    except Exception:
        pass
    if total_scrolled:
        print(f"      [Scroll] {total_scrolled} steps -> {last_count} rows visible")
    return last_count


async def _expand_show_more(page: Page, selector_mgr, context_league: str, max_clicks: int = 50):
    """Click 'Show more' until exhausted or max_clicks reached.

    Args:
        selector_mgr: SelectorManager instance (passed in to avoid circular import)
        context_league: selector context string e.g. "fs_league_page"
    """
    clicks = 0
    btn_sel = selector_mgr.get_selector(context_league, "show_more_matches")
    row_sel = selector_mgr.get_selector(context_league, "match_row") or ":is([id^='g_1_'], [id^='g_3_'])"
    while clicks < max_clicks:
        try:
            btn = page.locator(btn_sel)
            if await btn.count() > 0 and await btn.first.is_visible(timeout=3000):
                before = await page.locator(row_sel).count()
                await btn.first.click()
                waited = 0.0
                arrived = False
                while waited < SHOW_MORE_ROW_WAIT:
                    await asyncio.sleep(HYDRATION_POLL_INTERVAL)
                    waited += HYDRATION_POLL_INTERVAL
                    if await page.locator(row_sel).count() > before:
                        arrived = True
                        break
                clicks += 1
                if not arrived:
                    break
            else:
                break
        except Exception:
            break
    if clicks:
        print(f"      [Expand] Clicked 'Show more' {clicks}x")
