import json
import re
import os
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
import difflib

# Configuration
ROOT = Path(__file__).resolve().parents[1]
LEAGUES_JSON = ROOT / "Data" / "Store" / "leagues.json"
FB_BASKETBALL_DOC = ROOT / "docs" / "fb_basketball_country_leagues.html"
FS_BASKETBALL_DOC = ROOT / "docs" / "fs_basketball_country_leagues.html"
BASE_FB_URL = "https://www.football.com"

# Regex patterns
RE_CATEGORY_ID = re.compile(r"sr:category:(\d+)")
RE_TOURNAMENT_ID = re.compile(r"sr:(?:simple_)?tournament:(\d+)")

# Configuration for matching
# (FS_Country) -> Canonical_Country
COUNTRY_ALIASES = {
    "chinese taipei": "taiwan",
    "international": "europe",
    "republic of korea": "south korea",
    "turkiye": "turkey",
    "czech republic": "czechia",
    "usa": "usa",
    "al": "albania",
    "ar": "argentina",
    "au": "australia",
    "at": "austria",
    "be": "belgium",
    "br": "brazil",
    "ca": "canada",
    "cn": "china",
    "hr": "croatia",
    "cy": "cyprus",
    "cz": "czechia",
    "dk": "denmark",
    "ee": "estonia",
    "fi": "finland",
    "fr": "france",
    "ge": "georgia",
    "de": "germany",
    "gr": "greece",
    "hu": "hungary",
    "is": "iceland",
    "id": "indonesia",
    "ir": "iran",
    "iq": "iraq",
    "ie": "ireland",
    "il": "israel",
    "it": "italy",
    "jp": "japan",
    "jo": "jordan",
    "kz": "kazakhstan",
    "lv": "latvia",
    "lb": "lebanon",
    "lt": "lithuania",
    "lu": "luxembourg",
    "mx": "mexico",
    "me": "montenegro",
    "ma": "morocco",
    "nl": "netherlands",
    "nz": "new zealand",
    "no": "norway",
    "py": "paraguay",
    "ph": "philippines",
    "pl": "poland",
    "pt": "portugal",
    "pr": "puerto rico",
    "ro": "romania",
    "ru": "russia",
    "sa": "saudi arabia",
    "rs": "serbia",
    "sk": "slovakia",
    "si": "slovenia",
    "kr": "south korea",
    "es": "spain",
    "se": "sweden",
    "ch": "switzerland",
    "tw": "taiwan",
    "th": "thailand",
    "tn": "tunisia",
    "tr": "turkey",
    "ua": "ukraine",
    "ae": "uae",
    "gb": "united kingdom",
    "us": "usa",
    "uy": "uruguay",
    "ve": "venezuela",
    "vn": "vietnam",
}

# (FS_Country, FS_League) -> (FB_Country, FB_League)
# KEYS are what's in leagues.json (Flashscore target)
# VALUES are what's in doc (Football.com source)
LEAGUE_ALIASES = {
    # Argentina
    ("argentina", "liga a"): ("argentina", "lnb"),
    # Australia
    ("australia", "nbl"): ("australia", "nbl"),
    # Brazil
    ("brazil", "nbb"): ("brazil", "nbb"),
    # China
    ("china", "cba"): ("china", "cba"),
    ("china", "wcba women"): ("china", "wcba"),
    # Europe / International
    ("europe", "euroleague"): ("international", "euroleague"),
    ("europe", "eurocup"): ("international", "eurocup"),
    ("europe", "champions league"): ("international", "champions league"),
    ("europe", "fiba europe cup"): ("international", "europe cup"),
    ("europe", "admiralbet aba league"): ("international", "liga aba"),
    ("europe", "aba league 2"): ("international", "aba liga 2"),
    ("europe", "latvian estonian league"): ("international", "estonian latvian league"),
    # Other Countries
    ("greece", "basket league"): ("greece", "basketball league"),
    ("iceland", "premier league"): ("iceland", "urvalsdeild"),
    ("iceland", "premier league women"): ("iceland", "urvalsdeild women"),
    ("israel", "super league"): ("israel", "winner league"),
    ("israel", "liga leumit"): ("israel", "national league"),
    ("romania", "liga national women"): ("romania", "lnb women"),
    ("slovenia", "liga otp banka"): ("slovenia", "1 a skl"),
    ("spain", "acb"): ("spain", "liga acb"),
    ("south korea", "kbl"): ("south korea", "kbl"),
    ("south korea", "wkbl women"): ("south korea", "wkbl"),
    ("turkey", "super lig"): ("turkey", "bsl"),
    ("turkey", "kbsl women"): ("turkey", "super lig women"),
    # USA
    ("usa", "nba"): ("usa", "nba"),
    ("usa", "ncaa"): ("usa", "ncaa division i national championship"),
    ("usa", "ncaa women"): ("usa", "ncaa division i national championship women"),
    ("usa", "nit"): ("usa", "national invitation tournament"),
    ("usa", "cbc"): ("usa", "college basketball crown"),
}

