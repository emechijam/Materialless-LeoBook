# sync_schema.py: Supabase table schema DDL, column mappings, and sync config.
# Part of LeoBook Data — Access Layer
# Authoritative source for: TABLE_CONFIG, SUPABASE_SCHEMA, _ALLOWED_COLS, _COL_REMAP
# IMPORTANT: Column names here must exactly match sync_manager.SUPABASE_SCHEMA —
# they control what _ALLOWED_COLS accepts during push operations.

import re
from typing import Dict

# SQLite table -> Supabase table mapping
TABLE_CONFIG = {
    'predictions':      {'local_table': 'predictions',      'remote_table': 'predictions',      'key': 'fixture_id,user_id'},
    'schedules':        {'local_table': 'schedules',        'remote_table': 'schedules',        'key': 'fixture_id'},
    'teams':            {'local_table': 'teams',            'remote_table': 'teams',            'key': 'team_id'},
    'leagues':          {'local_table': 'leagues',          'remote_table': 'leagues',          'key': 'league_id'},
    'fb_matches':       {'local_table': 'fb_matches',       'remote_table': 'fb_matches',       'key': 'site_match_id,user_id'},
    'profiles':         {'local_table': 'profiles',         'remote_table': 'profiles',         'key': 'id'},
    'custom_rules':     {'local_table': 'custom_rules',     'remote_table': 'custom_rules',     'key': 'id'},
    'rule_executions':  {'local_table': 'rule_executions',  'remote_table': 'rule_executions',  'key': 'id'},
    'accuracy_reports': {'local_table': 'accuracy_reports', 'remote_table': 'accuracy_reports', 'key': 'report_id,user_id'},
    'audit_log':        {'local_table': 'audit_log',        'remote_table': 'audit_log',        'key': 'id'},
    'live_scores':      {'local_table': 'live_scores',      'remote_table': 'live_scores',      'key': 'fixture_id'},
    'countries':        {'local_table': 'countries',        'remote_table': 'countries',        'key': 'code'},
    'match_odds':       {'local_table': 'match_odds',       'remote_table': 'match_odds',       'key': 'fixture_id,market_id,exact_outcome,line'},
}

