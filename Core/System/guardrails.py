# guardrails.py: Safety guardrails for LeoBook betting pipeline.
# Part of LeoBook Core — System
#
# Functions: is_dry_run(), enable_dry_run(), check_kill_switch(),
#            check_balance_sanity(), check_daily_loss_limit(),
#            run_all_pre_bet_checks()
# Classes:   StaircaseTracker

"""
Safety Guardrails Module — Items 5-10
All six guardrails that MUST pass before any real bet placement.
Every guardrail is scoped to a user_id — no single-user fallback.
"""

import os
from pathlib import Path
from Core.Utils.constants import now_ng

# ── Configuration (overridable via .env) ──────────────────────────────────────

_REPO_ROOT = Path(__file__).parent.parent.parent
KILL_SWITCH_FILE = os.getenv("KILL_SWITCH_FILE", str(_REPO_ROOT / "STOP_BETTING"))
MIN_BALANCE = float(os.getenv("MIN_BALANCE_BEFORE_BET", 500))
DAILY_LOSS_LIMIT = float(os.getenv("DAILY_LOSS_LIMIT", 5000))
STAIRWAY_SEED = float(os.getenv("STAIRWAY_SEED", 1000))

# ── Item 5: Dry-Run Flag ─────────────────────────────────────────────────────

_DRY_RUN = False


def enable_dry_run():
    """Call from Leo.py when --dry-run is active."""
    global _DRY_RUN
    _DRY_RUN = True
    print("  [GUARDRAIL] Dry-run mode ENABLED. No real bets will be placed.")


def is_dry_run() -> bool:
    """Check if dry-run mode is active."""
    return _DRY_RUN


# ── Item 6: Kill Switch ──────────────────────────────────────────────────────

def check_kill_switch() -> bool:
    """Returns True if STOP_BETTING file exists → betting should HALT."""
    exists = os.path.exists(KILL_SWITCH_FILE)
    if exists:
        print(f"  [KILL SWITCH] File detected: {KILL_SWITCH_FILE}")
        print(f"  [KILL SWITCH] All betting operations HALTED.")
        print(f"  [KILL SWITCH] Delete the file to resume: del {KILL_SWITCH_FILE}")
    return exists


# ── Items 7 & 8: Staircase State Machine ─────────────────────────────────────

# The 7-step compounding table from PROJECT_STAIRWAY.md
STAIRWAY_TABLE = [
    {"step": 1, "stake": 1000,    "odds_target": 4.0, "payout": 4000},
    {"step": 2, "stake": 4000,    "odds_target": 4.0, "payout": 16000},
    {"step": 3, "stake": 16000,   "odds_target": 4.0, "payout": 64000},
    {"step": 4, "stake": 64000,   "odds_target": 4.0, "payout": 256000},
    {"step": 5, "stake": 256000,  "odds_target": 4.0, "payout": 1024000},
    {"step": 6, "stake": 1024000, "odds_target": 4.0, "payout": 4096000},
    {"step": 7, "stake": 2048000, "odds_target": 4.0, "payout": 2187000},
]


class StaircaseTracker:
    """
    Tracks the current position in the 7-step Stairway compounding sequence
    for a specific user. Persists state in SQLite `stairway_state` table
    (one row per user_id).

    Rules (from PROJECT_STAIRWAY.md):
      - Win  → advance to next step (stake = previous payout)
      - Loss → reset to step 1 (₦1,000 seed)
      - Step 7 win → cycle complete, withdraw + reset
    """

    def __init__(self, user_id: str):
        if not user_id:
            raise ValueError("StaircaseTracker requires a non-empty user_id.")
        self._user_id = user_id
        from Data.Access.league_db import get_connection
        self._conn = get_connection()
        self._ensure_row()

    def _ensure_row(self):
        row = self._conn.execute(
            "SELECT current_step FROM stairway_state WHERE user_id = ?",
            (self._user_id,),
        ).fetchone()
        if not row:
            self._conn.execute(
                "INSERT INTO stairway_state (user_id, current_step, last_updated, cycle_count) "
                "VALUES (?, 1, ?, 0)",
                (self._user_id, now_ng().isoformat()),
            )
            self._conn.commit()

    @property
    def current_step(self) -> int:
        row = self._conn.execute(
            "SELECT current_step FROM stairway_state WHERE user_id = ?",
            (self._user_id,),
        ).fetchone()
        return row[0] if row else 1

    def get_step_info(self) -> dict:
        """Return the Stairway table entry for the current step."""
        step = self.current_step
        idx = min(step, len(STAIRWAY_TABLE)) - 1
        return STAIRWAY_TABLE[idx]

    def get_max_stake(self) -> int:
        """Return the maximum allowed stake for the current step."""
        return int(self.get_step_info()["stake"])

    def get_current_stake(self) -> int:
        """Alias for get_max_stake — the Stairway stake IS the bet amount."""
        return self.get_max_stake()

    def advance(self):
        """Win: move to next step. If at step 7, complete the cycle and reset."""
        step = self.current_step
        now = now_ng().isoformat()

        if step >= 7:
            self._conn.execute(
                "UPDATE stairway_state SET current_step = 1, last_updated = ?, "
                "last_result = 'CYCLE_COMPLETE', cycle_count = cycle_count + 1 "
                "WHERE user_id = ?",
                (now, self._user_id),
            )
            print(f"  [STAIRWAY] CYCLE COMPLETE! 7-step streak achieved. Resetting to step 1.")
        else:
            self._conn.execute(
                "UPDATE stairway_state SET current_step = ?, last_updated = ?, "
                "last_result = 'WIN' WHERE user_id = ?",
                (step + 1, now, self._user_id),
            )
            next_info = STAIRWAY_TABLE[step]
            print(f"  [STAIRWAY] WIN at step {step}. Advancing to step {step + 1} "
                  f"(stake: ₦{next_info['stake']:,})")

        self._conn.commit()

    def reset(self):
        """Loss: reset to step 1 with fresh ₦1,000 seed."""
        now = now_ng().isoformat()
        step = self.current_step
        self._conn.execute(
            "UPDATE stairway_state SET current_step = 1, last_updated = ?, "
            "last_result = 'LOSS_RESET' WHERE user_id = ?",
            (now, self._user_id),
        )
        self._conn.commit()
        print(f"  [STAIRWAY] LOSS at step {step}. Reset to step 1 (₦{STAIRWAY_TABLE[0]['stake']:,})")

    def status(self) -> str:
        """Human-readable status string."""
        info = self.get_step_info()
        return (f"Step {self.current_step}/7 | "
                f"Stake: ₦{info['stake']:,} | "
                f"Target odds: {info['odds_target']} | "
                f"Payout: ₦{info['payout']:,}")


