-- supabase_migration_v9.5.6.sql
-- LeoBook Chapter 1: Data Pipeline Hardening & Rationale Integration
-- Run this in the Supabase SQL Editor.

-- 1. Modernize PREDICTIONS table for Rich Rationale
ALTER TABLE predictions 
ADD COLUMN IF NOT EXISTS form_home JSONB,
ADD COLUMN IF NOT EXISTS form_away JSONB,
ADD COLUMN IF NOT EXISTS h2h_summary JSONB,
ADD COLUMN IF NOT EXISTS standings_home JSONB,
ADD COLUMN IF NOT EXISTS standings_away JSONB,
ADD COLUMN IF NOT EXISTS rule_engine_decision TEXT,
ADD COLUMN IF NOT EXISTS rl_decision JSONB,
ADD COLUMN IF NOT EXISTS ensemble_weights JSONB,
ADD COLUMN IF NOT EXISTS rec_qualifications JSONB,
ADD COLUMN IF NOT EXISTS market_reliability_score DOUBLE PRECISION;

-- 2. Add helpful indexes for the new Rationale UI
CREATE INDEX IF NOT EXISTS idx_predictions_fixture_id ON predictions(fixture_id);
CREATE INDEX IF NOT EXISTS idx_predictions_league_date ON predictions(country_league, date);

-- 3. Enabling Realtime for these columns (optional but recommended for live updates)
-- Assuming 'predictions' is already in the 'supabase_realtime' publication.
-- If not, run:
-- ALTER PUBLICATION supabase_realtime ADD TABLE predictions;

-- 4. Verify Column Types
COMMENT ON COLUMN predictions.form_home IS 'List of last 10 matches for home team with scores/dates';
COMMENT ON COLUMN predictions.form_away IS 'List of last 10 matches for away team with scores/dates';
COMMENT ON COLUMN predictions.h2h_summary IS 'List of head-to-head encounters';
COMMENT ON COLUMN predictions.rec_qualifications IS 'Boolean metadata (high_form, h2h_rich, etc.) for UI badges';

-- 5. Final Cleanup (Optional: remove deprecated market_reliability string if exists)
-- DO NOT RUN UNTIL DATA IS VERIFIED:
-- ALTER TABLE predictions DROP COLUMN IF EXISTS market_reliability;
