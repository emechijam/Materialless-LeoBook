# rl_config_crud.py: CRUD operations for the user_rl_config table.
# Part of LeoBook Data — Access Layer
#
# Functions: get_rl_config(), save_rl_config(), update_rl_config_field(),
#            delete_rl_config(), list_rl_configs()
# Called by: Scripts, Core/Intelligence, Leo.py chapter sequencing

"""
user_rl_config CRUD
Per-user ML/RL configuration: min_confidence, min/max odds, risk_appetite,
market_weights (JSON), max_stake_pct, enabled_sports.

One row per user_id (PRIMARY KEY). All writes upsert.
"""

import json
import sqlite3
from datetime import datetime as dt
from typing import Any, Dict, List, Optional


# ── Defaults (mirror schema defaults) ───────────────────────────────────────

DEFAULT_RL_CONFIG: Dict[str, Any] = {
    "market_weights":  None,          # JSON blob or None
    "min_confidence":  0.6,
    "min_odds":        1.5,
    "max_odds":        8.0,
    "risk_appetite":   "medium",      # low | medium | high
    "max_stake_pct":   0.05,
    "enabled_sports":  "football,basketball",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    if d.get("market_weights") and isinstance(d["market_weights"], str):
        try:
            d["market_weights"] = json.loads(d["market_weights"])
        except (json.JSONDecodeError, ValueError):
            d["market_weights"] = None
    return d


def _encode_weights(weights) -> Optional[str]:
    if weights is None:
        return None
    if isinstance(weights, str):
        return weights
    return json.dumps(weights)


# ── CRUD ─────────────────────────────────────────────────────────────────────

def get_rl_config(conn: sqlite3.Connection, user_id: str) -> Dict[str, Any]:
    """
    Return the rl config row for user_id, or the default config dict if absent.
    Never raises — always returns a usable dict.
    """
    try:
        row = conn.execute(
            "SELECT * FROM user_rl_config WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row:
            return _row_to_dict(row)
    except Exception as e:
        print(f"  [RLConfig] get failed for {user_id}: {e}")

    # Return defaults with the requested user_id filled in
    return {"user_id": user_id, **DEFAULT_RL_CONFIG, "last_updated": None}


def save_rl_config(conn: sqlite3.Connection, user_id: str, config: Dict[str, Any]) -> bool:
    """
    Upsert a full rl config row for user_id.
    config may omit keys — missing keys fall back to DEFAULT_RL_CONFIG values.

    Returns True on success, False on error.
    """
    merged = {**DEFAULT_RL_CONFIG, **config}
    now = dt.utcnow().strftime("%Y-%m-%d %H:%M:%S")

    try:
        conn.execute(
            """
            INSERT INTO user_rl_config
                (user_id, market_weights, min_confidence, min_odds, max_odds,
                 risk_appetite, max_stake_pct, enabled_sports, last_updated)
            VALUES (?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                market_weights  = excluded.market_weights,
                min_confidence  = excluded.min_confidence,
                min_odds        = excluded.min_odds,
                max_odds        = excluded.max_odds,
                risk_appetite   = excluded.risk_appetite,
                max_stake_pct   = excluded.max_stake_pct,
                enabled_sports  = excluded.enabled_sports,
                last_updated    = excluded.last_updated
            """,
            (
                user_id,
                _encode_weights(merged.get("market_weights")),
                float(merged["min_confidence"]),
                float(merged["min_odds"]),
                float(merged["max_odds"]),
                str(merged["risk_appetite"]),
                float(merged["max_stake_pct"]),
                str(merged["enabled_sports"]),
                now,
            ),
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"  [RLConfig] save failed for {user_id}: {e}")
        return False


def update_rl_config_field(
    conn: sqlite3.Connection,
    user_id: str,
    field: str,
    value: Any,
) -> bool:
    """
    Patch a single field on an existing rl config row.
    If no row exists, creates one with defaults first.

    Allowed fields: market_weights, min_confidence, min_odds, max_odds,
                    risk_appetite, max_stake_pct, enabled_sports
    """
    _ALLOWED = {
        "market_weights", "min_confidence", "min_odds", "max_odds",
        "risk_appetite", "max_stake_pct", "enabled_sports",
    }
    if field not in _ALLOWED:
        print(f"  [RLConfig] update_field: unknown field '{field}'")
        return False

    # Ensure row exists
    existing = get_rl_config(conn, user_id)
    existing["user_id"] = user_id
    existing[field] = value
    return save_rl_config(conn, user_id, existing)


def delete_rl_config(conn: sqlite3.Connection, user_id: str) -> bool:
    """
    Delete the rl config row for user_id.
    Returns True if a row was deleted, False otherwise.
    """
    try:
        cursor = conn.execute(
            "DELETE FROM user_rl_config WHERE user_id = ?",
            (user_id,),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"  [RLConfig] delete failed for {user_id}: {e}")
        return False


def list_rl_configs(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """
    Return all rows from user_rl_config (admin/debug use).
    """
    try:
        rows = conn.execute(
            "SELECT * FROM user_rl_config ORDER BY last_updated DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as e:
        print(f"  [RLConfig] list failed: {e}")
        return []


def apply_rl_config_to_pipeline(
    config: Dict[str, Any],
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Filter a list of prediction candidates using the user's rl config.

    Applies:
    - min_confidence → drops rows whose numeric confidence is below threshold
    - min_odds / max_odds → drops rows outside odds window
    - enabled_sports → drops rows whose sport is not in the list

    This is a pure function — no DB access.
    """
    min_conf    = float(config.get("min_confidence", DEFAULT_RL_CONFIG["min_confidence"]))
    min_odds    = float(config.get("min_odds",       DEFAULT_RL_CONFIG["min_odds"]))
    max_odds    = float(config.get("max_odds",       DEFAULT_RL_CONFIG["max_odds"]))
    sports_str  = config.get("enabled_sports",       DEFAULT_RL_CONFIG["enabled_sports"]) or ""
    enabled     = {s.strip().lower() for s in sports_str.split(",") if s.strip()}

    # Confidence label → numeric mapping (mirrors AdaptiveRecommender)
    CONF_MAP = {"very high": 0.80, "high": 0.65, "medium": 0.50, "low": 0.35}

    filtered = []
    for c in candidates:
        # Sport gate
        sport = (c.get("sport") or "football").lower()
        if enabled and sport not in enabled:
            continue

        # Odds gate
        try:
            odds = float(c.get("booking_odds") or c.get("odds") or 0)
            if odds and not (min_odds <= odds <= max_odds):
                continue
        except (TypeError, ValueError):
            pass

        # Confidence gate
        conf_label = (c.get("confidence") or "").lower()
        conf_val = CONF_MAP.get(conf_label, 0.0)
        if conf_val and conf_val < min_conf:
            continue

        filtered.append(c)

    return filtered
