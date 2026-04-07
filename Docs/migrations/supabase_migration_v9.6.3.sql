-- ============================================================
-- LeoBook Supabase Migration v9.6.3
-- ============================================================
-- URGENT: Run this in Supabase SQL Editor NOW.
-- The schedules sync is failing with HTTP 400 because the
-- 'sport' column is missing from Supabase (exists in SQLite only).
-- ============================================================

-- 1. Add sport column to schedules (BLOCKING sync issue)
ALTER TABLE public.schedules
    ADD COLUMN IF NOT EXISTS sport TEXT DEFAULT 'football';

-- 2. Add sport column to leagues (same gap)
ALTER TABLE public.leagues
    ADD COLUMN IF NOT EXISTS sport TEXT DEFAULT 'football';

-- 3. Add sport column to predictions
ALTER TABLE public.predictions
    ADD COLUMN IF NOT EXISTS sport TEXT DEFAULT 'football';

-- 4. Backfill — all existing rows are football
UPDATE public.schedules  SET sport = 'football' WHERE sport IS NULL;
UPDATE public.leagues    SET sport = 'football' WHERE sport IS NULL;
UPDATE public.predictions SET sport = 'football' WHERE sport IS NULL;

-- Also backfill basketball leagues by league_id prefix (3_ = basketball)
UPDATE public.leagues SET sport = 'basketball' WHERE league_id LIKE '3_%';

-- ============================================================
-- Release notes:
--   Fixed: basketball extraction 0-row bug — sport-aware
--     participant selector fallback in EXTRACT_MATCHES_JS.
--   Fixed: Supabase 400 on schedules push (sport column missing).
--   App: guest → login, fingerprint read-only, sign-out wipes
--     Football.com creds, FAB +32dp, nav bar 35% glass.
-- ============================================================

--   • Basketball extraction fix: Playwright compound CSS selector
--     "[id^='g_1_'], [id^='g_3_']" replaced with ":is(...)" wrapper
--     and evaluate() pre-scan so basketball rows are correctly counted.
--   • App UX: guest profile card → login, fingerprint read-only,
--     sign-out wipes Football.com creds, FAB clearance +32dp,
--     bottom nav 35% glass opacity.
--
-- No schema changes in v9.6.3 — pure code release.
-- Run previous migrations (up to v9.6.2) first.
-- ============================================================

-- Verify period_scores column exists on schedules (added in v9.8.0 SQLite / should be in Supabase)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'schedules' AND column_name = 'period_scores'
    ) THEN
        ALTER TABLE public.schedules ADD COLUMN period_scores JSONB;
        COMMENT ON COLUMN public.schedules.period_scores IS
            'Basketball quarter/half scores. NULL for football. JSON: {"q1":{"home":28,"away":22},...}';
    END IF;
END;
$$;

-- Verify market_line + market_period exist on predictions
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'predictions' AND column_name = 'market_line'
    ) THEN
        ALTER TABLE public.predictions ADD COLUMN market_line REAL;
        COMMENT ON COLUMN public.predictions.market_line IS
            'Over/Under line targeted (e.g. 220.5). NULL for football 1X2.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'predictions' AND column_name = 'market_period'
    ) THEN
        ALTER TABLE public.predictions ADD COLUMN market_period TEXT DEFAULT 'full';
        COMMENT ON COLUMN public.predictions.market_period IS
            'Period targeted: full | h1 | h2 | q1 | q2 | q3 | q4';
    END IF;
END;
$$;
