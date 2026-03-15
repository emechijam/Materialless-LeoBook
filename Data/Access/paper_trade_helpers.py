# paper_trade_helpers.py: Paper trade persistence and outcome resolution.
# Part of LeoBook Data — Access Layer
# Imported by: outcome_reviewer.py, recommend_bets.py, db_helpers.py

from collections import defaultdict
from typing import Dict


def save_paper_trade(conn, trade: dict) -> None:
    """
    Upsert a paper trade record. On conflict (fixture_id, market_key),
    updates all non-outcome fields. Outcome fields (outcome_correct,
    simulated_pl, reviewed_at) are written only by outcome_reviewer.py.
    """
    cols = [
        "fixture_id", "trade_date", "created_at", "home_team", "away_team",
        "league_id", "match_date", "market_key", "market_name",
        "recommended_outcome", "live_odds", "synthetic_odds", "model_prob",
        "ev", "gated", "stairway_step", "simulated_stake", "simulated_payout",
        "rule_pick", "rl_pick", "ensemble_pick", "rl_confidence", "rule_confidence",
    ]
    vals = [trade.get(c) for c in cols]
    placeholders = ", ".join("?" * len(cols))
    col_str = ", ".join(cols)

    update_cols = [c for c in cols if c not in ("fixture_id", "market_key")]
    update_clause = ", ".join(f"{c} = excluded.{c}" for c in update_cols)

    sql = (
        f"INSERT INTO paper_trades ({col_str}) VALUES ({placeholders}) "
        f"ON CONFLICT(fixture_id, market_key) DO UPDATE SET {update_clause}"
    )
    conn.execute(sql, vals)
    conn.commit()


def update_paper_trade_outcome(conn, fixture_id: str, home_score: int, away_score: int) -> int:
    """
    Called by outcome_reviewer.py after a match finishes.
    Resolves all pending paper_trades for this fixture using
    derive_ground_truth() from market_space.py.

    Returns count of rows updated.
    """
    from Core.Intelligence.rl.market_space import derive_ground_truth
    from Core.Utils.constants import now_ng

    rows = conn.execute(
        "SELECT id, market_key, live_odds, synthetic_odds, simulated_stake "
        "FROM paper_trades WHERE fixture_id = ? AND outcome_correct IS NULL",
        (fixture_id,)
    ).fetchall()

    if not rows:
        return 0

    gt = derive_ground_truth(home_score, away_score)
    now_str = now_ng().isoformat()
    count = 0

    for row in rows:
        row_id = row[0]
        market_key = row[1]
        odds = row[2] or row[3] or 0.0
        stake = row[4] or 0.0

        correct = gt.get(market_key)
        if correct is None:
            continue

        outcome_int = 1 if correct else 0
        if correct:
            pl = stake * (odds - 1.0) if odds > 0 else 0.0
        else:
            pl = -stake

        conn.execute(
            "UPDATE paper_trades SET home_score=?, away_score=?, "
            "outcome_correct=?, simulated_pl=?, reviewed_at=? WHERE id=?",
            (home_score, away_score, outcome_int, round(pl, 2), now_str, row_id)
        )
        count += 1

    conn.commit()
    return count


def get_paper_trading_summary(conn) -> dict:
    """
    Returns aggregate stats over all paper_trades:
    total, pending, reviewed, accuracy, gated accuracy,
    simulated P&L, ROI, and per-market breakdown.
    """
    all_rows = conn.execute("SELECT * FROM paper_trades").fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM paper_trades LIMIT 0").description]

    records = [dict(zip(cols, r)) for r in all_rows]
    total = len(records)
    reviewed = [r for r in records if r.get("outcome_correct") is not None]
    pending = total - len(reviewed)
    correct = [r for r in reviewed if r.get("outcome_correct") == 1]

    gated_all = [r for r in records if r.get("gated") == 1]
    gated_reviewed = [r for r in reviewed if r.get("gated") == 1]
    gated_correct = [r for r in gated_reviewed if r.get("outcome_correct") == 1]

    total_pl = sum(r.get("simulated_pl", 0) or 0 for r in reviewed)
    total_stake = sum(r.get("simulated_stake", 0) or 0 for r in reviewed)

    by_market = defaultdict(lambda: {"count": 0, "correct": 0, "ev_sum": 0.0, "pl_sum": 0.0})
    for r in records:
        mk = r.get("market_key", "unknown")
        by_market[mk]["count"] += 1
        if r.get("outcome_correct") == 1:
            by_market[mk]["correct"] += 1
        by_market[mk]["ev_sum"] += r.get("ev", 0) or 0
        by_market[mk]["pl_sum"] += r.get("simulated_pl", 0) or 0

    market_summary = {}
    for mk, s in by_market.items():
        reviewed_in_mk = sum(1 for r in reviewed if r.get("market_key") == mk)
        market_summary[mk] = {
            "count": s["count"],
            "accuracy": (s["correct"] / reviewed_in_mk * 100) if reviewed_in_mk > 0 else 0.0,
            "avg_ev": s["ev_sum"] / s["count"] if s["count"] > 0 else 0.0,
            "total_pl": round(s["pl_sum"], 2),
        }

    return {
        "total_trades": total,
        "pending_review": pending,
        "reviewed_trades": len(reviewed),
        "correct_trades": len(correct),
        "accuracy": (len(correct) / len(reviewed) * 100) if reviewed else 0.0,
        "gated_trades": len(gated_all),
        "gated_accuracy": (len(gated_correct) / len(gated_reviewed) * 100) if gated_reviewed else 0.0,
        "total_simulated_pl": round(total_pl, 2),
        "roi": (total_pl / total_stake * 100) if total_stake > 0 else 0.0,
        "avg_stake": (total_stake / len(reviewed)) if reviewed else 0.0,
        "by_market": market_summary,
    }


__all__ = [
    "save_paper_trade",
    "update_paper_trade_outcome",
    "get_paper_trading_summary",
]
