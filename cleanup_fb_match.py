import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv('leobookapp/.env')
url = os.getenv('SUPABASE_URL')
key = os.getenv('SUPABASE_SERVICE_KEY')
supabase = create_client(url, key)

cleanup_steps = [
    ("DROP trigger", "DROP TRIGGER IF EXISTS trg_auto_match_fb_matches ON public.fb_matches;"),
    ("DROP trg_fn_auto_match_fb", "DROP FUNCTION IF EXISTS public.trg_fn_auto_match_fb();"),
    ("DROP auto_match_fb_matches", "DROP FUNCTION IF EXISTS public.auto_match_fb_matches();"),
    ("DROP match_fb_to_schedule", "DROP FUNCTION IF EXISTS public.match_fb_to_schedule(TEXT);"),
    ("DROP fb_match_candidates", "DROP VIEW IF EXISTS public.fb_match_candidates;"),
    ("CREATE idx_schedules_league_date", "CREATE INDEX IF NOT EXISTS idx_schedules_league_date ON public.schedules (league_id, date);"),
]

for label, sql in cleanup_steps:
    try:
        supabase.rpc('exec_sql', {'query': sql}).execute()
        print(f"[OK] {label}")
    except Exception as e:
        print(f"[ERR] {label}: {e}")

print("\nDone. fb_match_candidates VIEW and all related RPCs/triggers removed from Supabase.")