@dataclass
class FBLeague:
    country_raw: str
    country_norm: str
    league_raw: str
    league_norm: str
    href: str
    fb_url: str
    category_id: str | None
    tournament_id: str | None
    is_women: bool

@dataclass
class FSLeague:
    country_raw: str
    country_norm: str
    league_raw: str
    league_norm: str
    league_id: str
    url: str
    is_women: bool

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def normalize_country(text: str) -> str:
    c = clean(text).lower()
    return COUNTRY_ALIASES.get(c, c)

def normalize_league(text: str) -> str:
    t = clean(text).lower()
    t = t.replace("&", " and ").replace("+", " plus ")
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return clean(t)

def is_women_league(text: str) -> bool:
    t = text.lower()
    return "women" in t or "female" in t or "femenina" in t

class FBParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.leagues = []
        self.current_country = ""
        self.in_country_span = False
        self.in_league_name_div = False
        self.current_href = ""
        self.current_name_parts = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "div" and "m-league-title" in cls:
            self.current_country = ""
        if tag == "span" and "text" in cls:
            self.in_country_span = True
        if tag == "a" and "/sport/basketball/" in d.get("href", ""):
            self.current_href = d["href"]
            self.current_name_parts = []
        if tag == "div" and "m-item-left" in cls:
            self.in_league_name_div = True

    def handle_endtag(self, tag):
        if tag == "span" and self.in_country_span:
            self.in_country_span = False
            self.current_country = clean(self.current_country)
        if tag == "div" and self.in_league_name_div:
            self.in_league_name_div = False
        if tag == "a" and self.current_href:
            name = clean(" ".join(self.current_name_parts))
            if name and self.current_country:
                league = FBLeague(
                    country_raw=self.current_country,
                    country_norm=normalize_country(self.current_country),
                    league_raw=name,
                    league_norm=normalize_league(name),
                    href=self.current_href,
                    fb_url=urljoin(BASE_FB_URL, self.current_href),
                    category_id=None,
                    tournament_id=None,
                    is_women=is_women_league(name)
                )
                cat = RE_CATEGORY_ID.search(self.current_href)
                trny = RE_TOURNAMENT_ID.search(self.current_href)
                league.category_id = cat.group(1) if cat else None
                league.tournament_id = trny.group(1) if trny else None
                self.leagues.append(league)
            self.current_href = ""

    def handle_data(self, data):
        if self.in_country_span:
            self.current_country += data
        if self.in_league_name_div:
            self.current_name_parts.append(data)

class FSParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.leagues = []
        self.current_country_raw = ""
        self.in_country_span = False
        self.current_href = ""
        self.current_league_name_raw = ""
        self.in_template_a = False

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        cls = d.get("class", "")
        if tag == "span" and "lmc__elementName" in cls:
            self.in_country_span = True
            self.current_country_raw = ""
        if tag == "a" and "lmc__templateHref" in cls:
            self.current_href = d.get("href", "")
            self.current_league_name_raw = ""
            self.in_template_a = True
        if tag == "span" and "pin" in cls and "data-label-key" in d:
            if self.current_href and self.current_league_name_raw:
                self.leagues.append(FSLeague(
                    country_raw=self.current_country_raw,
                    country_norm=normalize_country(self.current_country_raw),
                    league_raw=self.current_league_name_raw,
                    league_norm=normalize_league(self.current_league_name_raw),
                    league_id=d["data-label-key"],
                    url=self.current_href,
                    is_women=is_women_league(self.current_league_name_raw)
                ))

    def handle_endtag(self, tag):
        if tag == "span" and self.in_country_span:
            self.in_country_span = False
            self.current_country_raw = clean(self.current_country_raw)
        if tag == "a" and self.in_template_a:
            self.in_template_a = False
            self.current_league_name_raw = clean(self.current_league_name_raw)

    def handle_data(self, data):
        if self.in_country_span:
            self.current_country_raw += data
        if self.in_template_a:
            self.current_league_name_raw += data

