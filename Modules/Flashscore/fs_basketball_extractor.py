# fs_basketball_extractor.py: Flashscore basketball league/fixture extractor.
# Part of LeoBook Modules — Flashscore
# Sport: basketball
#
# Functions: extract_basketball_leagues(), extract_basketball_fixtures(),
#            extract_basketball_results(), extract_basketball_seasons()

import re
from datetime import datetime
from typing import List, Dict, Optional

from playwright.async_api import Page

from Core.Utils.constants import now_ng

BASE_URL = "https://www.flashscore.com"
SPORT = "basketball"


# ═══════════════════════════════════════════════════════════════════════════════
#  CSS Selectors (basketball-specific DOM facts)
# ═══════════════════════════════════════════════════════════════════════════════

SEL = {
    # Country/league browser
    "country_item":   "a.lmc__element.lmc__item",
    "league_item":    "a.lmc__templateHref",
    "pin_key":        "span.pin.pinMyLeague",
    # Match rows
    "match_row":      "div.event__match",
    "match_link":     "a.eventRowLink",
    "match_time":     "div.event__time",
    # Participants
    "home_participant": "div.wcl-participant_bctDY.event__homeParticipant",
    "away_participant": "div.wcl-participant_bctDY.event__awayParticipant",
    "participant_name": 'span[data-testid="wcl-scores-simple-text-01"]',
    # Scores
    "score_home":     'span[data-testid="wcl-tableScore"][data-type="primary"][data-side="home"]',
    "score_away":     'span[data-testid="wcl-tableScore"][data-type="primary"][data-side="away"]',
    # Quarter scores: event__part--{home|away}.event__part--{1..5}
    "part_home_1":    'span.event__part.event__part--home.event__part--1[data-testid="wcl-tableScore"]',
    "part_away_1":    'span.event__part.event__part--away.event__part--1[data-testid="wcl-tableScore"]',
    "part_home_2":    'span.event__part.event__part--home.event__part--2[data-testid="wcl-tableScore"]',
    "part_away_2":    'span.event__part.event__part--away.event__part--2[data-testid="wcl-tableScore"]',
    "part_home_3":    'span.event__part.event__part--home.event__part--3[data-testid="wcl-tableScore"]',
    "part_away_3":    'span.event__part.event__part--away.event__part--3[data-testid="wcl-tableScore"]',
    "part_home_4":    'span.event__part.event__part--home.event__part--4[data-testid="wcl-tableScore"]',
    "part_away_4":    'span.event__part.event__part--away.event__part--4[data-testid="wcl-tableScore"]',
    "part_home_5":    'span.event__part.event__part--home.event__part--5[data-testid="wcl-tableScore"]',
    "part_away_5":    'span.event__part.event__part--away.event__part--5[data-testid="wcl-tableScore"]',
    # Tab navigation
    "tab_fixtures":   'a.tabs__tab[data-analytics-alias="fixtures"]',
    "tab_results":    'a.tabs__tab[data-analytics-alias="results"]',
    "tab_archive":    'a.tabs__tab[data-analytics-alias="archive"]',
    # Archive seasons
    "archive_link":   'a[href*="/basketball/"]',
}


# ═══════════════════════════════════════════════════════════════════════════════
#  JS Helpers
# ═══════════════════════════════════════════════════════════════════════════════

_EXTRACT_LEAGUES_JS = r"""() => {
    const results = [];
    const seen = new Set();
    const countryEls = document.querySelectorAll('a.lmc__element.lmc__item');
    for (const cEl of countryEls) {
        const href = cEl.getAttribute('href') || '';
        const m = href.match(/\/basketball\/([^/]+)\/?$/);
        if (!m) continue;
        const country = m[1];
        // Find league links that are siblings/children of this country item
        const parent = cEl.closest('li, div') || cEl.parentElement;
        if (!parent) continue;
        const leagueEls = parent.querySelectorAll('a.lmc__templateHref');
        for (const lEl of leagueEls) {
            const lHref = lEl.getAttribute('href') || '';
            const lm = lHref.match(/\/basketball\/([^/]+)\/([^/]+)\/?$/);
            if (!lm) continue;
            const url = lHref.startsWith('http') ? lHref : 'https://www.flashscore.com' + lHref;
            if (seen.has(url)) continue;
            seen.add(url);
            const name = lEl.innerText.trim();
            results.push({ name, url, country: lm[1], league_slug: lm[2], sport: 'basketball' });
        }
    }
    return results;
}"""

