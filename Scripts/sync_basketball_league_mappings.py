"""
Sync football.com basketball mappings from the local docs dump into leagues.json.

This script only enriches basketball rows that already exist in Data/Store/leagues.json.
It does not invent new Flashscore leagues for football.com-only competitions; unmatched
doc rows are reported so we can decide on them deliberately.

Run:
    python Scripts/sync_basketball_league_mappings.py
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[1]
LEAGUES_JSON = ROOT / "Data" / "Store" / "leagues.json"
FB_BASKETBALL_DOC = ROOT / "Docs" / "fb_basketball_country_leagues.html"

BASE_FB_URL = "https://www.football.com"
RE_CATEGORY_ID = re.compile(r"sr:category:(\d+)")
RE_TOURNAMENT_ID = re.compile(r"sr:(?:simple_)?tournament:(\d+)")

COUNTRY_ALIASES = {
    "chinese taipei": "taiwan",
    "international": "europe",
    "republic of korea": "south korea",
    "turkiye": "turkey",
}

# Doc label -> canonical Flashscore label when the competition names differ.
LEAGUE_ALIASES = {
    ("argentina", "lnb"): ("argentina", "liga a"),
    ("china", "wcba"): ("china", "wcba women"),
    ("czech republic", "zbl"): ("czech republic", "zbl women"),
    ("greece", "basketball league"): ("greece", "basket league"),
    ("iceland", "urvalsdeild"): ("iceland", "premier league"),
    ("iceland", "urvalsdeild women"): ("iceland", "premier league women"),
    ("europe", "liga aba"): ("europe", "admiralbet aba league"),
    ("europe", "aba liga 2"): ("europe", "aba league 2"),
    ("europe", "estonian latvian league"): ("europe", "latvian estonian league"),
    ("europe", "basketball africa league"): ("africa", "bal"),
    ("europe", "europe cup"): ("europe", "fiba europe cup"),
    ("israel", "national league"): ("israel", "liga leumit"),
    ("romania", "lnb women"): ("romania", "liga national women"),
    ("slovenia", "1 a skl"): ("slovenia", "liga otp banka"),
    ("spain", "liga acb"): ("spain", "acb"),
    ("south korea", "wkbl"): ("south korea", "wkbl women"),
    ("turkey", "super lig women"): ("turkey", "kbsl women"),
    ("usa", "ncaa division i national championship"): ("usa", "ncaa"),
    ("usa", "ncaa division i national championship women"): ("usa", "ncaa women"),
    ("usa", "national invitation tournament"): ("usa", "nit"),
    ("usa", "college basketball crown"): ("usa", "cbc"),
}


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def normalize_country(value: str) -> str:
    cleaned = clean_space(value).lower()
    return COUNTRY_ALIASES.get(cleaned, cleaned)


def normalize_name(value: str) -> str:
    cleaned = clean_space(value).lower()
    replacements = {
        "&": " and ",
        "+": " plus ",
        "/": " ",
        ",": " ",
        ".": " ",
        "-": " ",
        "(": " ",
        ")": " ",
        "'": "",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return re.sub(r"\s+", " ", cleaned).strip()


def titleize_country(value: str) -> str:
    words = []
    for token in value.split():
        if token in {"usa", "uk", "uae"}:
            words.append(token.upper())
        else:
            words.append(token.capitalize())
    return " ".join(words)


@dataclass
class BasketballDocRow:
    country_raw: str
    country_norm: str
    league_raw: str
    league_norm: str
    href: str
    fb_url: str
    fb_category_id: str | None
    fb_tournament_id: str | None


class FootballComBasketballDocParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[BasketballDocRow] = []
        self._in_league_title = False
        self._in_country_text = False
        self._in_link_name = False
        self._current_country_parts: list[str] = []
        self._current_country = ""
        self._current_href = ""
        self._current_name_parts: list[str] = []

    @staticmethod
    def _attrs_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
        return {k: (v or "") for k, v in attrs}

    @staticmethod
    def _classes(attrs: dict[str, str]) -> set[str]:
        return {cls for cls in attrs.get("class", "").split() if cls}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = self._attrs_map(attrs)
        classes = self._classes(attr_map)

        if tag == "div" and "m-league-title" in classes:
            self._in_league_title = True
            self._current_country_parts = []
            return

        if tag == "span" and self._in_league_title and "text" in classes:
            self._in_country_text = True
            return

        if tag == "a" and "/sport/basketball/" in attr_map.get("href", ""):
            self._current_href = attr_map["href"]
            self._current_name_parts = []
            return

        if tag == "div" and self._current_href and "m-item-left" in classes:
            self._in_link_name = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._in_country_text:
            self._in_country_text = False
            self._current_country = clean_space("".join(self._current_country_parts))
            return

        if tag == "div" and self._in_link_name:
            self._in_link_name = False
            return

        if tag == "div" and self._in_league_title:
            self._in_league_title = False
            return

        if tag == "a" and self._current_href:
            league_raw = clean_space("".join(self._current_name_parts))
            country_raw = clean_space(self._current_country)
            if league_raw and country_raw:
                href = self._current_href
                self.rows.append(
                    BasketballDocRow(
                        country_raw=country_raw,
                        country_norm=normalize_country(country_raw),
                        league_raw=league_raw,
                        league_norm=normalize_name(league_raw),
                        href=href,
                        fb_url=urljoin(BASE_FB_URL, href),
                        fb_category_id=_capture(RE_CATEGORY_ID, href),
                        fb_tournament_id=_capture(RE_TOURNAMENT_ID, href),
                    )
                )
            self._current_href = ""
            self._current_name_parts = []

    def handle_data(self, data: str) -> None:
        if self._in_country_text:
            self._current_country_parts.append(data)
        elif self._in_link_name:
            self._current_name_parts.append(data)


def _capture(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1) if match else None


def parse_fb_doc(path: Path) -> list[BasketballDocRow]:
    parser = FootballComBasketballDocParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser.rows


def load_basketball_entries(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in data if "/basketball/" in (row.get("url") or "").lower()]


def build_index(entries: list[dict]) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for row in entries:
        key = (
            normalize_country(row.get("fb_country") or row.get("country_code") or ""),
            normalize_name(row.get("name") or ""),
        )
        index[key] = row
    return index


def resolve_target(
    row: BasketballDocRow,
    index: dict[tuple[str, str], dict],
) -> tuple[dict | None, str]:
    exact_key = (row.country_norm, row.league_norm)
    if exact_key in index:
        return index[exact_key], "exact"

    alias_key = LEAGUE_ALIASES.get(exact_key)
    if alias_key and alias_key in index:
        return index[alias_key], "alias"

    return None, "unmatched"


def sync() -> int:
    if not LEAGUES_JSON.exists():
        raise FileNotFoundError(f"Missing {LEAGUES_JSON}")
    if not FB_BASKETBALL_DOC.exists():
        raise FileNotFoundError(f"Missing {FB_BASKETBALL_DOC}")

    raw_data = json.loads(LEAGUES_JSON.read_text(encoding="utf-8"))
    basketball_entries = [row for row in raw_data if "/basketball/" in (row.get("url") or "").lower()]
    index = build_index(basketball_entries)
    doc_rows = parse_fb_doc(FB_BASKETBALL_DOC)

    before_count = sum(1 for row in basketball_entries if row.get("fb_url"))
    exact_hits = 0
    alias_hits = 0
    updated = 0
    already_current = 0
    unresolved: list[BasketballDocRow] = []
    conflicts: list[str] = []
    assigned_target_ids: dict[str, BasketballDocRow] = {}

    for doc_row in doc_rows:
        target, mode = resolve_target(doc_row, index)
        if target is None:
            unresolved.append(doc_row)
            continue

        if mode == "exact":
            exact_hits += 1
        elif mode == "alias":
            alias_hits += 1

        league_id = target["league_id"]
        prior = assigned_target_ids.get(league_id)
        if prior and prior.fb_url != doc_row.fb_url:
            conflicts.append(
                f"{league_id}: {prior.country_raw} / {prior.league_raw} clashes with "
                f"{doc_row.country_raw} / {doc_row.league_raw}"
            )
            continue
        assigned_target_ids[league_id] = doc_row

        desired = {
            "fb_league_name": doc_row.league_raw,
            "fb_country": target.get("fb_country") or titleize_country(doc_row.country_norm),
            "fb_category_id": doc_row.fb_category_id,
            "fb_tournament_id": doc_row.fb_tournament_id,
            "fb_url": doc_row.fb_url,
            "fb_matched_tier": "T1",
        }

        if target.get("fb_url") and target.get("fb_url") != doc_row.fb_url:
            conflicts.append(
                f"{league_id}: existing fb_url {target.get('fb_url')} differs from doc {doc_row.fb_url}"
            )
            continue

        changed = False
        for key, value in desired.items():
            if target.get(key) != value:
                target[key] = value
                changed = True

        if changed:
            updated += 1
        else:
            already_current += 1

    after_count = sum(1 for row in basketball_entries if row.get("fb_url"))

    if updated:
        LEAGUES_JSON.write_text(
            json.dumps(raw_data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    print("=" * 72)
    print("Basketball league mapping sync")
    print("=" * 72)
    print(f"Doc rows parsed          : {len(doc_rows)}")
    print(f"Basketball rows in JSON  : {len(basketball_entries)}")
    print(f"Exact matches            : {exact_hits}")
    print(f"Alias matches            : {alias_hits}")
    print(f"Rows updated             : {updated}")
    print(f"Already current          : {already_current}")
    print(f"Mapped before            : {before_count}")
    print(f"Mapped after             : {after_count}")
    print(f"Unresolved doc rows      : {len(unresolved)}")
    print(f"Conflicts skipped        : {len(conflicts)}")

    if unresolved:
        print("\nUnresolved:")
        for row in unresolved:
            print(f"  - {row.country_raw}: {row.league_raw}")

    if conflicts:
        print("\nConflicts:")
        for item in conflicts:
            print(f"  - {item}")

    return 0 if not conflicts else 1


if __name__ == "__main__":
    raise SystemExit(sync())
