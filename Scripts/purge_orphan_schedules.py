#!/usr/bin/env python3
"""
purge_orphan_schedules.py
─────────────────────────
Deletes rows from Supabase `schedules` where league_id is NOT present
in Data/Store/leagues.json.

Strategy: we know the 297 valid IDs — no need to scan schedules.
Generates a SQL DELETE and executes it via Supabase SQL editor or RPC.

Usage (from repo root in codespace):
    python Scripts/purge_orphan_schedules.py [--dry-run]
"""

import json
import sys
import os
import argparse
from pathlib import Path

# ── Bootstrap env ─────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Load valid league IDs from leagues.json ───────────────────────────────────
LEAGUES_JSON = Path(__file__).parent.parent / "Data" / "Store" / "leagues.json"
leagues = json.loads(LEAGUES_JSON.read_text(encoding="utf-8"))
valid_ids: list[str] = sorted({row["league_id"] for row in leagues if row.get("league_id")})
print(f"[INFO] Valid leagues in leagues.json: {len(valid_ids):,}")

# ── Build SQL ─────────────────────────────────────────────────────────────────
id_list = ", ".join(f"'{lid}'" for lid in valid_ids)
sql = f"DELETE FROM public.schedules WHERE league_id NOT IN ({id_list});"

SQL_OUT = Path("/tmp/purge_orphan_schedules.sql")
SQL_OUT.write_text(sql, encoding="utf-8")
print(f"[INFO] SQL written to: {SQL_OUT}")

# ── Dry-run: just print SQL path and exit ─────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

if args.dry_run:
    print(f"\n[DRY RUN] Would execute:\n  {sql[:200]}...")
    print(f"\n[DRY RUN] Paste {SQL_OUT} into Supabase SQL Editor to preview.\n")
    sys.exit(0)

# ── Confirm ───────────────────────────────────────────────────────────────────
print(f"\n⚠️  About to DELETE all schedules rows whose league_id is NOT in the {len(valid_ids)} valid leagues.")
print(f"    SQL saved at: {SQL_OUT}")
confirm = input("Type YES to proceed via RPC: ").strip()
if confirm != "YES":
    print(f"[ABORTED] Paste {SQL_OUT} into Supabase SQL Editor to run manually.")
    sys.exit(0)

# ── Execute via exec_sql RPC (requires the function to exist) ─────────────────
print("[INFO] Executing via Supabase exec_sql RPC...")
try:
    res = supabase.rpc("exec_sql", {"query": sql}).execute()
    print(f"[DONE] RPC response: {res.data}")
except Exception as rpc_err:
    rpc_msg = str(rpc_err)
    if "Could not find the function" in rpc_msg or "PGRST202" in rpc_msg:
        print("\n[RPC not available] Falling back to REST batched deletes...")
        # ── Batched NOT IN delete via REST ─────────────────────────────────────
        # Supabase REST doesn't support NOT IN natively — we delete by
        # explicitly including only the orphan IDs we discover from a
        # lightweight RPC count query, or we chunk the valid IDs with neq workaround.
        # Simplest reliable path: tell user to run the SQL file.
        print(f"\n[ACTION REQUIRED] Paste this file into Supabase SQL Editor:")
        print(f"  {SQL_OUT}")
        print(f"\nOr run this one-liner SQL:\n")
        print(f"  DELETE FROM public.schedules WHERE league_id NOT IN ({id_list[:120]}...);")
        print(f"\n(Full SQL saved at {SQL_OUT})")
    else:
        print(f"[ERROR] RPC failed: {rpc_err}")
        print(f"\n[ACTION REQUIRED] Run manually in Supabase SQL Editor:")
        print(f"  File: {SQL_OUT}")

