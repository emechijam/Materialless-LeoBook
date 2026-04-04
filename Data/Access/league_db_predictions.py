# league_db_predictions.py: Prediction CRUD operations for the LeoBook SQLite database.
# Part of LeoBook Data — Access Layer
#
# Functions: upsert_prediction(), get_predictions(), update_prediction()
# Called by: prediction_pipeline.py, recommend_bets.py, outcome_reviewer.py

import json
import sqlite3
from typing import List, Dict, Any, Optional
from Core.Utils.constants import now_ng


def upsert_prediction(conn: sqlite3.Connection, data: Dict[str, Any],
                      user_id: str, commit: bool = True):
    """Insert or update a prediction row scoped to user_id."""
    now = now_ng().isoformat()
    # Normalize over_2.5 → over_2_5
    if "over_2.5" in data:
        data["over_2_5"] = data.pop("over_2.5")

    cols = [
        "fixture_id", "user_id", "date", "match_time", "country_league",
        "home_team", "away_team", "home_team_id", "away_team_id",
        "prediction", "confidence", "reason",
        "home_form_n", "away_form_n",
        "h2h_count", "actual_score", "outcome_correct",
        "status", "match_link", "odds",
        "market_reliability_score", "home_crest_url", "away_crest_url",
        "recommendation_score", "h2h_fixture_ids", "form_fixture_ids",
        "standings_snapshot", "league_stage", "generated_at",
        "home_score", "away_score", "chosen_market", "market_id",
        "rule_explanation", "override_reason", "statistical_edge",
        "pure_model_suggestion",
        "form_home", "form_away", "h2h_summary", "standings_home", "standings_away",
        "rule_engine_decision", "rl_decision", "ensemble_weights", "rec_qualifications",
        "is_available", "last_updated",
    ]
    values = {c: data.get(c) for c in cols}
    values["user_id"] = user_id
    values["last_updated"] = now

    json_fields = (
        "h2h_fixture_ids", "form_fixture_ids", "standings_snapshot",
        "form_home", "form_away", "h2h_summary", "standings_home", "standings_away",
        "ensemble_weights", "rec_qualifications", "rl_decision"
    )
    for jf in json_fields:
        if jf in values and values[jf] is not None and not isinstance(values[jf], str):
            values[jf] = json.dumps(values[jf])

    present = {k: v for k, v in values.items() if v is not None}
    col_str = ", ".join(present.keys())
    placeholders = ", ".join([f":{k}" for k in present.keys()])
    updates = ", ".join(
        [f"{k} = excluded.{k}" for k in present.keys()
         if k not in ("fixture_id", "user_id")]
    )

    conn.execute(
        f"INSERT INTO predictions ({col_str}) VALUES ({placeholders}) "
        f"ON CONFLICT(fixture_id, user_id) DO UPDATE SET {updates}",
        present,
    )
    if commit:
        conn.commit()


def get_predictions(conn: sqlite3.Connection, user_id: str,
                    status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get predictions for a user, optionally filtered by status."""
    if status:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE user_id = ? AND status = ?",
            (user_id, status),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE user_id = ?", (user_id,)
        ).fetchall()
    return [dict(r) for r in rows]


def update_prediction(conn: sqlite3.Connection, fixture_id: str, user_id: str,
                      updates: Dict[str, Any], commit: bool = True):
    """Update specific fields on a prediction scoped to user_id."""
    now = now_ng().isoformat()
    updates["last_updated"] = now
    set_clause = ", ".join([f"{k} = :{k}" for k in updates.keys()])
    updates["fixture_id"] = fixture_id
    updates["user_id"] = user_id
    conn.execute(
        f"UPDATE predictions SET {set_clause} "
        f"WHERE fixture_id = :fixture_id AND user_id = :user_id",
        updates,
    )
    if commit:
        conn.commit()
