import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('leobookapp/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

# Step 1: Recreate the VIEW with exact INNER JOIN matching
view_sql = """
CREATE OR REPLACE VIEW public.fb_match_candidates AS
SELECT
    fb.site_match_id,
    fb.date AS fb_date, fb.match_time AS fb_time,
    fb.home_team AS fb_home, fb.away_team AS fb_away,
    fb.league AS fb_league, fb.url AS fb_url,
    s.fixture_id,
    s.date AS s_date, s.match_time AS s_time,
    s.home_team AS s_home, s.away_team AS s_away,
    s.home_team_id, s.away_team_id, s.league_id, s.region_league,
    CASE
        WHEN fb.date::DATE = s.date::DATE THEN 100
        WHEN ABS(EXTRACT(EPOCH FROM (fb.date::DATE - s.date::DATE)) / 86400) <= 1 THEN 90
        ELSE 0
    END AS confidence
FROM public.fb_matches fb
INNER JOIN public.schedules s
    ON s.league_id = fb.league_id
    AND public.normalize_team_name(fb.home_team) = public.normalize_team_name(s.home_team)
    AND public.normalize_team_name(fb.away_team) = public.normalize_team_name(s.away_team)
    AND ABS(EXTRACT(EPOCH FROM (fb.date::DATE - s.date::DATE)) / 86400) <= 1
WHERE fb.date IS NOT NULL AND s.date IS NOT NULL
  AND (fb.fixture_id IS NULL OR fb.matched IS NULL OR fb.matched = 'false');
"""

# Step 2: Recreate RPC functions
rpc_sql = """
CREATE OR REPLACE FUNCTION public.match_fb_to_schedule(p_site_match_id TEXT)
RETURNS TABLE(fixture_id TEXT, confidence INTEGER, home_team_id TEXT, away_team_id TEXT,
              s_home TEXT, s_away TEXT, s_date TEXT, s_time TEXT)
LANGUAGE sql STABLE AS $$
    SELECT c.fixture_id, c.confidence, c.home_team_id, c.away_team_id,
           c.s_home, c.s_away, c.s_date, c.s_time
    FROM public.fb_match_candidates c
    WHERE c.site_match_id = p_site_match_id AND c.confidence > 0
    ORDER BY c.confidence DESC, c.s_date ASC LIMIT 1;
$$;
"""

batch_sql = """
CREATE OR REPLACE FUNCTION public.auto_match_fb_matches()
RETURNS INTEGER LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE matched_count INTEGER := 0; rec RECORD;
BEGIN
    FOR rec IN
        SELECT DISTINCT ON (site_match_id) site_match_id, fixture_id AS resolved_fixture_id, confidence
        FROM public.fb_match_candidates WHERE confidence >= 90
        ORDER BY site_match_id, confidence DESC
    LOOP
        UPDATE public.fb_matches
        SET fixture_id = rec.resolved_fixture_id, matched = 'sql_v2.0', last_updated = NOW()
        WHERE site_match_id = rec.site_match_id AND (fixture_id IS NULL OR fixture_id = '');
        IF FOUND THEN matched_count := matched_count + 1; END IF;
    END LOOP;
    RETURN matched_count;
END;
$$;
"""

trigger_sql = """
CREATE OR REPLACE FUNCTION public.trg_fn_auto_match_fb()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE best RECORD;
BEGIN
    IF NEW.fixture_id IS NOT NULL AND NEW.fixture_id <> '' THEN RETURN NEW; END IF;
    SELECT fixture_id, confidence INTO best FROM public.match_fb_to_schedule(NEW.site_match_id) LIMIT 1;
    IF FOUND AND best.confidence >= 90 THEN
        NEW.fixture_id := best.fixture_id; NEW.matched := 'sql_v2.0'; NEW.last_updated := NOW();
    END IF;
    RETURN NEW;
END;
$$;
"""

index_sql = """
CREATE INDEX IF NOT EXISTS idx_fb_matches_unresolved ON public.fb_matches (league_id, date)
    WHERE fixture_id IS NULL OR fixture_id = '';
CREATE INDEX IF NOT EXISTS idx_schedules_league_date_teams ON public.schedules (league_id, date, home_team, away_team);
"""

steps = [
    ("VIEW fb_match_candidates", view_sql),
    ("RPC match_fb_to_schedule", rpc_sql),
    ("RPC auto_match_fb_matches", batch_sql),
    ("TRIGGER trg_fn_auto_match_fb", trigger_sql),
    ("INDEXES", index_sql),
]

for label, sql in steps:
    try:
        supabase.rpc('exec_sql', {'query': sql}).execute()
        print(f"[OK] {label}")
    except Exception as e:
        print(f"[ERR] {label}: {e}")

# Verify
try:
    result = supabase.from_('fb_match_candidates').select('*', count='exact').limit(3).execute()
    print(f"\n[OK] VIEW verified -- {result.count} candidates found")
    for row in result.data:
        print(f"   {row['fb_home']} vs {row['fb_away']} -> {row['s_home']} vs {row['s_away']} (conf:{row['confidence']})")
except Exception as e:
    print(f"[ERR] Verify: {e}")