# ── Item 9: Balance Sanity Check ─────────────────────────────────────────────

def check_balance_sanity(balance: float) -> bool:
    """Returns True if balance is above the minimum threshold."""
    if balance < MIN_BALANCE:
        print(f"  [GUARDRAIL] Balance ₦{balance:,.0f} is below minimum ₦{MIN_BALANCE:,.0f}. Betting blocked.")
        return False
    return True


# ── Item 10: Daily Loss Limit ────────────────────────────────────────────────

def check_daily_loss_limit(user_id: str, conn=None) -> bool:
    """
    Sum today's BET_PLACEMENT losses from audit_log for user_id.
    Returns True if still within the daily limit.
    """
    if not user_id:
        raise ValueError("check_daily_loss_limit requires a non-empty user_id.")
    if conn is None:
        from Data.Access.league_db import get_connection
        conn = get_connection()

    today = now_ng().strftime("%Y-%m-%d")

    try:
        row = conn.execute("""
            SELECT COALESCE(SUM(
                CASE WHEN CAST(balance_before AS REAL) > CAST(balance_after AS REAL)
                     THEN CAST(balance_before AS REAL) - CAST(balance_after AS REAL)
                     ELSE 0
                END
            ), 0) as total_loss
            FROM audit_log
            WHERE user_id = ?
              AND event_type = 'BET_PLACEMENT'
              AND timestamp LIKE ?
        """, (user_id, f"{today}%")).fetchone()

        total_loss = float(row[0]) if row else 0.0

        if total_loss >= DAILY_LOSS_LIMIT:
            print(f"  [GUARDRAIL] Daily loss limit reached: ₦{total_loss:,.0f} / ₦{DAILY_LOSS_LIMIT:,.0f}. Betting HALTED for today.")
            return False

        remaining = DAILY_LOSS_LIMIT - total_loss
        print(f"  [GUARDRAIL] Daily loss budget: ₦{remaining:,.0f} remaining (₦{total_loss:,.0f} lost today)")
        return True

    except Exception as e:
        print(f"  [GUARDRAIL WARNING] Could not check daily loss limit: {e}")
        print(f"  [GUARDRAIL WARNING] Proceeding with caution — ensure audit_log table exists.")
        return True


# ── Master Pre-Bet Check ─────────────────────────────────────────────────────

def run_all_pre_bet_checks(user_id: str, conn=None, balance: float = 0.0) -> tuple:
    """
    Run all safety guardrails in sequence for user_id.
    Returns (ok: bool, reason: str).
    If ok is False, betting MUST NOT proceed.
    """
    if not user_id:
        return False, "NO_USER: user_id is required for all guardrail checks."

    # 1. Dry-run check
    if is_dry_run():
        return False, "DRY_RUN: Dry-run mode is active"

    # 2. Kill switch
    if check_kill_switch():
        return False, "KILL_SWITCH: STOP_BETTING file detected"

    # 3. Balance sanity
    if balance is not None and not check_balance_sanity(balance):
        return False, f"LOW_BALANCE: Balance ₦{balance:,.0f} below minimum ₦{MIN_BALANCE:,.0f}"

    # 4. Daily loss limit
    if not check_daily_loss_limit(user_id, conn):
        return False, "DAILY_LOSS_LIMIT: Today's loss limit exceeded"

    # 5. Staircase sanity
    try:
        tracker = StaircaseTracker(user_id)
        print(f"  [GUARDRAIL] Stairway status: {tracker.status()}")
    except Exception as e:
        return False, f"STAIRWAY_ERROR: Cannot initialize staircase tracker: {e}"

    print("  [GUARDRAIL] ✓ All pre-bet checks passed.")
    return True, "ALL_CLEAR"
