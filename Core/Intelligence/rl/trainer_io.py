# trainer_io.py: Historical vision-data building, online updates, and persistence.
# Part of LeoBook Core — Intelligence (RL Engine)
# Mixed into RLTrainer via TrainerIOMixin.

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class TrainerIOMixin:
    """
    Data-loading, online-update, and persistence methods.
    Requires self.model, self.registry, self.device, self.active_phase from RLTrainer.
    """

    # -------------------------------------------------------------------
    # Historical vision data builder
    # -------------------------------------------------------------------

    def _build_training_vision_data(
        self, conn, match_date: str, league_id: str,
        home_team_id: str, home_team_name: str,
        away_team_id: str, away_team_name: str,
        season: str = None,
    ) -> Dict[str, Any]:
        """
        Build a vision_data dict from historical fixtures for training.
        Uses ONLY data before match_date (no future leakage).
        """
        from Data.Access.league_db import computed_standings

        home_form = self._get_team_form(conn, home_team_id, home_team_name, match_date)
        away_form = self._get_team_form(conn, away_team_id, away_team_name, match_date)
        h2h = self._get_h2h(conn, home_team_id, away_team_id, match_date)

        standings = []
        if league_id:
            try:
                standings = computed_standings(
                    conn=conn, league_id=league_id,
                    season=season, before_date=match_date
                )
            except Exception:
                standings = []

        # --- ALL-OR-NOTHING CONTRACT ENFORCEMENT ---
        hfn = len(home_form)
        afn = len(away_form)
        st_n = len(standings)
        is_complete = (hfn >= 5 and afn >= 5 and st_n > 0)

        return {
            "is_complete": is_complete,
            "h2h_data": {
                "home_team": home_team_name,
                "away_team": away_team_name,
                "home_last_10_matches": home_form,
                "away_last_10_matches": away_form,
                "head_to_head": h2h,
                "country_league": league_id,
            },
            "standings": standings,
        }

    def _get_team_form(self, conn, team_id: str, team_name: str,
                       before_date: str) -> List[Dict]:
        """Get last 10 matches for a team before a given date."""
        cursor = conn.execute("""
            SELECT date, home_team_name, away_team_name, home_score, away_score
            FROM schedules
            WHERE (home_team_id = ? OR away_team_id = ?)
              AND date < ?
              AND home_score IS NOT NULL AND away_score IS NOT NULL
              AND home_score != '' AND away_score != ''
              AND (match_status = 'finished' OR match_status IS NULL)
            ORDER BY date DESC
            LIMIT 10
        """, (team_id, team_id, before_date))

        matches = []
        for row in cursor.fetchall():
            hs, as_ = int(row[3] or 0), int(row[4] or 0)
            winner = "Home" if hs > as_ else "Away" if as_ > hs else "Draw"
            matches.append({
                "date": row[0],
                "home": row[1],
                "away": row[2],
                "score": f"{hs}-{as_}",
                "winner": winner,
            })
        return matches

    def _get_h2h(self, conn, home_id: str, away_id: str,
                 before_date: str) -> List[Dict]:
        """Get H2H matches between two teams before a given date (540-day window)."""
        cutoff_date = (datetime.strptime(before_date, "%Y-%m-%d")
                       - timedelta(days=540)).strftime("%Y-%m-%d")

        cursor = conn.execute("""
            SELECT date, home_team_name, away_team_name, home_score, away_score
            FROM schedules
            WHERE ((home_team_id = ? AND away_team_id = ?)
                OR (home_team_id = ? AND away_team_id = ?))
              AND date < ?
              AND date >= ?
              AND home_score IS NOT NULL AND away_score IS NOT NULL
              AND home_score != '' AND away_score != ''
              AND (match_status = 'finished' OR match_status IS NULL)
            ORDER BY date DESC
            LIMIT 10
        """, (home_id, away_id, away_id, home_id, before_date, cutoff_date))

        matches = []
        for row in cursor.fetchall():
            hs, as_ = int(row[3] or 0), int(row[4] or 0)
            winner = "Home" if hs > as_ else "Away" if as_ > hs else "Draw"
            matches.append({
                "date": row[0],
                "home": row[1],
                "away": row[2],
                "score": f"{hs}-{as_}",
                "winner": winner,
            })
        return matches

    # -------------------------------------------------------------------
    # Online update (from new prediction outcomes)
    # -------------------------------------------------------------------

    def update_from_outcomes(self, reviewed_predictions: List[Dict[str, Any]]):
        """
        Online learning from new prediction outcomes.
        Called after outcome_reviewer completes a batch.

        FIX-4: active_phase is explicitly set to self.active_phase before calling
        train_step, so online updates never silently use the wrong reward function.
        """
        from .feature_encoder import FeatureEncoder

        if not reviewed_predictions:
            return

        self.load()
        updated = 0

        for pred in reviewed_predictions:
            if pred.get("outcome_correct") not in ("True", "False", "1", "0"):
                continue

            is_correct = pred.get("outcome_correct") in ("True", "1")

            vision_data = {
                "h2h_data": {
                    "home_team": pred.get("home_team", ""),
                    "away_team": pred.get("away_team", ""),
                    "home_last_10_matches": [],
                    "away_last_10_matches": [],
                    "head_to_head": [],
                    "country_league": pred.get("country_league", "GLOBAL"),
                },
                "standings": [],
            }

            features = FeatureEncoder.encode(vision_data)

            league_id = pred.get("country_league", "GLOBAL")
            home_tid = pred.get("home_team_id", "GLOBAL")
            away_tid = pred.get("away_team_id", "GLOBAL")

            l_idx = self.registry.get_league_idx(league_id)
            h_idx = self.registry.get_team_idx(home_tid)
            a_idx = self.registry.get_team_idx(away_tid)

            outcome = {
                "result": "home_win" if is_correct else "draw",
                "home_score": int(pred.get("home_score", 0) or 0),
                "away_score": int(pred.get("away_score", 0) or 0),
            }

            self.train_step(
                features, l_idx, h_idx, a_idx,
                outcome=outcome,
                active_phase=self.active_phase,
            )
            updated += 1

        if updated > 0:
            self.save()
            print(f"  [RL] Updated model from {updated} new outcomes")

    # -------------------------------------------------------------------
    # Persistence
    # -------------------------------------------------------------------

    def save(self):
        """Save model and registry."""
        import os, torch
        from pathlib import Path
        models_dir = Path(__file__).parent.parent.parent.parent / "Data" / "Store" / "models"
        base_path = models_dir / "leobook_base.pth"
        os.makedirs(models_dir, exist_ok=True)
        torch.save(self.model.state_dict(), base_path)
        self.registry.save()

    def load(self):
        """Load model and registry if they exist."""
        import torch
        from pathlib import Path
        models_dir = Path(__file__).parent.parent.parent.parent / "Data" / "Store" / "models"
        base_path = models_dir / "leobook_base.pth"
        if base_path.exists():
            try:
                state_dict = torch.load(base_path, map_location=self.device, weights_only=True)
                self.model.load_state_dict(state_dict, strict=False)
            except Exception as e:
                print(f"  [RL] Could not load model: {e}")
        self.registry = self.registry.__class__()


__all__ = ["TrainerIOMixin"]
