-- supabase_rls_setup.sql
-- LeoBook — Supabase Row Level Security setup
--
-- PURPOSE
-- -------
-- Enable RLS on all LeoBook tables and create a dedicated sync role
-- (leobook_sync) that has exactly the privileges needed for the daemon:
--   SELECT / INSERT / UPDATE on data tables
--   No DELETE, no schema access, no other tables
--
-- USAGE
-- -----
-- 1. Run this script once in the Supabase SQL Editor (Settings → SQL Editor).
-- 2. Copy the JWT secret of the leobook_sync role into your .env as
--    SUPABASE_SYNC_KEY (see step 3 below).
-- 3. Remove SUPABASE_SERVICE_KEY from .env once verified working.
--
-- STEP 1 — Create a scoped database role
-- ----------------------------------------
-- In the Supabase dashboard: Authentication → Users → Add User
-- OR via SQL (if your plan allows custom roles):
--
--   CREATE ROLE leobook_sync WITH LOGIN PASSWORD '<strong-password>';
--
-- STEP 2 — Enable RLS on all LeoBook tables
-- -------------------------------------------

ALTER TABLE leagues           ENABLE ROW LEVEL SECURITY;
ALTER TABLE teams             ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedules         ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE fb_matches        ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_odds        ENABLE ROW LEVEL SECURITY;
ALTER TABLE live_scores       ENABLE ROW LEVEL SECURITY;
ALTER TABLE countries         ENABLE ROW LEVEL SECURITY;
ALTER TABLE accuracy_reports  ENABLE ROW LEVEL SECURITY;
-- _sync_watermarks is SQLite-only (local sync_manager.py) — not present in Supabase, skip.

-- STEP 3 — Service-role bypass (keeps existing behaviour for the service key)
-- ----------------------------------------------------------------------------
-- Supabase's service_role already bypasses RLS by default. These policies are
-- belt-and-suspenders so the intent is explicit in the policy list.

CREATE POLICY "service_role full access" ON leagues
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON teams
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON schedules
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON predictions
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON audit_log
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON fb_matches
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON match_odds
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON live_scores
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON countries
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role full access" ON accuracy_reports
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- (no _sync_watermarks policy — table is SQLite-only)

-- STEP 4 — Scoped sync-role policies (SELECT + INSERT + UPDATE only)
-- -------------------------------------------------------------------
-- Replace 'leobook_sync' with the actual Supabase user/role you created.
-- If using Supabase Auth users, use auth.uid() checks instead.
--
-- These policies allow the sync daemon to read and write data but NOT delete rows
-- and NOT access any other table in the schema.

CREATE POLICY "sync read"   ON leagues FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON leagues FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON leagues FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON teams FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON teams FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON teams FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON schedules FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON schedules FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON schedules FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON predictions FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON predictions FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON predictions FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON audit_log FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON audit_log FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON audit_log FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON fb_matches FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON fb_matches FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON fb_matches FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON match_odds FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON match_odds FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON match_odds FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON live_scores FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON live_scores FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON live_scores FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON countries FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON countries FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON countries FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON accuracy_reports FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON accuracy_reports FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON accuracy_reports FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

-- (no _sync_watermarks policies — table is SQLite-only)

-- STEP 5 — Grant table-level privileges to the sync role
-- -------------------------------------------------------

GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO leobook_sync;
-- Revoke dangerous privileges explicitly
REVOKE DELETE ON ALL TABLES IN SCHEMA public FROM leobook_sync;
REVOKE TRUNCATE ON ALL TABLES IN SCHEMA public FROM leobook_sync;

-- STEP 6 — Generate a JWT for the sync role (Supabase dashboard)
-- ---------------------------------------------------------------
-- Dashboard → Settings → API → JWT Settings → "Generate new token"
-- Set role claim to "leobook_sync" and copy the resulting JWT into
-- .env as SUPABASE_SYNC_KEY.
--
-- .env additions:
--   SUPABASE_SYNC_KEY=<jwt-for-leobook_sync-role>
--
-- Once SUPABASE_SYNC_KEY is set, supabase_client.py will prefer it
-- over SUPABASE_SERVICE_KEY. Remove SUPABASE_SERVICE_KEY from .env
-- after confirming sync works correctly.

-- STEP 7 — User feature tables (provision with Data/Supabase/user_features_schema.sql first)
-- ---------------------------------------------------------------------------
-- Daemon upserts: stairway mirror, Football.com balance, optional rule_engine copies.

CREATE POLICY "sync read"   ON user_rule_engines FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON user_rule_engines FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON user_rule_engines FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON user_stairway_state FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON user_stairway_state FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON user_stairway_state FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON user_fb_balance FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON user_fb_balance FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON user_fb_balance FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);

CREATE POLICY "sync read"   ON rl_training_jobs FOR SELECT TO leobook_sync USING (true);
CREATE POLICY "sync write"  ON rl_training_jobs FOR INSERT TO leobook_sync WITH CHECK (true);
CREATE POLICY "sync update" ON rl_training_jobs FOR UPDATE TO leobook_sync USING (true) WITH CHECK (true);
-- service_role: add explicit policies via Data/Supabase/user_features_schema.sql (or rely on bypass)
