# db_helpers_import.py: Data ingestion helpers for LeoBook SQLite.
# Part of LeoBook Data — Access Layer
#
# Split from db_helpers.py (v9.6.0) — prediction/schedule/standings/team write functions.
# All callers should use league_db.py (facade) or db_helpers.py (backward-compat re-exports).

"""
DB Helpers Import Module
High-level write/read helpers for predictions, schedules, standings, teams, and leagues.
All data persisted to leobook.db via league_db.py.
"""

import logging
from datetime import datetime as dt
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

from Data.Access.league_db import (
    upsert_prediction, update_prediction, get_predictions,
    upsert_fixture, bulk_upsert_fixtures,
    upsert_standing, get_standings as _get_standings_db,
    upsert_league, upsert_team, upsert_live_score,
    query_all,
)


# Imported lazily from db_helpers to avoid circular imports
def _get_conn_ref():
    from Data.Access.db_helpers import _get_conn
    return _get_conn()


# ─── Predictions ───

def save_prediction(match_data: Dict[str, Any], prediction_result: Dict[str, Any], commit: bool = True):
    """UPSERTs a prediction into the database."""
    fixture_id = match_data.get('fixture_id') or match_data.get('id')
    if not fixture_id or fixture_id == 'unknown':
        print(f"   [Warning] Skipping prediction save: Missing unique fixture_id for "
              f"{match_data.get('home_team')} v {match_data.get('away_team')}")
        return

    date = match_data.get('date', dt.now().strftime("%Y-%m-%d"))

    row = {
        'fixture_id': fixture_id,
        'date': date,
        'match_time': match_data.get('match_time') or match_data.get('time', '00:00'),
        'country_league': match_data.get('country_league', 'Unknown'),
        'home_team': match_data.get('home_team', 'Unknown'),
        'away_team': match_data.get('away_team', 'Unknown'),
        'home_team_id': match_data.get('home_team_id', 'unknown'),
        'away_team_id': match_data.get('away_team_id', 'unknown'),
        'prediction': prediction_result.get('type', 'SKIP'),
        'confidence': prediction_result.get('confidence', 'Low'),
        'reason': " | ".join(prediction_result.get('reason', [])),
        'h2h_count': str(prediction_result.get('h2h_n', 0)),
        'home_form_n': str(prediction_result.get('home_form_n', 0)),
        'away_form_n': str(prediction_result.get('away_form_n', 0)),
        'generated_at': dt.now().isoformat(),
        'status': 'pending',
        'match_link': f"{match_data.get('match_link', '')}",
        'odds': str(prediction_result.get('odds', '')),
        'market_reliability_score': str(prediction_result.get('market_reliability', 0.0)),
        'home_crest_url': get_team_crest(match_data.get('home_team_id'), match_data.get('home_team')),
        'away_crest_url': get_team_crest(match_data.get('away_team_id'), match_data.get('away_team')),
        'recommendation_score': str(prediction_result.get('recommendation_score', 0)),
        'h2h_fixture_ids': prediction_result.get('h2h_fixture_ids', []),
        'form_fixture_ids': prediction_result.get('form_fixture_ids', []),
        'standings_snapshot': prediction_result.get('standings_snapshot', []),
        'league_stage': match_data.get('league_stage', ''),
        # --- Rule Engine Manager Fields ---
        'chosen_market': prediction_result.get('chosen_market'),
        'market_id': prediction_result.get('market_id'),
        'rule_explanation': prediction_result.get('rule_explanation'),
        'override_reason': prediction_result.get('override_reason'),
        'statistical_edge': prediction_result.get('statistical_edge', 0.0),
        'pure_model_suggestion': prediction_result.get('pure_model_suggestion'),
        # --- Rich Rationale Fields (JSON strings handled by league_db) ---
        'form_home': prediction_result.get('form_home', {}),
        'form_away': prediction_result.get('form_away', {}),
        'h2h_summary': prediction_result.get('h2h_summary', {}),
        'standings_home': prediction_result.get('standings_home', {}),
        'standings_away': prediction_result.get('standings_away', {}),
        'rule_engine_decision': prediction_result.get('rule_engine_decision'),
        'rl_decision': prediction_result.get('rl_decision'),
        'ensemble_weights': prediction_result.get('ensemble_weights', {}),
        'rec_qualifications': prediction_result.get('rec_qualifications', {}),
        'last_updated': dt.now().isoformat(),
        # v9.6.0 — sport (basketball / football; defaults to football for all existing predictions)
        'sport': match_data.get('sport') or prediction_result.get('sport', 'football'),
        # v9.8.0 — period targeting (basketball O/U markets)
        'market_line':   prediction_result.get('market_line'),
        'market_period': prediction_result.get('market_period', 'full'),
    }

    if not row['odds'] and row['prediction'] != 'SKIP':
        logger.warning(
            f"  [DBHelpers] Non-SKIP prediction saved with empty odds | "
            f"fixture: {row['fixture_id']} | "
            f"market: {prediction_result.get('chosen_market')}"
        )

    upsert_prediction(_get_conn_ref(), row, commit=commit)


