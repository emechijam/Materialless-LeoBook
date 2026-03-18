import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('leobookapp/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

sql = """
CREATE OR REPLACE VIEW public.computed_standings AS
WITH all_matches AS (
    SELECT
        league_id, season,
        home_team_id AS team_id, home_team AS team_name,
        home_score::INTEGER AS gf, away_score::INTEGER AS ga
    FROM public.schedules
    WHERE home_score IS NOT NULL AND away_score IS NOT NULL
      AND match_status = 'finished'
    UNION ALL
    SELECT
        league_id, season,
        away_team_id AS team_id, away_team AS team_name,
        away_score::INTEGER AS gf, home_score::INTEGER AS ga
    FROM public.schedules
    WHERE home_score IS NOT NULL AND away_score IS NOT NULL
      AND match_status = 'finished'
)
SELECT
    league_id, season, team_id, team_name,
    COUNT(*)::INTEGER AS played,
    SUM(CASE WHEN gf > ga THEN 1 ELSE 0 END)::INTEGER AS won,
    SUM(CASE WHEN gf = ga THEN 1 ELSE 0 END)::INTEGER AS drawn,
    SUM(CASE WHEN gf < ga THEN 1 ELSE 0 END)::INTEGER AS lost,
    SUM(gf)::INTEGER AS goals_for,
    SUM(ga)::INTEGER AS goals_against,
    (SUM(gf) - SUM(ga))::INTEGER AS goal_difference,
    SUM(CASE WHEN gf > ga THEN 3 WHEN gf = ga THEN 1 ELSE 0 END)::INTEGER AS points
FROM all_matches
GROUP BY league_id, season, team_id, team_name;
"""

grant_sql = "GRANT SELECT ON public.computed_standings TO anon, authenticated, service_role;"

try:
    supabase.rpc('exec_sql', {'query': sql}).execute()
    print("[OK] computed_standings VIEW created successfully.")
except Exception as e:
    print(f"[ERR] Error creating VIEW: {e}")

try:
    supabase.rpc('exec_sql', {'query': grant_sql}).execute()
    print("[OK] GRANT SELECT applied.")
except Exception as e:
    print(f"[ERR] Error granting SELECT: {e}")

# Verify it works
try:
    result = supabase.from_('computed_standings').select('*', count='exact').limit(5).execute()
    print(f"[OK] VIEW verified -- {result.count} total rows, showing first {len(result.data)}:")
    for row in result.data:
        print(f"   {row['team_name']} | P:{row['played']} W:{row['won']} D:{row['drawn']} L:{row['lost']} Pts:{row['points']}")
except Exception as e:
    print(f"[ERR] Verification failed: {e}")
