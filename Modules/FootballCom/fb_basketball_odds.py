# fb_basketball_odds.py: Football.com basketball odds extractor.
# Part of LeoBook Modules — FootballCom
# Sport: basketball
#
# Functions: extract_basketball_leagues_fb(), extract_basketball_match_odds()
# Called by: fb_manager (basketball odds worker)

"""
Basketball Odds Extraction — Football.com
Scrapes league listings and per-match betting markets (1X2, Over/Under,
Handicap) from football.com basketball pages without requiring a login.
"""

import asyncio
import re
import time
from typing import List, Dict, Optional

from playwright.async_api import Page

from Core.Utils.constants import now_ng
from Modules.Flashscore.fs_league_hydration import _scroll_to_load


# ── Constants ──────────────────────────────────────────────────────────────

_BASE_URL = "https://www.football.com"
_BASKETBALL_SCHEDULE = "/ng/m/sport/basketball/?time=all"

# Selectors — basketball league browser
_SEL_M_LEAGUE         = "div.m-league"
_SEL_LEAGUE_TITLE     = "div.m-league-title"
_SEL_LEAGUE_LINK      = "ul.m-country-row li.not-top-league a"

# Selectors — match page
_SEL_MATCH_CARD       = "section.match-card-section.match-card"
_SEL_TEAM_NAME        = "h1.team-name"
_SEL_MARKET_CONTENT   = "div.market-content"
_SEL_TABLE_ROW        = "div.m-table-row"
_SEL_TABLE_CELL       = "div.m-table-cell"
_SEL_ODDS_CELL        = "div.m-outcome-only-odds"
_SEL_MARKET_ID_ATTR   = "data-market-id"
_SEL_MARKET_TYPE_ATTR = "data-market-type"

# Regex helpers
_RE_CATEGORY_ID   = re.compile(r"sr:category:(\d+)")
_RE_TOURNAMENT_ID = re.compile(r"sr:tournament:(\d+)")
_RE_MATCH_ID      = re.compile(r"sr:match:(\d+)")
_RE_NUMERIC       = re.compile(r"[-+]?\d+(?:\.\d+)?")


# ── Internal helpers ────────────────────────────────────────────────────────

def _parse_ids_from_league_href(href: str) -> tuple[Optional[str], Optional[str]]:
    """Extract fb_category_id and fb_tournament_id from a league href."""
    cat   = _RE_CATEGORY_ID.search(href)
    tourn = _RE_TOURNAMENT_ID.search(href)
    return (
        cat.group(1)   if cat   else None,
        tourn.group(1) if tourn else None,
    )


def _parse_line(text: str) -> Optional[str]:
    """Extract the numeric line from an outcome label.
    'Over 212.5' → '212.5',  '+4.5' → '4.5',  'Home' → None."""
    m = _RE_NUMERIC.search(text)
    return m.group() if m else None


async def _scroll_until_stable(page: Page, row_selector: str, tag: str = "") -> int:
    """Scroll until no new elements matching row_selector appear."""
    return await _scroll_to_load(
        page,
        row_selector=row_selector,
        max_steps=30,
        step_wait=0.8,
        no_new_rows_limit=3,
    )


# ── League Discovery ────────────────────────────────────────────────────────

