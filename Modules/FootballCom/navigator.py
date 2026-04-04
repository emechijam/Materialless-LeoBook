# navigator.py: High-level site navigation and state discovery for Football.com.
# Part of LeoBook Modules — Football.com
#
# Functions: log_page_title(), extract_balance(), perform_login(),
#            load_or_create_session(), hide_overlays(),
#            navigate_to_schedule(), select_target_date()
# Called by: fb_manager.py (Chapter 1 P1, Chapter 2 P1)

"""
Navigator Module
Handles login, session management, balance extraction, and schedule navigation
for Football.com. All operations are scoped to a user_id — credentials are
fetched from the user_credentials table, never from module-level .env variables.
"""

import asyncio
import re
from pathlib import Path
from typing import Tuple

from playwright.async_api import BrowserContext, Page

from Core.Browser.site_helpers import fb_universal_popup_dismissal
from Core.Intelligence.selector_manager import SelectorManager
from Core.Utils.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT, now_ng
from Core.Utils.utils import capture_debug_snapshot, parse_date_robust
from Core.Intelligence.aigo_suite import AIGOSuite

AUTH_DIR = Path("Data/Auth")
MOBILE_VIEWPORT = {"width": 500, "height": 640}


def _get_user_credentials(user_id: str) -> Tuple[str, str]:
    """Fetch Football.com phone + password for user_id from user_credentials table.
    Raises ValueError if credentials are not stored for this user."""
    from Data.Access.league_db import get_connection, get_user_credential
    conn = get_connection()
    phone = get_user_credential(conn, user_id, "football_com", "phone")
    password = get_user_credential(conn, user_id, "football_com", "password")
    if not phone or not password:
        raise ValueError(
            f"No Football.com credentials found for user_id='{user_id}'. "
            "Register them with: store_user_credential(conn, user_id, 'football_com', 'phone', ...)"
        )
    return phone, password


async def log_page_title(page: Page, label: str = "") -> str:
    """Log the current page title."""
    try:
        return await page.title()
    except Exception as e:
        print(f"  [Simple Log] Could not get title: {e}")
        return ""


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_match_page", element_key="navbar_balance")
async def extract_balance(page: Page) -> float:
    """Extract account balance with AIGO self-healing safety net."""
    await page.set_viewport_size(MOBILE_VIEWPORT)
    print("  [Money] Retrieving account balance...")

    balance_sel = SelectorManager.get_selector_strict("fb_match_page", "navbar_balance")

    if balance_sel:
        await page.wait_for_selector(balance_sel, state="visible", timeout=5000)
        if await page.locator(balance_sel).count() > 0:
            balance_text = await page.locator(balance_sel).first.inner_text(timeout=3000)
            cleaned = re.sub(r'[^\d.]', '', balance_text)
            if cleaned:
                return float(cleaned)

    raise ValueError("Balance element not found or empty.")


@AIGOSuite.aigo_retry(max_retries=2, delay=3.0, context_key="fb_global", element_key="login_button")
async def perform_login(page: Page, phone: str, password: str):
    """Perform login for the given credentials with AIGO protection."""
    await page.set_viewport_size(MOBILE_VIEWPORT)
    print("  [Auth] Initiating Football.com login flow...")

    await page.goto("https://www.football.com/ng", wait_until='domcontentloaded',
                    timeout=NAVIGATION_TIMEOUT)
    await asyncio.sleep(2)

    login_sel = SelectorManager.get_selector_strict("fb_global", "login_button")
    if await page.locator(login_sel).count() > 0:
        await page.locator(login_sel).first.click(force=True)
        await asyncio.sleep(2)

    mobile_selector  = SelectorManager.get_selector_strict("fb_login_page", "login_input_username")
    password_selector = SelectorManager.get_selector_strict("fb_login_page", "login_input_password")
    login_btn_selector = SelectorManager.get_selector_strict("fb_login_page", "login_button_submit")

    print("  [Login] Filling mobile number...")
    await page.wait_for_selector(mobile_selector, state="visible", timeout=10000)
    await page.fill(mobile_selector, phone)

    print("  [Login] Filling password...")
    await page.wait_for_selector(password_selector, state="visible", timeout=5000)
    await page.fill(password_selector, password)

    print("  [Login] Clicking login submit...")
    await page.locator(login_btn_selector).first.click(force=True)

    await page.wait_for_load_state('networkidle', timeout=30000)
    await asyncio.sleep(5)
    print("[Login] Football.com login process completed.")


