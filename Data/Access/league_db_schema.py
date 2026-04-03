# MIGRATION REQUIRED (Supabase):
# ALTER TABLE leagues ADD COLUMN IF NOT EXISTS region TEXT DEFAULT '';

# league_db_schema.py: Table definitions for LeoBook SQLite.
# Part of LeoBook Data — Access
#
# Called by: league_db.py (init_db)ly. All callers should use league_db.py.

# ── SQLite schema ─────────────────────────────────────────────────────────────

_SCHEMA_SQL = """
    CREATE TABLE IF NOT EXISTS leagues (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        league_id           TEXT UNIQUE NOT NULL,
        fs_league_id        TEXT,
        country_code        TEXT,
        continent           TEXT,
        name                TEXT NOT NULL,
        crest               TEXT,
        current_season      TEXT,
        url                 TEXT,
        processed           INTEGER DEFAULT 0,
        region              TEXT,
        region_flag         TEXT,
        region_url          TEXT,
        other_names         TEXT,
        abbreviations       TEXT,
        search_terms        TEXT,
        date_updated        TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS teams (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id             TEXT UNIQUE,
        name                TEXT NOT NULL,
        league_ids          JSON,
        crest               TEXT,
        country_code        TEXT,
        url                 TEXT,
        hq_crest            INTEGER DEFAULT 0,
        country             TEXT,
        city                TEXT,
        stadium             TEXT,
        other_names         TEXT,
        abbreviations       TEXT,
        search_terms        TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS schedules (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id          TEXT UNIQUE,
        date                TEXT,
        time                TEXT,
        league_id           TEXT,
        home_team_id        TEXT,
        home_team_name      TEXT,
        away_team_id        TEXT,
        away_team_name      TEXT,
        home_score          INTEGER,
        away_score          INTEGER,
        extra               JSON,
        league_stage        TEXT,
        match_status        TEXT,
        season              TEXT,
        home_crest          TEXT,
        away_crest          TEXT,
        home_red_cards      INTEGER DEFAULT 0,
        away_red_cards      INTEGER DEFAULT 0,
        winner              TEXT,
        url                 TEXT,
        country_league      TEXT,
        match_link          TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS predictions (
        fixture_id          TEXT NOT NULL,
        user_id             TEXT NOT NULL DEFAULT '',
        date                TEXT,
        match_time          TEXT,
        country_league      TEXT,
        home_team           TEXT,
        away_team           TEXT,
        home_team_id        TEXT,
        away_team_id        TEXT,
        prediction          TEXT,
        confidence          TEXT,
        reason              TEXT,
        home_form_n         INTEGER,
        away_form_n         INTEGER,
        h2h_count           INTEGER,
        actual_score        TEXT,
        outcome_correct     TEXT,
        status              TEXT DEFAULT 'pending',
        match_link          TEXT,
        odds                TEXT,
        market_reliability_score REAL,
        home_crest_url      TEXT,
        away_crest_url      TEXT,
        recommendation_score REAL,
        h2h_fixture_ids     JSON,
        form_fixture_ids    JSON,
        standings_snapshot  JSON,
        league_stage        TEXT,
        generated_at        TEXT,
        home_score          TEXT,
        away_score          TEXT,
        chosen_market       TEXT,
        market_id           TEXT,
        rule_explanation    TEXT,
        override_reason     TEXT,
        statistical_edge    REAL,
        pure_model_suggestion TEXT,
        form_home           JSON,
        form_away           JSON,
        h2h_summary         JSON,
        standings_home      JSON,
        standings_away      JSON,
        rule_engine_decision TEXT,
        rl_decision         TEXT,
        ensemble_weights    JSON,
        rec_qualifications  JSON,
        is_available        INTEGER DEFAULT 0,
        last_updated        TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (fixture_id, user_id)
    );

    -- standings: REMOVED in v7.0 — computed on-the-fly from schedules table.
    -- See computed_standings() function and Supabase computed_standings VIEW.

    CREATE TABLE IF NOT EXISTS audit_log (
        id                  TEXT PRIMARY KEY,
        user_id             TEXT NOT NULL DEFAULT '',
        timestamp           TEXT,
        event_type          TEXT,
        description         TEXT,
        balance_before      REAL,
        balance_after       REAL,
        stake               REAL,
        status              TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS fb_matches (
        site_match_id       TEXT NOT NULL,
        user_id             TEXT NOT NULL DEFAULT '',
        date                TEXT,
        time                TEXT,
        home_team           TEXT,
        away_team           TEXT,
        league              TEXT,
        url                 TEXT,
        last_extracted      TEXT,
        fixture_id          TEXT,
        matched             TEXT,
        odds                TEXT,
        booking_status      TEXT,
        booking_details     TEXT,
        booking_code        TEXT,
        booking_url         TEXT,
        status              TEXT,
        last_updated        TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (site_match_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS live_scores (
        fixture_id          TEXT PRIMARY KEY,
        date                TEXT,
        match_time          TEXT,
        home_team           TEXT,
        away_team           TEXT,
        home_score          TEXT,
        away_score          TEXT,
        minute              TEXT,
        status              TEXT,
        country_league      TEXT,
        match_link          TEXT,
        timestamp           TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS accuracy_reports (
        report_id           TEXT NOT NULL,
        user_id             TEXT NOT NULL DEFAULT '',
        timestamp           TEXT,
        volume              INTEGER,
        win_rate            REAL,
        return_pct          REAL,
        period              TEXT,
        last_updated        TEXT DEFAULT (datetime('now')),
        PRIMARY KEY (report_id, user_id)
    );

    CREATE TABLE IF NOT EXISTS countries (
        code                TEXT PRIMARY KEY,
        name                TEXT,
        continent           TEXT,
        capital             TEXT,
        flag_1x1            TEXT,
        flag_4x3            TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS profiles (
        id                  TEXT PRIMARY KEY,
        email               TEXT,
        username            TEXT,
        full_name           TEXT,
        avatar_url          TEXT,
        tier                TEXT,
        credits             REAL,
        created_at          TEXT,
        updated_at          TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS custom_rules (
        id                  TEXT PRIMARY KEY,
        user_id             TEXT,
        name                TEXT,
        description         TEXT,
        is_active           INTEGER,
        logic               TEXT,
        priority            INTEGER,
        created_at          TEXT,
        updated_at          TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS rule_executions (
        id                  TEXT PRIMARY KEY,
        rule_id             TEXT,
        fixture_id          TEXT,
        user_id             TEXT,
        result              TEXT,
        executed_at         TEXT,
        last_updated        TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS match_odds (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id      TEXT    NOT NULL,
        site_match_id   TEXT    NOT NULL,
        market_id       TEXT    NOT NULL,
        base_market     TEXT    NOT NULL,
        category        TEXT    NOT NULL DEFAULT '',
        exact_outcome   TEXT    NOT NULL,
        line            TEXT    DEFAULT '',
        odds_value      REAL    NOT NULL,
        likelihood_pct  INTEGER NOT NULL DEFAULT 0,
        rank_in_list    INTEGER NOT NULL DEFAULT 0,
        extracted_at    TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(fixture_id, market_id, exact_outcome, line)
    );




    CREATE TABLE IF NOT EXISTS log_segments (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     TEXT NOT NULL DEFAULT '',
        path        TEXT NOT NULL UNIQUE,
        category    TEXT NOT NULL,
        started_at  TEXT NOT NULL,
        closed_at   TEXT,
        size_bytes  INTEGER DEFAULT 0,
        uploaded    INTEGER DEFAULT 0,
        remote_path TEXT
    );

    -- Per-user stairway compounding state (one row per user).
    CREATE TABLE IF NOT EXISTS stairway_state (
        user_id         TEXT PRIMARY KEY,
        current_step    INTEGER DEFAULT 1,
        last_updated    TEXT,
        last_result     TEXT,
        cycle_count     INTEGER DEFAULT 0
    );

    -- Per-user credentials for third-party betting platforms (encrypted at rest).
    -- platform: e.g. 'football_com', 'betfair', 'smarkets'
    -- credential_key: e.g. 'phone', 'password', 'api_key'
    -- credential_value: encrypted via Fernet (CREDENTIAL_ENCRYPTION_KEY in .env)
    CREATE TABLE IF NOT EXISTS user_credentials (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id         TEXT NOT NULL,
        platform        TEXT NOT NULL,
        credential_key  TEXT NOT NULL,
        credential_value TEXT NOT NULL,
        last_updated    TEXT DEFAULT (datetime('now')),
        UNIQUE(user_id, platform, credential_key)
    );

    -- Indexes for hot-path queries
    CREATE INDEX IF NOT EXISTS idx_schedules_league ON schedules(league_id);
    CREATE INDEX IF NOT EXISTS idx_schedules_date ON schedules(date);
    CREATE INDEX IF NOT EXISTS idx_schedules_fixture_id ON schedules(fixture_id);
    CREATE INDEX IF NOT EXISTS idx_leagues_league_id ON leagues(league_id);
    CREATE INDEX IF NOT EXISTS idx_predictions_user ON predictions(user_id);
    CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions(user_id, date);
    CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(user_id, status);
    CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id, timestamp);
    CREATE INDEX IF NOT EXISTS idx_fb_matches_user ON fb_matches(user_id);
    CREATE INDEX IF NOT EXISTS idx_accuracy_reports_user ON accuracy_reports(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_credentials_user ON user_credentials(user_id, platform);
    CREATE INDEX IF NOT EXISTS idx_match_odds_fixture ON match_odds(fixture_id);
    CREATE INDEX IF NOT EXISTS idx_match_odds_market ON match_odds(market_id, extracted_at);
    CREATE INDEX IF NOT EXISTS idx_match_odds_site ON match_odds(site_match_id);
"""