# ── Supabase auto-provisioning DDL ─────────────────────────────────────────
SUPABASE_SCHEMA = {
    'predictions': """
        CREATE TABLE IF NOT EXISTS public.predictions (
            fixture_id TEXT PRIMARY KEY,
            date TEXT, match_time TEXT, country_league TEXT,
            home_team TEXT, away_team TEXT, home_team_id TEXT, away_team_id TEXT,
            prediction TEXT, confidence TEXT, reason TEXT,
            xg_home REAL, xg_away REAL, btts TEXT, over_2_5 TEXT,
            best_score TEXT, top_scores TEXT,
            home_form_n INTEGER, away_form_n INTEGER,
            home_tags TEXT, away_tags TEXT, h2h_tags TEXT, standings_tags TEXT,
            h2h_count INTEGER, actual_score TEXT, outcome_correct TEXT,
            status TEXT DEFAULT 'pending', match_link TEXT, odds TEXT,
            market_reliability_score REAL, home_crest_url TEXT, away_crest_url TEXT,
            recommendation_score REAL, h2h_fixture_ids JSONB, form_fixture_ids JSONB,
            standings_snapshot JSONB, league_stage TEXT, generated_at TEXT,
            home_score TEXT, away_score TEXT,
            form_home JSONB, form_away JSONB, h2h_summary JSONB,
            standings_home JSONB, standings_away JSONB,
            is_available BOOLEAN DEFAULT FALSE,
            last_updated TIMESTAMPTZ DEFAULT now(),
            -- v9.6.0 rule engine + sport fields
            sport TEXT DEFAULT 'football',
            user_id TEXT DEFAULT '',
            chosen_market TEXT,
            market_id TEXT,
            rule_explanation TEXT,
            override_reason TEXT,
            statistical_edge REAL,
            pure_model_suggestion TEXT,
            rule_engine_decision TEXT,
            rl_decision JSONB,
            ensemble_weights JSONB,
            rec_qualifications JSONB,
            -- v9.8.0 market period targeting
            market_line REAL,
            market_period TEXT DEFAULT 'full'
        );""",
    'schedules': """
        CREATE TABLE IF NOT EXISTS public.schedules (
            fixture_id TEXT PRIMARY KEY,
            date TEXT, match_time TEXT, league_id TEXT,
            home_team_id TEXT, home_team TEXT, away_team_id TEXT, away_team TEXT,
            home_score INTEGER, away_score INTEGER, extra JSONB,
            league_stage TEXT, match_status TEXT, season TEXT,
            home_crest TEXT, away_crest TEXT, match_link TEXT,
            country_league TEXT,
            home_red_cards INTEGER DEFAULT 0,
            away_red_cards INTEGER DEFAULT 0,
            winner TEXT,
            period_scores JSONB,
            sport TEXT DEFAULT 'football',
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'teams': """
        CREATE TABLE IF NOT EXISTS public.teams (
            team_id TEXT PRIMARY KEY,
            name TEXT NOT NULL, league_ids JSONB, crest TEXT,
            country_code TEXT, url TEXT,
            city TEXT, stadium TEXT,
            other_names TEXT, abbreviations TEXT, search_terms TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'leagues': """
        CREATE TABLE IF NOT EXISTS public.leagues (
            league_id TEXT PRIMARY KEY,
            fs_league_id TEXT, country_code TEXT, continent TEXT,
            name TEXT NOT NULL, crest TEXT, current_season TEXT,
            url TEXT, region_flag TEXT,
            other_names TEXT, abbreviations TEXT, search_terms TEXT,
            level TEXT, season_format TEXT,
            date_updated TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'audit_log': """
        CREATE TABLE IF NOT EXISTS public.audit_log (
            id TEXT PRIMARY KEY,
            timestamp TEXT, event_type TEXT, description TEXT,
            balance_before REAL, balance_after REAL, stake REAL, status TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'fb_matches': """
        CREATE TABLE IF NOT EXISTS public.fb_matches (
            site_match_id TEXT PRIMARY KEY,
            league_id TEXT,
            date TEXT, match_time TEXT,
            home_team TEXT, away_team TEXT,
            url TEXT,
            fixture_id TEXT,
            matched TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
        # NOTE: Supabase column renamed from 'time' → 'match_time' on 2026-03-16.
        # Run once in Supabase SQL editor after deploying this change:
        #   ALTER TABLE public.fb_matches RENAME COLUMN time TO match_time;
    'live_scores': """
        CREATE TABLE IF NOT EXISTS public.live_scores (
            fixture_id TEXT PRIMARY KEY,
            date TEXT, match_time TEXT,
            home_team TEXT, away_team TEXT,
            home_score TEXT, away_score TEXT, minute TEXT,
            status TEXT, country_league TEXT, match_link TEXT,
            sport TEXT DEFAULT 'football',
            part_scores TEXT,
            timestamp TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'accuracy_reports': """
        CREATE TABLE IF NOT EXISTS public.accuracy_reports (
            report_id TEXT PRIMARY KEY,
            timestamp TEXT, volume INTEGER, win_rate REAL,
            return_pct REAL, period TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'countries': """
        CREATE TABLE IF NOT EXISTS public.countries (
            code TEXT PRIMARY KEY,
            name TEXT, continent TEXT, capital TEXT,
            flag_1x1 TEXT, flag_4x3 TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'profiles': """
        CREATE TABLE IF NOT EXISTS public.profiles (
            id TEXT PRIMARY KEY,
            email TEXT, username TEXT, full_name TEXT,
            avatar_url TEXT, tier TEXT, credits REAL,
            created_at TEXT, updated_at TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'custom_rules': """
        CREATE TABLE IF NOT EXISTS public.custom_rules (
            id TEXT PRIMARY KEY,
            user_id TEXT, name TEXT, description TEXT,
            is_active INTEGER, logic TEXT, priority INTEGER,
            created_at TEXT, updated_at TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'rule_executions': """
        CREATE TABLE IF NOT EXISTS public.rule_executions (
            id TEXT PRIMARY KEY,
            rule_id TEXT, fixture_id TEXT, user_id TEXT,
            result TEXT, executed_at TEXT,
            last_updated TIMESTAMPTZ DEFAULT now()
        );""",
    'match_odds': """
        CREATE TABLE IF NOT EXISTS public.match_odds (
            fixture_id TEXT,
            site_match_id TEXT,
            market_id TEXT,
            base_market TEXT,
            category TEXT,
            exact_outcome TEXT,
            line TEXT,
            odds_value REAL,
            likelihood_pct INTEGER,
            rank_in_list INTEGER,
            extracted_at TEXT,
            last_updated TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (fixture_id, market_id, exact_outcome, line)
        );""",
    'user_rule_engines': """
        CREATE TABLE IF NOT EXISTS public.user_rule_engines (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_default BOOLEAN NOT NULL DEFAULT false,
            is_builtin_default BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );""",
    'user_stairway_state': """
        CREATE TABLE IF NOT EXISTS public.user_stairway_state (
            user_id TEXT PRIMARY KEY,
            current_step INTEGER NOT NULL DEFAULT 1,
            last_updated TIMESTAMPTZ,
            last_result TEXT,
            cycle_count INTEGER NOT NULL DEFAULT 0,
            week_bucket TEXT,
            week_cycles_completed INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );""",
    'user_fb_balance': """
        CREATE TABLE IF NOT EXISTS public.user_fb_balance (
            user_id TEXT PRIMARY KEY,
            balance REAL NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'NGN',
            source TEXT,
            captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );""",
    'rl_training_jobs': """
        CREATE TABLE IF NOT EXISTS public.rl_training_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id TEXT NOT NULL,
            rule_engine_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            train_season TEXT,
            phase INTEGER DEFAULT 1,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            error TEXT
        );""",
    'user_device_fingerprint': """
        CREATE TABLE IF NOT EXISTS public.user_device_fingerprint (
            user_id TEXT PRIMARY KEY,
            proxy_server TEXT,
            user_agent TEXT,
            viewport_w INTEGER,
            viewport_h INTEGER,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );""",
}

# ── Derived: allowed columns per remote table (parsed from SUPABASE_SCHEMA DDL) ──
_ALLOWED_COLS: Dict[str, set] = {}
for _tbl, _ddl in SUPABASE_SCHEMA.items():
    _cols = set(re.findall(r'\b([a-z_][a-z0-9_]*)\s+(?:TEXT|INTEGER|REAL|JSONB|TIMESTAMPTZ|BOOLEAN)', _ddl, re.IGNORECASE))
    _cols.discard('TABLE')
    _cols.discard('NOT')
    _cols.discard('IF')
    _cols.discard('EXISTS')
    _cols.discard('DEFAULT')
    _ALLOWED_COLS[_tbl] = _cols

# Column remaps: local name → remote name (applied before schema filtering)
_COL_REMAP = {
    'time':           'match_time',
    'over_2.5':       'over_2_5',
    'country':        'country_code',
    'team_name':      'name',
    'home_team_name': 'home_team',
    'away_team_name': 'away_team',
}

# ── Per-table batch sizes ─────────────────────────────────────────────────────
_BATCH_SIZES: Dict[str, int] = {
    'schedules':   500,
    'match_odds':  1000,
    'predictions': 200,   # 1969-row single upsert → Supabase 57014 timeout. Chunked at 200.
    'default':     2000,
}

# ── Matching Engine v1.2 — full idempotent SQL (STEP 9 from bootstrap) ────────
# Used by any bootstrap/provision routine to install the SQL matching engine
# on a fresh or existing Supabase project. Safe to re-run (CREATE OR REPLACE).
# Run via:
#   supabase.rpc('exec_sql', {'query': MATCHING_ENGINE_SQL})
# or paste directly in Supabase SQL Editor.
# v1.2 adds: normalize_team_name(), fb_match_candidates view,
#             match_fb_to_schedule(), auto_match_fb_matches(),
#             trg_auto_match_fb_matches trigger, performance indexes.
MATCHING_ENGINE_SQL = """
-- =============================================================================
-- LEOBOOK Team Matching Engine v1.2  (2026-03-17) — STEP 9 bootstrap block
-- Safe to re-run: CREATE OR REPLACE / IF NOT EXISTS throughout.
-- =============================================================================

-- 9a: Name normalizer
DROP FUNCTION IF EXISTS public.normalize_team_name(TEXT);
CREATE OR REPLACE FUNCTION public.normalize_team_name(raw TEXT)
RETURNS TEXT LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT TRIM(
           REGEXP_REPLACE(
             REGEXP_REPLACE(
               LOWER(COALESCE(raw, '')),
               '\\m(fc|cf|sc|ac|bk|sk|fk|if|afc|bfc|sfc|united|city|town|rovers|wanderers|athletic|albion|county)\\M',
               '', 'gi'
             ),
             '[^a-z0-9]+', ' ', 'g'
           )
         )
$$;
GRANT EXECUTE ON FUNCTION public.normalize_team_name(TEXT) TO service_role, anon, authenticated;

-- 9b-e: REMOVED — fb_match_candidates VIEW, match_fb_to_schedule RPC,
-- auto_match_fb_matches RPC, and trg_auto_match_fb trigger are all replaced
-- by inline Python logic in Modules/FootballCom/match_resolver.py (v2.0).
-- Matching is now: league_id + date + normalized home + away (exact INNER JOIN).

-- 9f: Performance indexes (kept for Python-side queries)
CREATE INDEX IF NOT EXISTS idx_schedules_league_date ON public.schedules (league_id, date);
CREATE INDEX IF NOT EXISTS idx_schedules_date ON public.schedules (date);
"""

# Note: computed_standings VIEW is NOT in SUPABASE_SCHEMA because it is not
# a synced table — it is a Postgres VIEW defined in the bootstrap SQL and
# queried directly by the Flutter app and Python backend.
# It is re-created by SUPABASE_SETUP.md STEP 6 (and Part 3B upgrade path).

__all__ = [
    "TABLE_CONFIG",
    "SUPABASE_SCHEMA",
    "_ALLOWED_COLS",
    "_COL_REMAP",
    "_BATCH_SIZES",
    "MATCHING_ENGINE_SQL",
]