_EXTRACT_MATCHES_JS = r"""(s) => {
    const rows = document.querySelectorAll('div.event__match');
    const matches = [];
    for (const row of rows) {
        const rowId = row.getAttribute('id') || '';
        if (!rowId.startsWith('g_3_')) continue;
        const fixtureId = rowId.replace('g_3_', '');

        // Status
        let matchStatus = 'scheduled';
        if (row.classList.contains('event__match--scheduled')) matchStatus = 'scheduled';
        else if (row.classList.contains('event__match--live'))  matchStatus = 'live';
        else if (row.classList.contains('event__match--played')) matchStatus = 'finished';

        // Time/Date
        const timeEl = row.querySelector('div.event__time');
        let matchDate = '', matchTime = '';
        if (timeEl) {
            const raw = timeEl.innerText.trim()
                .replace(/Postp\.?|Canc\.?|Abn\.?/gi, '').trim();
            const fullM = raw.match(/(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})/);
            if (fullM) {
                matchDate = fullM[3] + '-' + fullM[2] + '-' + fullM[1];
                matchTime = fullM[4] + ':' + fullM[5];
            } else {
                const shortM = raw.match(/(\d{2})\.(\d{2})\.\s*(\d{2}):(\d{2})/);
                if (shortM) {
                    const yr = new Date().getFullYear();
                    matchDate = yr + '-' + shortM[2] + '-' + shortM[1];
                    matchTime = shortM[3] + ':' + shortM[4];
                } else {
                    const tmOnly = raw.match(/(\d{2}):(\d{2})/);
                    if (tmOnly) matchTime = tmOnly[1] + ':' + tmOnly[2];
                }
            }
            // Check for postponed/cancelled in raw text
            if (/Postp/i.test(timeEl.innerText)) matchStatus = 'postponed';
        }

        // Teams
        const homeEl = row.querySelector('div.wcl-participant_bctDY.event__homeParticipant');
        const awayEl = row.querySelector('div.wcl-participant_bctDY.event__awayParticipant');
        const homeName = homeEl
            ? (homeEl.querySelector('span[data-testid="wcl-scores-simple-text-01"]') || homeEl).innerText.trim()
            : '';
        const awayName = awayEl
            ? (awayEl.querySelector('span[data-testid="wcl-scores-simple-text-01"]') || awayEl).innerText.trim()
            : '';

        // Final scores
        const hScoreEl = row.querySelector('span[data-testid="wcl-tableScore"][data-type="primary"][data-side="home"]');
        const aScoreEl = row.querySelector('span[data-testid="wcl-tableScore"][data-type="primary"][data-side="away"]');
        const homeScore = hScoreEl && hScoreEl.innerText.trim() !== '-'
            ? parseInt(hScoreEl.innerText.trim(), 10) : null;
        const awayScore = aScoreEl && aScoreEl.innerText.trim() !== '-'
            ? parseInt(aScoreEl.innerText.trim(), 10) : null;

        // Quarter scores Q1-Q4 (event__part--1..4) and OT (event__part--5)
        function qScore(side, num) {
            const el = row.querySelector(
                `span.event__part.event__part--${side}.event__part--${num}[data-testid="wcl-tableScore"]`
            );
            if (!el || el.innerText.trim() === '-' || el.innerText.trim() === '') return null;
            const v = parseInt(el.innerText.trim(), 10);
            return isNaN(v) ? null : v;
        }

        // Match link → IDs
        const linkEl = row.querySelector('a.eventRowLink');
        const mLink = linkEl ? (linkEl.getAttribute('href') || '') : '';
        let homeTeamId = '', awayTeamId = '';
        const lm = mLink.match(/\/match\/basketball\/([^/]+)\/([^/]+)\//);
        if (lm) {
            homeTeamId = lm[1].substring(lm[1].lastIndexOf('-') + 1);
            awayTeamId = lm[2].substring(lm[2].lastIndexOf('-') + 1);
        }

        matches.push({
            fixture_id: fixtureId,
            date: matchDate,
            time: matchTime,
            home_team: homeName,
            away_team: awayName,
            home_team_id: homeTeamId,
            away_team_id: awayTeamId,
            home_score: homeScore,
            away_score: awayScore,
            q1_home: qScore('home', 1), q1_away: qScore('away', 1),
            q2_home: qScore('home', 2), q2_away: qScore('away', 2),
            q3_home: qScore('home', 3), q3_away: qScore('away', 3),
            q4_home: qScore('home', 4), q4_away: qScore('away', 4),
            ot_home: qScore('home', 5), ot_away: qScore('away', 5),
            match_status: matchStatus,
            match_link: mLink,
        });
    }
    return matches;
}"""