# ── ALTER TABLE migrations (idempotent) ───────────────────────────────────────

_ALTER_MIGRATIONS = [
    ("leagues", "region", "TEXT"),
    ("leagues", "region_flag", "TEXT"),
    ("leagues", "region_url", "TEXT"),
    ("leagues", "other_names", "TEXT"),
    ("leagues", "abbreviations", "TEXT"),
    ("leagues", "search_terms", "TEXT"),
    ("leagues", "date_updated", "TEXT"),
    ("leagues", "fs_league_id", "TEXT"),
    ("teams", "team_id", "TEXT"),
    ("teams", "city", "TEXT"),
    ("teams", "stadium", "TEXT"),
    ("teams", "other_names", "TEXT"),
    ("teams", "abbreviations", "TEXT"),
    ("teams", "search_terms", "TEXT"),
    ("teams", "hq_crest", "INTEGER DEFAULT 0"),
    ("schedules", "country_league", "TEXT"),
    ("schedules", "match_link", "TEXT"),
    ("schedules", "home_red_cards", "INTEGER DEFAULT 0"),
    ("schedules", "away_red_cards", "INTEGER DEFAULT 0"),
    ("schedules", "winner", "TEXT"),
    ("predictions", "pure_model_suggestion", "TEXT"),
    ("predictions", "form_home", "JSON"),
    ("predictions", "form_away", "JSON"),
    ("predictions", "h2h_summary", "JSON"),
    ("predictions", "standings_home", "JSON"),
    ("predictions", "standings_away", "JSON"),
    ("predictions", "rule_engine_decision", "TEXT"),
    ("predictions", "rl_decision", "TEXT"),
    ("predictions", "ensemble_weights", "JSON"),
    ("predictions", "rec_qualifications", "JSON"),
    ("predictions", "is_available", "INTEGER DEFAULT 0"),
    ("live_scores", "date", "TEXT"),
    ("live_scores", "match_time", "TEXT"),
    # v9.5.9 — multi-user tenancy: user_id added to all per-user tables
    ("predictions",      "user_id", "TEXT NOT NULL DEFAULT ''"),
    ("audit_log",        "user_id", "TEXT NOT NULL DEFAULT ''"),
    ("fb_matches",       "user_id", "TEXT NOT NULL DEFAULT ''"),
    ("accuracy_reports", "user_id", "TEXT NOT NULL DEFAULT ''"),
    ("log_segments",     "user_id", "TEXT NOT NULL DEFAULT ''"),
]

