-- ============================================================
-- LeoBook Supabase Migration v9.6.3
-- ============================================================
-- Release notes:
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
