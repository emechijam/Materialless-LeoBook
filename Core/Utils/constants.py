import os
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ── Timezone: Africa/Lagos (WAT = UTC+1) ────────────────────────────────────
# All timestamps across the system MUST use this timezone for consistency
# regardless of platform (local Windows, GitHub Codespaces, Supabase).
TZ_NG = timezone(timedelta(hours=1))  # West Africa Time (WAT)
TZ_NG_NAME = "WAT"   # Human-readable label for log timestamps.
                     # Change this if TZ_NG ever changes — logs follow automatically.


def now_ng() -> datetime:
    """Return current Nigerian time (Africa/Lagos, WAT = UTC+1)."""
    return datetime.now(TZ_NG)

# Timeout Constants (in milliseconds)
NAVIGATION_TIMEOUT = 180000  # 3 minutes for page navigation
WAIT_FOR_LOAD_STATE_TIMEOUT = 90000  # 1.5 minutes for load state operations
STANDINGS_LOAD_TIMEOUT = 20000  # 20 seconds for standings (supplementary data)

# Financial Settings
DEFAULT_STAKE = float(os.getenv("DEFAULT_STAKE", 1.0))
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "$")

# Concurrency Control
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", 4))

# Browser / Mobile Settings
FB_MOBILE_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1"
FB_MOBILE_VIEWPORT = {'width': 375, 'height': 612}

# ── Prediction Engine Thresholds ─────────────────────────────────────────────
# Data contract: minimum form matches required for prediction eligibility.
# Any fixture with fewer results for either team is rejected as incomplete.
MIN_FORM_MATCHES = 5

# xG gap needed to credit one team with a genuine advantage
XG_ADVANTAGE_THRESHOLD = 0.5
# xG gap narrow enough to signal a likely draw
XG_DRAW_THRESHOLD = 0.3
# xG gap large enough to invalidate a contrary win prediction outright
XG_CONTRADICTION_THRESHOLD = 1.25

# Fallback xG values used when a team has no form data (league averages)
XG_HOME_FALLBACK = 1.4
XG_AWAY_FALLBACK = 1.1
# Below this raw xG value, treat the team as having no data and use the fallback
XG_MIN_THRESHOLD = 0.05

# Recommendation score composition
REC_SCORE_BASE_WEIGHT = 85       # confidence (0–1) × this = base score (0–85)
XG_HIGH_TOTAL_THRESHOLD = 2.5    # total xG above this awards a +10 bonus

# Both-Teams-To-Score label thresholds
BTTS_YES_THRESHOLD = 0.60        # Probability above → label "YES"
BTTS_NO_THRESHOLD  = 0.40        # Probability below → label "NO"

# Over 2.5 Goals label thresholds
OVER25_YES_THRESHOLD = 0.65      # Probability above → label "YES"
OVER25_NO_THRESHOLD  = 0.45      # Probability below → label "NO"

# Minimum probability for a correct-score entry to appear in top-scores list
CORRECT_SCORE_MIN_PROB = 0.03

# ── Odds Harvesting ───────────────────────────────────────────────────────────
# Number of leagues processed in one browser batch during odds harvesting
ODDS_HARVEST_BATCH_SIZE = 25
# Playwright page-navigation timeout in milliseconds
ODDS_PAGE_TIMEOUT_MS = 25_000
# Seconds to sleep after page load before beginning extraction
ODDS_PAGE_LOAD_DELAY = 1.5
# Skip matches whose kick-off is within this many hours of now
IMMINENT_MATCH_CUTOFF_HOURS = 0.5

# ── LeoBook Version ──────────────────────────────────────────────────────────
# Increment both on every release. Referenced by lifecycle.py session header
# and any other version-stamped output. Do NOT hardcode elsewhere.
LEOBOOK_VERSION = "9.6.1"
LEOBOOK_CODENAME = "Stairway Engine"