async def extract_basketball_leagues_fb(page: Page) -> List[Dict]:
    """
    Navigate to the football.com basketball schedule and extract every
    visible non-top league.

    Returns a list of dicts:
        {
            name:               str,
            url:                str   (absolute),
            sport:              'basketball',
            fb_category_id:     str | None,
            fb_tournament_id:   str | None,
        }
    """
    print("  [BB Leagues] Navigating to basketball schedule...")
    try:
        await page.goto(
            f"{_BASE_URL}{_BASKETBALL_SCHEDULE}",
            wait_until="domcontentloaded",
            timeout=30000,
        )
        await asyncio.sleep(2)
    except Exception as e:
        print(f"  [BB Leagues] Navigation failed: {e}")
        return []

    # Scroll to hydrate all m-league blocks
    await _scroll_until_stable(page, _SEL_M_LEAGUE, tag="leagues")

    leagues: List[Dict] = []

    try:
        league_blocks = await page.locator(_SEL_M_LEAGUE).all()
    except Exception as e:
        print(f"  [BB Leagues] Could not locate m-league blocks: {e}")
        return []

    for block in league_blocks:
        # Country name from the m-league-title div
        country = ""
        try:
            title_el = block.locator(_SEL_LEAGUE_TITLE).first
            if await title_el.count() > 0:
                country = (await title_el.inner_text()).strip()
        except Exception:
            pass

        # Individual league links
        try:
            links = await block.locator(_SEL_LEAGUE_LINK).all()
        except Exception:
            continue

        for link in links:
            try:
                href = await link.get_attribute("href") or ""
                name_text = (await link.inner_text()).strip()
                if not href or not name_text:
                    continue

                abs_url = href if href.startswith("http") else f"{_BASE_URL}{href}"
                cat_id, tourn_id = _parse_ids_from_league_href(href)

                display_name = f"{country} — {name_text}" if country else name_text

                leagues.append({
                    "name":               display_name,
                    "url":                abs_url,
                    "sport":              "basketball",
                    "fb_category_id":     cat_id,
                    "fb_tournament_id":   tourn_id,
                })
            except Exception:
                continue

    print(f"  [BB Leagues] Found {len(leagues)} basketball leagues.")
    return leagues


# ── Match Odds Extraction ───────────────────────────────────────────────────

