-- =============================================
-- Create computed_standings VIEW in Supabase
-- Run this in the Supabase SQL Editor
-- =============================================

CREATE OR REPLACE VIEW public.computed_standings AS
WITH all_matches AS (
    SELECT
        league_id, NULL::TEXT AS season,
        home_team_id AS team_id, home_team AS team_name,
        home_score::INTEGER AS gf, away_score::INTEGER AS ga
    FROM public.schedules
    WHERE home_score IS NOT NULL AND away_score IS NOT NULL
      AND match_status = 'finished'
    UNION ALL
    SELECT
        league_id, NULL::TEXT AS season,
        away_team_id AS team_id, away_team AS team_name,
        away_score::INTEGER AS gf, home_score::INTEGER AS ga
    FROM public.schedules
    WHERE home_score IS NOT NULL AND away_score IS NOT NULL
      AND match_status = 'finished'
)
SELECT
    league_id, season, team_id, team_name,
    COUNT(*) AS played,
    SUM(CASE WHEN gf > ga THEN 1 ELSE 0 END) AS won,
    SUM(CASE WHEN gf = ga THEN 1 ELSE 0 END) AS drawn,
    SUM(CASE WHEN gf < ga THEN 1 ELSE 0 END) AS lost,
    SUM(gf) AS goals_for,
    SUM(ga) AS goals_against,
    SUM(gf) - SUM(ga) AS goal_difference,
    SUM(CASE WHEN gf > ga THEN 3 WHEN gf = ga THEN 1 ELSE 0 END) AS points
FROM all_matches
GROUP BY league_id, season, team_id, team_name;

GRANT SELECT ON public.computed_standings TO anon, authenticated, service_role;
