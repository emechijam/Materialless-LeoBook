# open_bets_verifier.py: Verify placed bets appear on the open_bets page.
# Part of LeoBook Modules — FootballCom Booking
#
# Functions: verify_bet_on_open_bets()
#
# Called by: placement.py after place_stairway_accumulator()
# Source: https://www.football.com/ng/n/my_accounts/open_bets

"""
Open Bets Verification Module
After a bet is placed, navigates to the open_bets page and confirms the bet
actually landed by checking the DOM for matching bet details (stake, type, matches).
Also reports total accumulated open bets count.
"""

import asyncio
from typing import List, Dict, Optional
from playwright.async_api import Page
from Data.Access.db_helpers import log_audit_event


# ── Selectors (derived from user-provided open_bets DOM 2026-03-21) ─────────

OPEN_BETS_URL = "https://www.football.com/ng/n/my_accounts/open_bets"

# Tab showing total open bets count: "Open Bets (1)"
_SEL_OPEN_BETS_TAB = 'a[href*="open_bets"] .active-link, a[href*="open_bets"].active-link'
_SEL_OPEN_BETS_TAB_TEXT = 'a[href*="open_bets"]'

# Each bet card on the page
_SEL_BET_CARD = '[data-op="open-bets-page-item-with-data"]'

# Inside each bet card:
_SEL_BET_AMOUNT = '[data-op="open-bets-list-item-bet-money-text"]'  # "NGN 100.00"
_SEL_BET_TYPE = '[data-op="open-bets-list-item-bet-type-text"]'      # "Multiple"
_SEL_EVENT_ITEM = '[data-op="open-bets-card-event-item"]'           # each match row


def _normalise(text: str) -> str:
    """Lowercase, strip, remove extra whitespace for comparison."""
    import re
    return re.sub(r'\s+', ' ', text.lower().strip())


def _extract_currency_value(text: str) -> float:
    """Extract numeric value from currency string like 'NGN 100.00'."""
    import re
    match = re.search(r'[\d,]+\.?\d*', text.replace(',', ''))
    if match:
        try:
            return float(match.group())
        except ValueError:
            pass
    return 0.0


async def _get_open_bets_count(page: Page) -> int:
    """Extract total open bets count from the tab badge or text."""
    try:
        # Try the footer badge first: <span class="open-bets">1</span>
        badge = page.locator('span.open-bets').first
        if await badge.count() > 0:
            text = (await badge.inner_text()).strip()
            if text.isdigit():
                return int(text)

        # Fallback: parse "Open Bets (1)" from tab text
        tab = page.locator(_SEL_OPEN_BETS_TAB_TEXT).first
        if await tab.count() > 0:
            import re
            tab_text = await tab.inner_text()
            m = re.search(r'\((\d+)\)', tab_text)
            if m:
                return int(m.group(1))
    except Exception:
        pass
    return -1  # Unknown


async def _parse_bet_cards(page: Page) -> List[Dict]:
    """Parse all open bet cards from the page DOM."""
    cards = []
    try:
        card_locators = page.locator(_SEL_BET_CARD)
        count = await card_locators.count()

        for i in range(count):
            card = card_locators.nth(i)
            card_data = {}

            # Bet amount
            amount_el = card.locator(_SEL_BET_AMOUNT).first
            if await amount_el.count() > 0:
                card_data['amount_text'] = (await amount_el.inner_text()).strip()
                card_data['amount'] = _extract_currency_value(card_data['amount_text'])

            # Bet type
            type_el = card.locator(_SEL_BET_TYPE).first
            if await type_el.count() > 0:
                card_data['bet_type'] = (await type_el.inner_text()).strip()

            # Match events
            events = []
            event_locators = card.locator(_SEL_EVENT_ITEM)
            ev_count = await event_locators.count()
            for j in range(ev_count):
                ev = event_locators.nth(j)
                ev_text = _normalise(await ev.inner_text())
                events.append(ev_text)
            card_data['events'] = events
            card_data['event_count'] = ev_count

            # "and X other matches" text (total legs)
            try:
                other_text = await card.locator(
                    'p[data-cms-key="and_other_matches"]'
                ).first.inner_text()
                import re
                m = re.search(r'(\d+)\s+other', other_text)
                if m:
                    card_data['hidden_events'] = int(m.group(1))
                    card_data['total_legs'] = ev_count + card_data['hidden_events']
            except Exception:
                card_data['hidden_events'] = 0
                card_data['total_legs'] = ev_count

            # Stake and To Win
            try:
                stake_el = card.locator('text=Stake').locator('..').locator('span').last
                if await stake_el.count() > 0:
                    card_data['stake'] = _extract_currency_value(await stake_el.inner_text())
            except Exception:
                pass

            try:
                win_el = card.locator('text=To Win').locator('..').locator('span').last
                if await win_el.count() > 0:
                    card_data['to_win'] = _extract_currency_value(await win_el.inner_text())
            except Exception:
                pass

            cards.append(card_data)

    except Exception as e:
        print(f"    [OpenBets] Error parsing cards: {e}")

    return cards