_EXTRACT_ARCHIVE_JS = r"""() => {
    const urls = [];
    const seen = new Set();
    for (const a of document.querySelectorAll('a')) {
        const href = a.getAttribute('href') || '';
        if (!href.match(/\/basketball\/[^/]+\/[^/]+-\d{4}/)) continue;
        const url = href.startsWith('http') ? href : 'https://www.flashscore.com' + href;
        if (!seen.has(url)) { seen.add(url); urls.push(url); }
    }
    return urls;
}"""


# ═══════════════════════════════════════════════════════════════════════════════
#  Date Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _infer_year(month: int) -> int:
    """Infer year from month for short-date formats."""
    now = now_ng()
    if month > now.month:
        return now.year - 1
    return now.year


def _parse_short_date(raw: str) -> str:
    """Parse 'DD.MM. HH:MM' or 'DD.MM.' into YYYY-MM-DD, best-effort."""
    m = re.match(r'(\d{2})\.(\d{2})\.', raw)
    if m:
        day, mon = int(m.group(1)), int(m.group(2))
        year = _infer_year(mon)
        return f"{year}-{mon:02d}-{day:02d}"
    return ""


# ═══════════════════════════════════════════════════════════════════════════════
#  Public Functions
# ═══════════════════════════════════════════════════════════════════════════════

async def extract_basketball_leagues(page: Page) -> List[Dict]:
    """Extract all basketball leagues from the country/league browser.

    Returns list of {name, url, country, league_slug, sport='basketball'}.
    Navigates to the basketball section if not already there.
    """
    bball_url = f"{BASE_URL}/basketball/"
    if "/basketball" not in page.url:
        await page.goto(bball_url, wait_until="domcontentloaded", timeout=60000)

    # Wait for the left-menu country items
    try:
        await page.wait_for_selector(SEL["country_item"], timeout=15000)
    except Exception:
        pass

    leagues: List[Dict] = await page.evaluate(_EXTRACT_LEAGUES_JS)

    # Fallback: if JS found nothing (menu not expanded), try direct link scrape
    if not leagues:
        raw: List[Dict] = await page.evaluate(r"""() => {
            const results = [], seen = new Set();
            for (const a of document.querySelectorAll('a.lmc__templateHref')) {
                const href = a.getAttribute('href') || '';
                const m = href.match(/\/basketball\/([^/]+)\/([^/]+)\/?$/);
                if (!m) continue;
                const url = href.startsWith('http') ? href : 'https://www.flashscore.com' + href;
                if (seen.has(url)) continue;
                seen.add(url);
                results.push({ name: a.innerText.trim(), url, country: m[1], league_slug: m[2], sport: 'basketball' });
            }
            return results;
        }""")
        leagues = raw

    return [lg for lg in leagues if lg.get("name") and lg.get("url")]