def reconcile():
    print(f"Loading {LEAGUES_JSON}...")
    with open(LEAGUES_JSON, "r", encoding="utf-8") as f:
        leagues_data = json.load(f)

    # All basketball leagues
    basketball_leagues = [l for l in leagues_data if "/basketball/" in l.get("url", "")]
    print(f"Loaded {len(basketball_leagues)} basketball leagues from JSON.")

    print(f"Parsing FB doc: {FB_BASKETBALL_DOC}...")
    fb_parser = FBParser()
    fb_parser.feed(FB_BASKETBALL_DOC.read_text(encoding="utf-8"))
    fb_leagues = fb_parser.leagues
    print(f"Found {len(fb_leagues)} FB leagues (source).")

    print(f"Parsing FS doc: {FS_BASKETBALL_DOC}...")
    fs_parser = FSParser()
    fs_parser.feed(FS_BASKETBALL_DOC.read_text(encoding="utf-8"))
    fs_leagues = fs_parser.leagues
    print(f"Found {len(fs_leagues)} FS leagues (target).")

    # Bridge Map: Index FS by leagueId to get doc-style country names
    fs_doc_info = {l.league_id: l for l in fs_leagues}

    # Source Map: Index FB by normalized (country, name)
    fb_index = {}
    for l in fb_leagues:
        key = (l.country_norm, l.league_norm)
        fb_index[key] = l

    updated_count = 0
    mapped_count = 0
    already_mapped = 0
    unresolved = []

    print("\nStarting reconciliation...")
    for l in basketball_leagues:
        lid = l["league_id"]
        
        # 1. Determine canonical country and name
        l_name_raw = l["name"]
        l_name_norm = normalize_league(l_name_raw)
        
        canonical_country_norm = None
        if lid in fs_doc_info:
            canonical_country_norm = fs_doc_info[lid].country_norm
            l_name_norm = fs_doc_info[lid].league_norm
        else:
            # Fallback to country_code or existing data
            c_code = l.get("country_code", "").lower()
            canonical_country_norm = normalize_country(c_code)
            if not canonical_country_norm or len(canonical_country_norm) == 2:
                 canonical_country_norm = normalize_country(l.get("fb_country", ""))

        is_women = is_women_league(l_name_raw)
        matched_fb = None
        
        # 2. Try Exact Match (Country + Name)
        key = (canonical_country_norm, l_name_norm)
        if key in fb_index:
            matched_fb = fb_index[key]
            
        # 3. Try Alias Match
        if not matched_fb:
            alias_key = LEAGUE_ALIASES.get(key)
            if alias_key:
                # alias_key is actually the normalized (FB_Country, FB_League)
                # But my LEAGUE_ALIASES maps (FS_Country, FS_League) to (FB_Country, FB_League_RAW)
                # Let's normalize the value part to be safe
                fb_c, fb_l_raw = alias_key
                fb_l_norm = normalize_league(fb_l_raw)
                if (fb_c, fb_l_norm) in fb_index:
                    matched_fb = fb_index[(fb_c, fb_l_norm)]

        # 4. Try Fuzzy Match within same country
        if not matched_fb and canonical_country_norm:
            candidates = [f for f in fb_leagues if f.country_norm == canonical_country_norm and f.is_women == is_women]
            if candidates:
                names = [c.league_norm for c in candidates]
                matches = difflib.get_close_matches(l_name_norm, names, n=1, cutoff=0.85)
                if matches:
                    matched_fb = next(c for c in candidates if c.league_norm == matches[0])

        if matched_fb:
            # Check if this mapping is already applied
            if l.get("fb_tournament_id") == matched_fb.tournament_id and l.get("fb_url") == matched_fb.fb_url:
                already_mapped += 1
                mapped_count += 1
                continue

            # Apply mapping
            l["fb_league_name"] = matched_fb.league_raw
            l["fb_country"] = matched_fb.country_raw
            l["fb_category_id"] = matched_fb.category_id
            l["fb_tournament_id"] = matched_fb.tournament_id
            l["fb_url"] = matched_fb.fb_url
            l["fb_matched_tier"] = "T1"
            
            updated_count += 1
            mapped_count += 1
        else:
            unresolved.append(f"{canonical_country_norm or '??'} | {l_name_raw}")

    # Save updates
    if updated_count > 0:
        print(f"Updating {LEAGUES_JSON} with {updated_count} updates...")
        with open(LEAGUES_JSON, "w", encoding="utf-8") as f:
            json.dump(leagues_data, f, indent=2, ensure_ascii=False)
            f.write("\n")
    else:
        print("No updates applied.")

    print("\n" + "="*40)
    print("BASKETBALL RECONCILIATION SUMMARY")
    print("="*40)
    print(f"Total Basketball in JSON : {len(basketball_leagues)}")
    print(f"Already Mapped           : {already_mapped}")
    print(f"New Updates Applied      : {updated_count}")
    print(f"Total Mapped Now         : {mapped_count}")
    print(f"Unmapped Remaining       : {len(unresolved)}")
    print(f"Coverage                 : {mapped_count/len(basketball_leagues)*100:.1f}%")
    print("="*40)

    if unresolved:
        print("\nTOP UNMAPPED (First 20):")
        for r in unresolved[:20]:
            print(f"  - {r}")

if __name__ == "__main__":
    reconcile()