async def load_or_create_session(context: BrowserContext, user_id: str) -> Tuple[BrowserContext, Page]:
    """
    Load session from persistent context, validate, and log in if needed.
    Credentials are fetched from user_credentials table for user_id.
    """
    print("  [Auth] Using Persistent Context. Verifying session...")
    await asyncio.sleep(3)

    if not context.pages:
        page = await context.new_page()
    else:
        page = context.pages[0]

    await page.set_viewport_size(MOBILE_VIEWPORT)

    current_url = page.url
    if "football.com" not in current_url or current_url == "about:blank":
        await page.goto("https://www.football.com/ng", wait_until='networkidle',
                        timeout=NAVIGATION_TIMEOUT)

    print("  [Auth] Step 0: Validating session state...")

    not_logged_in_sel = SelectorManager.get_selector_strict("fb_global", "not_logged_in_indicator")
    if not_logged_in_sel:
        try:
            if (await page.locator(not_logged_in_sel).count() > 0
                    and await page.locator(not_logged_in_sel).is_visible(timeout=3000)):
                print("  [Auth] User is NOT logged in. Fetching credentials and logging in...")
                phone, password = _get_user_credentials(user_id)
                await perform_login(page, phone, password)
        except Exception as e:
            print(f"  [Auth] Login validation error: {e}. Attempting login...")
            phone, password = _get_user_credentials(user_id)
            await perform_login(page, phone, password)

    balance = await extract_balance(page)
    print(f"  [Auth] Current Account Balance: {balance}")
    if balance <= 10.0:
        print("  [Warning] Low balance detected!")

    try:
        from .booker.slip import force_clear_slip
        await force_clear_slip(page)
    except ImportError:
        print("  [Auth] Warning: Could not import force_clear_slip.")
    except Exception as e:
        print(f"  [Auth] Failed to clear betslip: {e}")

    return context, page


async def hide_overlays(page: Page):
    """Inject CSS to hide obstructing overlays like bottom nav and download bars."""
    try:
        overlay_sel = SelectorManager.get_selector_strict("fb_global", "overlay_elements")
        css_content = f"""
            {overlay_sel} {{
                display: none !important;
                visibility: hidden !important;
                pointer-events: none !important;
            }}
        """
        await page.add_style_tag(content=css_content)
        await page.evaluate(
            f"document.querySelectorAll(\"{overlay_sel}\").forEach(el => el.style.display = 'none');"
        )
    except Exception as e:
        print(f"  [UI] Failed to hide overlays: {e}")


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_global", element_key="full_schedule_button")
async def navigate_to_schedule(page: Page):
    """Navigate to the Football.com match schedule page."""
    await fb_universal_popup_dismissal(page)
    schedule_url = "https://www.football.com/ng/m/sport/football/?sort=2&tab=matches"
    print(f"  [Navigation] Going to schedule URL: {schedule_url}")
    await page.goto(schedule_url, wait_until="domcontentloaded", timeout=30000)
    await hide_overlays(page)


@AIGOSuite.aigo_retry(max_retries=2, delay=2.0, context_key="fb_schedule_page", element_key="filter_dropdown_today")
async def select_target_date(page: Page, target_date: str) -> bool:
    """Select target date on the schedule page with AIGO self-healing."""
    await capture_debug_snapshot(page, "pre_date_select", f"Attempting to select {target_date}")

    dropdown_sel = SelectorManager.get_selector_strict("fb_schedule_page", "filter_dropdown_today")
    if not dropdown_sel or await page.locator(dropdown_sel).count() == 0:
        raise ValueError(f"Date dropdown '{dropdown_sel}' not found.")

    await page.locator(dropdown_sel).first.click(force=True)
    await asyncio.sleep(1)

    target_dt = parse_date_robust(target_date)
    today_ng = now_ng().date()
    day_str = "Today" if target_dt.date() == today_ng else target_dt.strftime("%A")

    day_item_tmpl = SelectorManager.get_selector_strict("fb_schedule_page", "day_list_item_template")
    day_item_sel = day_item_tmpl.replace("{day}", day_str)

    if await page.locator(day_item_sel).count() == 0:
        day_item_sel = day_item_tmpl.replace("{day}", target_dt.strftime("%a"))

    if await page.locator(day_item_sel).count() > 0:
        await page.locator(day_item_sel).first.click(force=True)
    else:
        raise ValueError(f"Target day '{day_str}' not found in dropdown.")

    await page.wait_for_load_state('networkidle', timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)

    sort_sel = SelectorManager.get_selector_strict("fb_schedule_page", "sort_dropdown")
    if sort_sel and await page.locator(sort_sel).count() > 0:
        await page.locator(sort_sel).first.click(force=True)
        await asyncio.sleep(1)
        item_tmpl = SelectorManager.get_selector_strict("fb_schedule_page", "sort_dropdown_list_item_template")
        item_sel = item_tmpl.replace("{sort}", "League")
        await page.locator(item_sel).first.click(force=True)

    return True