async def extract_basketball_fixtures(page: Page, league_url: str) -> List[Dict]:
    """Navigate to the fixtures tab and extract upcoming basketball matches.

    Returns list of:
        {fixture_id, date, time, home_team, away_team, home_team_id,
         away_team_id, match_status, sport, league_url, match_link}
    """
    fixtures_url = league_url.rstrip("/") + "/fixtures/"
    resp = await page.goto(fixtures_url, wait_until="domcontentloaded", timeout=60000)
    if resp and resp.status >= 400:
        print(f"  [Basketball/Fixtures] HTTP {resp.status} for {fixtures_url}")
        return []

    try:
        await page.wait_for_selector(SEL["match_row"], timeout=15000)
    except Exception:
        pass

    raw: List[Dict] = await page.evaluate(_EXTRACT_MATCHES_JS, SEL)

    out = []
    for m in raw:
        if not m.get("home_team") or not m.get("away_team"):
            continue
        out.append({
            "fixture_id":   m["fixture_id"],
            "date":         m["date"],
            "time":         m["time"],
            "home_team":    m["home_team"],
            "away_team":    m["away_team"],
            "home_team_id": m.get("home_team_id", ""),
            "away_team_id": m.get("away_team_id", ""),
            "match_status": m.get("match_status", "scheduled"),
            "match_link":   m.get("match_link", ""),
            "sport":        SPORT,
            "league_url":   league_url,
        })
    print(f"  [Basketball/Fixtures] {len(out)} fixtures from {league_url}")
    return out


async def extract_basketball_results(page: Page, league_url: str) -> List[Dict]:
    """Navigate to the results tab and extract completed basketball matches with quarter scores.

    Returns list of:
        {fixture_id, date, time, home_team, away_team, home_score, away_score,
         q1_home..q4_away, ot_home, ot_away, match_status, sport, league_url, match_link}
    """
    results_url = league_url.rstrip("/") + "/results/"
    resp = await page.goto(results_url, wait_until="domcontentloaded", timeout=60000)
    if resp and resp.status >= 400:
        print(f"  [Basketball/Results] HTTP {resp.status} for {results_url}")
        return []

    try:
        await page.wait_for_selector(SEL["match_row"], timeout=15000)
    except Exception:
        pass

    raw: List[Dict] = await page.evaluate(_EXTRACT_MATCHES_JS, SEL)

    out = []
    for m in raw:
        if not m.get("home_team") or not m.get("away_team"):
            continue
        status = m.get("match_status", "finished")
        if status == "scheduled":
            status = "finished"  # results tab only shows played matches

        # Coerce score fields to int or None
        def _int(v) -> Optional[int]:
            if v is None:
                return None
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        out.append({
            "fixture_id":   m["fixture_id"],
            "date":         m["date"],
            "time":         m["time"],
            "home_team":    m["home_team"],
            "away_team":    m["away_team"],
            "home_team_id": m.get("home_team_id", ""),
            "away_team_id": m.get("away_team_id", ""),
            "home_score":   _int(m.get("home_score")),
            "away_score":   _int(m.get("away_score")),
            "q1_home":      _int(m.get("q1_home")),
            "q1_away":      _int(m.get("q1_away")),
            "q2_home":      _int(m.get("q2_home")),
            "q2_away":      _int(m.get("q2_away")),
            "q3_home":      _int(m.get("q3_home")),
            "q3_away":      _int(m.get("q3_away")),
            "q4_home":      _int(m.get("q4_home")),
            "q4_away":      _int(m.get("q4_away")),
            "ot_home":      _int(m.get("ot_home")),
            "ot_away":      _int(m.get("ot_away")),
            "match_status": status,
            "match_link":   m.get("match_link", ""),
            "sport":        SPORT,
            "league_url":   league_url,
        })
    print(f"  [Basketball/Results] {len(out)} results from {league_url}")
    return out


async def extract_basketball_seasons(page: Page, league_url: str) -> List[str]:
    """Navigate to the archive tab and return all available season URLs.

    Returns list of absolute season URLs (strings), most recent first.
    """
    archive_url = league_url.rstrip("/") + "/archive/"
    resp = await page.goto(archive_url, wait_until="domcontentloaded", timeout=60000)
    if resp and resp.status >= 400:
        print(f"  [Basketball/Seasons] HTTP {resp.status} for {archive_url}")
        return []

    try:
        await page.wait_for_selector(SEL["archive_link"], timeout=15000)
    except Exception:
        pass

    urls: List[str] = await page.evaluate(_EXTRACT_ARCHIVE_JS)
    # Sort descending by year extracted from URL
    def _url_year(u: str) -> int:
        m = re.search(r'-(\d{4})(?:-\d{4})?/?$', u)
        return int(m.group(1)) if m else 0

    urls.sort(key=_url_year, reverse=True)
    print(f"  [Basketball/Seasons] {len(urls)} seasons from {league_url}")
    return urls
