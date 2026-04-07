#!/usr/bin/env python3
"""
purge_orphan_schedules.py
─────────────────────────
Deletes rows from Supabase `schedules` where league_id is NOT present
in Data/Store/leagues.json.

Usage (from repo root in codespace):
    python Scripts/purge_orphan_schedules.py [--dry-run]

Flags:
    --dry-run   Print counts only — no deletes.
"""

import json
import sys
import os
import argparse
from pathlib import Path

# ── Bootstrap env ────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]  # needs service role for bulk deletes
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Load valid league IDs ─────────────────────────────────────────────────────
LEAGUES_JSON = Path(__file__).parent.parent / "Data" / "Store" / "leagues.json"
leagues = json.loads(LEAGUES_JSON.read_text(encoding="utf-8"))
valid_ids: set[str] = {row["league_id"] for row in leagues if row.get("league_id")}
print(f"[INFO] Valid leagues in leagues.json: {len(valid_ids):,}")

# ── Discover distinct league_ids currently in schedules ──────────────────────
print("[INFO] Fetching distinct league_ids from schedules (paginating)...")
all_league_ids_in_db: set[str] = set()
offset = 0
PAGE = 1000
while True:
    res = (
        supabase.table("schedules")
        .select("league_id")
        .limit(PAGE)
        .offset(offset)
        .execute()
    )
    rows = res.data
    if not rows:
        break
    for r in rows:
        lid = r.get("league_id")
        if lid:
            all_league_ids_in_db.add(lid)
    offset += len(rows)
    if len(rows) < PAGE:
        break

print(f"[INFO] Distinct league_ids in schedules: {len(all_league_ids_in_db):,}")

orphan_ids = sorted(all_league_ids_in_db - valid_ids)
print(f"[INFO] Orphan league_ids (to purge): {len(orphan_ids):,}")

if not orphan_ids:
    print("[OK] Nothing to delete. schedules is clean.")
    sys.exit(0)

print("\nOrphan league_ids:")
for lid in orphan_ids:
    print(f"  {lid}")

# ── Dry-run guard ─────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser()
parser.add_argument("--dry-run", action="store_true")
args = parser.parse_args()

if args.dry_run:
    print("\n[DRY RUN] No deletes performed.")
    sys.exit(0)

# ── Confirm ───────────────────────────────────────────────────────────────────
print(f"\n⚠️  About to DELETE all schedules rows for {len(orphan_ids)} orphan league(s).")
confirm = input("Type YES to proceed: ").strip()
if confirm != "YES":
    print("[ABORTED]")
    sys.exit(0)

# ── Delete in batches of 50 IDs (Supabase IN clause limit) ───────────────────
BATCH = 50
total_deleted = 0
for i in range(0, len(orphan_ids), BATCH):
    chunk = orphan_ids[i : i + BATCH]
    # Supabase REST: .in_() maps to ?league_id=in.(...)
    res = (
        supabase.table("schedules")
        .delete()
        .in_("league_id", chunk)
        .execute()
    )
    deleted = len(res.data) if res.data else 0
    total_deleted += deleted
    print(f"  Batch {i//BATCH + 1}: deleted {deleted:,} rows  (league_ids: {chunk[:3]}{'...' if len(chunk)>3 else ''})")

print(f"\n[DONE] Total rows deleted: {total_deleted:,}")