def update_prediction_status(match_id: str, date: str, new_status: str, commit: bool = True, **kwargs):
    """Updates the status and optional fields for a prediction."""
    updates = {'status': new_status}
    updates.update(kwargs)
    update_prediction(_get_conn_ref(), match_id, updates, commit=commit)


def backfill_prediction_entry(fixture_id: str, updates: Dict[str, str]):
    """Partially updates an existing prediction row. Only updates empty/Unknown fields."""
    if not fixture_id or not updates:
        return False

    conn = _get_conn_ref()
    row = conn.execute("SELECT * FROM predictions WHERE fixture_id = ?", (fixture_id,)).fetchone()
    if not row:
        return False

    filtered = {}
    for key, value in updates.items():
        if value:
            current = row[key] if key in row.keys() else ''
            current = str(current).strip() if current else ''
            if not current or current in ('Unknown', 'N/A', 'unknown', 'None', ''):
                filtered[key] = value

    if filtered:
        update_prediction(conn, fixture_id, filtered)
        return True
    return False


def get_last_processed_info() -> Dict:
    """Loads last processed match info."""
    last_processed_info = {}
    conn = _get_conn_ref()
    row = conn.execute(
        "SELECT fixture_id, date FROM predictions ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    if row:
        date_str = row['date']
        if date_str:
            try:
                last_processed_info = {
                    'date': date_str,
                    'id': row['fixture_id'],
                    'date_obj': dt.strptime(date_str, "%Y-%m-%d").date()
                }
                print(f"    [Resume] Last processed: ID {last_processed_info['id']} on {date_str}")
            except Exception:
                pass
    return last_processed_info


# ─── Schedules / Fixtures ───

def save_schedule_entry(match_info: Dict[str, Any], commit: bool = True):
    """Saves a single schedule entry."""
    match_info['last_updated'] = dt.now().isoformat()
    # period_scores: accept either already-encoded JSON string or a raw dict
    ps = match_info.get('period_scores') or match_info.get('part_scores')
    if isinstance(ps, dict):
        import json as _j
        ps = _j.dumps(ps)
    mapped = {
        'fixture_id': match_info.get('fixture_id'),
        'date': match_info.get('date'),
        'time': match_info.get('match_time', match_info.get('time')),
        'league_id': match_info.get('league_id'),
        'home_team_name': match_info.get('home_team', match_info.get('home_team_name')),
        'away_team_name': match_info.get('away_team', match_info.get('away_team_name')),
        'home_team_id': match_info.get('home_team_id'),
        'away_team_id': match_info.get('away_team_id'),
        'home_score': match_info.get('home_score'),
        'away_score': match_info.get('away_score'),
        'match_status': match_info.get('match_status'),
        'country_league': match_info.get('country_league'),
        'match_link': match_info.get('match_link'),
        'league_stage': match_info.get('league_stage'),
        'sport': match_info.get('sport', 'football'),
        'period_scores': ps,
    }
    upsert_fixture(_get_conn_ref(), mapped, commit=commit)


def transform_streamer_match_to_schedule(m: Dict[str, Any]) -> Dict[str, Any]:
    """Transforms a raw match dictionary from the streamer into a standard Schedule entry."""
    import json as _j
    now = dt.now()

    date_str = m.get('date')
    if not date_str:
        ts = m.get('timestamp')
        if ts:
            try:
                date_str = dt.fromisoformat(ts.replace('Z', '+00:00')).strftime("%Y-%m-%d")
            except Exception:
                date_str = now.strftime("%Y-%m-%d")
        else:
            date_str = now.strftime("%Y-%m-%d")

    league_id = m.get('league_id', '')
    if not league_id and m.get('country_league'):
        league_id = m['country_league'].replace(' - ', '_').replace(' ', '_').upper()

    # period_scores: prefer explicit field, fall back to part_scores dict from extractor
    ps = m.get('period_scores') or m.get('part_scores')
    if isinstance(ps, dict):
        ps = _j.dumps(ps)

    return {
        'fixture_id': m.get('fixture_id'),
        'date': date_str,
        'match_time': m.get('match_time', '00:00'),
        'country_league': m.get('country_league', 'Unknown'),
        'league_id': league_id,
        'home_team': m.get('home_team', 'Unknown'),
        'away_team': m.get('away_team', 'Unknown'),
        'home_team_id': m.get('home_team_id', 'unknown'),
        'away_team_id': m.get('away_team_id', 'unknown'),
        'home_score': m.get('home_score', ''),
        'away_score': m.get('away_score', ''),
        'match_status': m.get('status', 'scheduled'),
        'match_link': m.get('match_link', ''),
        'league_stage': m.get('league_stage', ''),
        'sport': m.get('sport', 'football'),
        'period_scores': ps,
        'last_updated': now.isoformat(),
    }


def save_schedule_batch(entries: List[Dict[str, Any]], commit: bool = True):
    """Batch UPSERTs multiple schedule entries."""
    import json as _j
    if not entries:
        return
    mapped = []
    for e in entries:
        ps = e.get('period_scores') or e.get('part_scores')
        if isinstance(ps, dict):
            ps = _j.dumps(ps)
        mapped.append({
            'fixture_id': e.get('fixture_id'),
            'date': e.get('date'),
            'time': e.get('match_time', e.get('time')),
            'league_id': e.get('league_id'),
            'home_team_name': e.get('home_team', e.get('home_team_name')),
            'away_team_name': e.get('away_team', e.get('away_team_name')),
            'home_team_id': e.get('home_team_id'),
            'away_team_id': e.get('away_team_id'),
            'home_score': e.get('home_score'),
            'away_score': e.get('away_score'),
            'match_status': e.get('match_status'),
            'country_league': e.get('country_league'),
            'match_link': e.get('match_link'),
            'league_stage': e.get('league_stage'),
            'sport': e.get('sport', 'football'),
            'period_scores': ps,
        })
    bulk_upsert_fixtures(_get_conn_ref(), mapped, commit=commit)


def get_all_schedules() -> List[Dict[str, Any]]:
    """Loads all match schedules."""
    return query_all(_get_conn_ref(), 'schedules')


# ─── Live Scores ───

def save_live_score_entry(match_info: Dict[str, Any]):
    """Saves or updates a live score entry."""
    match_info['last_updated'] = dt.now().isoformat()
    upsert_live_score(_get_conn_ref(), match_info)


# ─── Standings ───

def save_standings(standings_data: List[Dict[str, Any]], country_league: str, league_id: str = "", commit: bool = True):
    """UPSERTs standings data for a specific league."""
    if not standings_data:
        return

    last_updated = dt.now().isoformat()
    updated_count = 0

    for row in standings_data:
        row['country_league'] = country_league or row.get('country_league', 'Unknown')
        row['last_updated'] = last_updated

        t_id = row.get('team_id', '')
        l_id = league_id or row.get('league_id', '')
        if not l_id and country_league and " - " in country_league:
            l_id = country_league.split(" - ")[1].replace(' ', '_').upper()
        row['league_id'] = l_id

        if t_id and l_id:
            row['standings_key'] = f"{l_id}_{t_id}".upper()
            upsert_standing(_get_conn_ref(), row, commit=False)
            updated_count += 1

    if updated_count > 0:
        if commit:
            _get_conn_ref().commit()
        print(f"      [DB] UPSERTed {updated_count} standings entries for {country_league or league_id}")


def get_standings(country_league: str) -> List[Dict[str, Any]]:
    """Loads standings for a specific league."""
    return _get_standings_db(_get_conn_ref(), country_league)


# ─── URL standardization ───

def _standardize_url(url: str, base_type: str = "flashscore") -> str:
    """Ensures URLs are absolute and follow standard patterns."""
    if not url or url == 'N/A' or url.startswith("data:"):
        return url

    if url.startswith("/"):
        url = f"https://www.flashscore.com{url}"

    if "/team/" in url and "https://www.flashscore.com/team/" not in url:
        clean_path = url.split("team/")[-1].strip("/")
        url = f"https://www.flashscore.com/team/{clean_path}/"
    elif "/team/" in url:
        if not url.endswith("/"):
            url += "/"

    if "flashscore.com" not in url and not url.startswith("http"):
        url = f"https://www.flashscore.com{url if url.startswith('/') else '/' + url}"

    return url


# ─── Region / League ───

def save_country_league_entry(info: Dict[str, Any]):
    """Saves or updates a single region-league entry."""
    league_id = info.get('league_id')
    region = info.get('region', 'Unknown')
    league = info.get('league', 'Unknown')
    if not league_id:
        league_id = f"{region}_{league}".replace(' ', '_').replace('-', '_').upper()

    upsert_league(_get_conn_ref(), {
        'league_id': league_id,
        'name': info.get('league', info.get('name', league)),
        'region': region,
        'region_flag': _standardize_url(info.get('region_flag', '')),
        'region_url': _standardize_url(info.get('region_url', '')),
        'crest': _standardize_url(info.get('league_crest', info.get('crest', ''))),
        'url': _standardize_url(info.get('league_url', info.get('url', ''))),
        'date_updated': dt.now().isoformat(),
    })


# ─── Teams ───

def save_team_entry(team_info: Dict[str, Any]):
    """Saves or updates a single team entry with multi-league support."""
    team_id = team_info.get('team_id')
    if not team_id or team_id == 'unknown':
        return

    conn = _get_conn_ref()

    new_league_id = team_info.get('league_ids', team_info.get('country_league', ''))
    merged_league_ids = new_league_id

    row = conn.execute("SELECT league_ids FROM teams WHERE team_id = ?", (team_id,)).fetchone()
    if row and row['league_ids']:
        existing = row['league_ids'].split(';')
        if new_league_id and new_league_id not in existing:
            existing.append(new_league_id)
        merged_league_ids = ';'.join(filter(None, existing))

    upsert_team(conn, {
        'team_id': team_id,
        'name': team_info.get('name', team_info.get('team_name', 'Unknown')),
        'league_ids': [merged_league_ids] if merged_league_ids else [],
        'crest': _standardize_url(team_info.get('team_crest', team_info.get('crest', ''))),
        'url': _standardize_url(team_info.get('team_url', team_info.get('url', ''))),
        'country_code': team_info.get('country_code', team_info.get('country')),
        'city': team_info.get('city'),
        'stadium': team_info.get('stadium'),
        'other_names': team_info.get('other_names'),
        'abbreviations': team_info.get('abbreviations'),
        'search_terms': team_info.get('search_terms'),
    })


def get_team_crest(team_id: str, team_name: str = "") -> str:
    """Retrieves the crest URL for a team."""
    if not team_id and not team_name:
        return ""

    conn = _get_conn_ref()
    if team_id:
        row = conn.execute("SELECT crest FROM teams WHERE team_id = ?", (str(team_id),)).fetchone()
        if row and row['crest']:
            return row['crest']

    if team_name:
        row = conn.execute("SELECT crest FROM teams WHERE name = ?", (team_name,)).fetchone()
        if row and row['crest']:
            return row['crest']

    return ""


def propagate_crest_urls():
    """Propagates Supabase crest URLs from teams into schedules."""
    conn = _get_conn_ref()
    h = conn.execute("""
        UPDATE schedules SET home_crest = (
            SELECT t.crest FROM teams t
            WHERE t.team_id = schedules.home_team_id AND t.crest LIKE 'http%'
        ) WHERE home_team_id IN (SELECT team_id FROM teams WHERE crest LIKE 'http%')
          AND (home_crest IS NULL OR home_crest NOT LIKE 'http%supabase%')
    """).rowcount
    a = conn.execute("""
        UPDATE schedules SET away_crest = (
            SELECT t.crest FROM teams t
            WHERE t.team_id = schedules.away_team_id AND t.crest LIKE 'http%'
        ) WHERE away_team_id IN (SELECT team_id FROM teams WHERE crest LIKE 'http%')
          AND (away_crest IS NULL OR away_crest NOT LIKE 'http%supabase%')
    """).rowcount
    conn.commit()
    if h + a > 0:
        print(f"    [Crest] Propagated Supabase URLs: {h} home + {a} away")