async def extract_basketball_match_odds(page: Page, match_url: str) -> Dict:
    """
    Extract all basketball betting markets from a match detail page.

    The page is expected to already be navigated to match_url, OR this
    function navigates there itself if the current URL differs.

    Returns:
        {
            site_match_id:  str,           # 'sr:match:XXXXX'
            home_team:      str,
            away_team:      str,
            sport:          'basketball',
            extracted_at:   str,           # ISO timestamp
            markets:        list[dict],
        }

    Each market dict is one of:
        1X2 outcome:
            { market_id, market_type, base_market, outcome, odds_value }
        Over/Under row:
            { market_id, market_type, base_market, line, over_odds, under_odds }
        Handicap row:
            { market_id, market_type, base_market, line, home_odds, away_odds }
    """
    result: Dict = {
        "site_match_id":  "",
        "home_team":      "",
        "away_team":      "",
        "sport":          "basketball",
        "extracted_at":   now_ng().isoformat(),
        "markets":        [],
    }

    # Navigate if needed
    if page.url != match_url:
        try:
            await page.goto(match_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"  [BB Odds] Navigation to {match_url} failed: {e}")
            return result

    # ── Extract site_match_id from data-event-id attribute ──────────────────
    try:
        card = page.locator(_SEL_MATCH_CARD).first
        if await card.count() > 0:
            event_id = await card.get_attribute("data-event-id") or ""
            result["site_match_id"] = event_id  # e.g. 'sr:match:12345'
    except Exception:
        # Fallback: try to parse from URL
        m = _RE_MATCH_ID.search(match_url)
        if m:
            result["site_match_id"] = f"sr:match:{m.group(1)}"

    # ── Extract team names ───────────────────────────────────────────────────
    try:
        team_els = await page.locator(_SEL_TEAM_NAME).all()
        if len(team_els) >= 2:
            result["home_team"] = (await team_els[0].inner_text()).strip()
            result["away_team"] = (await team_els[1].inner_text()).strip()
        elif len(team_els) == 1:
            result["home_team"] = (await team_els[0].inner_text()).strip()
    except Exception as e:
        print(f"  [BB Odds] Team name extraction failed: {e}")

    # ── Scroll to load all market containers ─────────────────────────────────
    await _scroll_until_stable(page, f"[{_SEL_MARKET_ID_ATTR}]", tag="markets")

    # ── JS extraction — all markets in one pass ───────────────────────────────
    # We extract structured rows directly from the DOM using the known
    # basketball-specific selectors described in the DOM facts above.
    raw_markets = await page.evaluate(r"""() => {
        const results = [];

        // All market containers on the page
        const containers = document.querySelectorAll('[data-market-id]');

        containers.forEach((container) => {
            const marketId   = container.getAttribute('data-market-id') || '';
            const marketType = container.getAttribute('data-market-type') || 'normal-market';

            // Market title text
            const titleEl  = container.querySelector('div.m-market-title span.text');
            const baseName = titleEl ? titleEl.textContent.trim() : '';

            // ── Over/Under specifier rows ────────────────────────────────────
            // data-op="specifier-combo-content-outcome-row-{MARKET_ID}-{VALUE}-"
            const ouPattern = new RegExp(
                `specifier-combo-content-outcome-row-${marketId}-([\\d.]+)-`
            );
            const specifierRows = container.querySelectorAll('[data-op]');
            specifierRows.forEach((row) => {
                const op = row.getAttribute('data-op') || '';
                const match = op.match(ouPattern);
                if (!match) return;
                const line = match[1];

                // Odds cells inside this specifier row
                const oddsCells = row.querySelectorAll('div.m-outcome-only-odds');
                if (oddsCells.length < 2) return;

                const overText  = oddsCells[0].textContent.trim();
                const underText = oddsCells[1].textContent.trim();
                const overVal   = parseFloat(overText.replace(',', '.'));
                const underVal  = parseFloat(underText.replace(',', '.'));

                if (isNaN(overVal) || isNaN(underVal)) return;
                if (overVal <= 1.0 || underVal <= 1.0) return;

                results.push({
                    market_id:   marketId,
                    market_type: 'over_under',
                    base_market: baseName,
                    line:        line,
                    over_odds:   overVal,
                    under_odds:  underVal,
                });
            });

            // ── Standard table rows (1X2 and Handicap) ──────────────────────
            const tableRows = container.querySelectorAll('div.m-table-row');
            tableRows.forEach((row) => {
                const cells = row.querySelectorAll('div.m-table-cell');
                if (cells.length === 0) return;

                // Detect handicap: cells have a numeric label (spread value)
                // Detect 1X2: cells have text labels like Home / Draw / Away
                const cellData = [];
                cells.forEach((cell) => {
                    const oddsEl = cell.querySelector('div.m-outcome-only-odds');
                    if (!oddsEl) return;
                    const oddsVal = parseFloat(
                        oddsEl.textContent.trim().replace(',', '.')
                    );
                    if (isNaN(oddsVal) || oddsVal <= 1.0) return;

                    // Label is the non-odds text sibling
                    let labelText = '';
                    cell.childNodes.forEach((node) => {
                        if (node !== oddsEl && node.textContent) {
                            labelText += node.textContent;
                        }
                    });
                    labelText = labelText.trim();

                    cellData.push({ label: labelText, odds: oddsVal });
                });

                if (cellData.length === 0) return;

                // Handicap rows: two cells each with a numeric spread label
                if (
                    cellData.length === 2 &&
                    /[-+]?\d+\.?\d*/.test(cellData[0].label) &&
                    /[-+]?\d+\.?\d*/.test(cellData[1].label)
                ) {
                    const lineMatch = cellData[0].label.match(/([-+]?\d+\.?\d*)/);
                    const line = lineMatch ? lineMatch[1] : cellData[0].label;
                    results.push({
                        market_id:   marketId,
                        market_type: 'handicap',
                        base_market: baseName,
                        line:        line,
                        home_odds:   cellData[0].odds,
                        away_odds:   cellData[1].odds,
                    });
                    return;
                }

                // 1X2 rows: each cell is a named outcome
                cellData.forEach((cd) => {
                    if (!cd.label) return;
                    results.push({
                        market_id:   marketId,
                        market_type: '1x2',
                        base_market: baseName,
                        outcome:     cd.label,
                        odds_value:  cd.odds,
                    });
                });
            });
        });

        return results;
    }""")

    result["markets"] = raw_markets or []

    # Summarise
    by_type: Dict[str, int] = {}
    for m in result["markets"]:
        t = m.get("market_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    print(
        f"  [BB Odds] {result['home_team']} vs {result['away_team']} "
        f"({result['site_match_id']}): "
        f"{len(result['markets'])} rows extracted — {by_type}"
    )
    return result