def _match_accumulator_to_card(
    accumulator: List[Dict],
    card: Dict,
    expected_stake: float,
) -> bool:
    """
    Check if a bet card matches the accumulator we just placed.
    Matching criteria:
      1. Bet type contains "Multiple" (accumulator = multi bet)
      2. Stake matches (within ±1 tolerance for rounding)
      3. At least 2 team names from accumulator appear in the card events
    """
    # Check bet type
    bet_type = card.get('bet_type', '').lower()
    if 'multiple' not in bet_type and 'multi' not in bet_type and 'acca' not in bet_type:
        return False

    # Check stake
    card_stake = card.get('stake', card.get('amount', 0))
    if abs(card_stake - expected_stake) > 2.0:
        return False

    # Check team names — at least 2 accumulator teams must appear in events
    all_event_text = ' '.join(card.get('events', []))
    matches_found = 0
    for leg in accumulator:
        home = _normalise(leg.get('home_team', ''))
        away = _normalise(leg.get('away_team', ''))
        if home and home in all_event_text:
            matches_found += 1
        elif away and away in all_event_text:
            matches_found += 1
    return matches_found >= min(2, len(accumulator))


async def verify_bet_on_open_bets(
    page: Page,
    accumulator: List[Dict],
    expected_stake: float,
) -> bool:
    """
    Navigate to the open_bets page and verify the just-placed bet appears.

    Args:
        page:            Playwright Page (logged-in session).
        accumulator:     List of leg dicts with 'home_team', 'away_team' keys.
        expected_stake:  The stake amount that was placed (float).

    Returns:
        True if bet is verified on the page, False otherwise.
    """
    try:
        print(f"\n    [OpenBets] Verifying bet on open_bets page...")
        await page.goto(OPEN_BETS_URL, wait_until='domcontentloaded', timeout=30000)
        await asyncio.sleep(3)

        # 1. Get total open bets count
        total_open = await _get_open_bets_count(page)
        if total_open >= 0:
            print(f"    [OpenBets] Total open bets: {total_open}")
        else:
            print(f"    [OpenBets] Could not determine open bets count")

        # 2. Parse all bet cards
        cards = await _parse_bet_cards(page)
        print(f"    [OpenBets] Found {len(cards)} bet card(s) on page")

        if not cards:
            print(f"    [OpenBets] WARNING: No bet cards found!")
            log_audit_event(
                "OPEN_BETS_VERIFY",
                f"No cards found on open_bets page. Total badge: {total_open}",
                status="no_cards",
            )
            return False

        # 3. Try to match our accumulator to one of the cards
        for i, card in enumerate(cards):
            if _match_accumulator_to_card(accumulator, card, expected_stake):
                legs = card.get('total_legs', card.get('event_count', '?'))
                stake = card.get('stake', card.get('amount', '?'))
                to_win = card.get('to_win', '?')
                print(
                    f"    [OpenBets] VERIFIED: Bet #{i+1} matches accumulator "
                    f"({legs} legs, stake {stake}, to win {to_win})"
                )
                log_audit_event(
                    "OPEN_BETS_VERIFY",
                    f"Bet verified on open_bets page. "
                    f"Total open: {total_open}, Legs: {legs}, "
                    f"Stake: {stake}, To Win: {to_win}",
                    status="verified",
                )
                return True

        # 4. No match found
        print(
            f"    [OpenBets] WARNING: Placed accumulator not found among "
            f"{len(cards)} open bet(s). Manual check needed."
        )
        # Log card summaries for debugging
        for i, card in enumerate(cards):
            print(
                f"      Card {i+1}: {card.get('bet_type', '?')} | "
                f"stake={card.get('stake', card.get('amount', '?'))} | "
                f"legs={card.get('total_legs', card.get('event_count', '?'))}"
            )

        log_audit_event(
            "OPEN_BETS_VERIFY",
            f"Accumulator not matched among {len(cards)} cards. "
            f"Expected stake={expected_stake}, legs={len(accumulator)}",
            status="not_found",
        )
        return False

    except Exception as e:
        print(f"    [OpenBets] Verification error: {e}")
        log_audit_event(
            "OPEN_BETS_VERIFY",
            f"Verification failed with error: {e}",
            status="error",
        )
        return False


__all__ = ["verify_bet_on_open_bets"]