# ── CSV → SQLite import map REMOVED (v7.0) ───────────────────────────────────
# CSV is no longer a valid ingestion path. All data enters through the
# upsert_*() functions in league_db.py (upsert_fixture, upsert_league,
# upsert_team, upsert_prediction, etc.). There are no .csv files in the
# production data pipeline. If you see any reference to _CSV_TABLE_MAP,
# it is dead code and should be removed.

# ── Computed standings SQL (v7.0) ─────────────────────────────────────────────

_COMPUTED_STANDINGS_SQL = """
    WITH match_results AS (
        SELECT
            s.league_id,
            s.home_team_id AS team_id,
            COALESCE(s.home_team_name, h.name) AS team_name,
            s.season,
            s.date,
            CASE WHEN s.home_score > s.away_score THEN 3 WHEN s.home_score = s.away_score THEN 1 ELSE 0 END AS points,
            CASE WHEN s.home_score > s.away_score THEN 1 ELSE 0 END AS wins,
            CASE WHEN s.home_score = s.away_score THEN 1 ELSE 0 END AS draws,
            CASE WHEN s.home_score < s.away_score THEN 1 ELSE 0 END AS losses,
            s.home_score AS goals_for,
            s.away_score AS goals_against
        FROM schedules s
        LEFT JOIN teams h ON s.home_team_id = h.team_id
        WHERE s.match_status = 'finished'
          AND s.home_score IS NOT NULL AND s.away_score IS NOT NULL
          AND (TYPEOF(s.home_score) != 'text' OR CAST(s.home_score AS INTEGER) = s.home_score)

        UNION ALL

        SELECT
            s.league_id,
            s.away_team_id AS team_id,
            COALESCE(s.away_team_name, a.name) AS team_name,
            s.season,
            s.date,
            CASE WHEN s.away_score > s.home_score THEN 3 WHEN s.away_score = s.home_score THEN 1 ELSE 0 END,
            CASE WHEN s.away_score > s.home_score THEN 1 ELSE 0 END,
            CASE WHEN s.away_score = s.home_score THEN 1 ELSE 0 END,
            CASE WHEN s.away_score < s.home_score THEN 1 ELSE 0 END,
            s.away_score,
            s.home_score
        FROM schedules s
        LEFT JOIN teams a ON s.away_team_id = a.team_id
        WHERE s.match_status = 'finished'
          AND s.home_score IS NOT NULL AND s.away_score IS NOT NULL
          AND (TYPEOF(s.home_score) != 'text' OR CAST(s.home_score AS INTEGER) = s.home_score)
    )
    SELECT
        league_id, team_id, MAX(team_name) AS team_name, season,
        COUNT(*) AS played,
        SUM(wins) AS wins,
        SUM(draws) AS draws,
        SUM(losses) AS losses,
        SUM(goals_for) AS goals_for,
        SUM(goals_against) AS goals_against,
        SUM(goals_for) - SUM(goals_against) AS goal_difference,
        SUM(points) AS points
    FROM match_results
    WHERE 1=1 {filters}
    GROUP BY league_id, team_id, season
    ORDER BY league_id, season, points DESC, goal_difference DESC, goals_for DESC
"""

__all__ = [
    "_SCHEMA_SQL",
    "_ALTER_MIGRATIONS",
    "_COMPUTED_STANDINGS_SQL",
]
