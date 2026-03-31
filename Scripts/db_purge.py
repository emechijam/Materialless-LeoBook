# db_purge.py: Removes orphan leagues and associated data from SQL and Supabase.
# Part of LeoBook Data — Maintenance
#
# Functions: purge_orphans(), delete_league_data()
# Called by: Leo.py | manual execution

import os
import json
import sqlite3
import logging
from typing import List, Set
from Data.Access.league_db import init_db, get_connection, DB_PATH
from Data.Access.supabase_client import get_supabase_client

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

LEAGUES_JSON_PATH = os.path.join("Data", "Store", "leagues.json")

def load_valid_league_ids() -> Set[str]:
    """Load valid league IDs from leagues.json."""
    if not os.path.exists(LEAGUES_JSON_PATH):
        logger.error(f"leagues.json not found at {LEAGUES_JSON_PATH}")
        return set()
    
    with open(LEAGUES_JSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return {l['league_id'] for l in data if 'league_id' in l}

def purge_sqlite(valid_ids: Set[str], dry_run: bool = False):
    """Purge orphans from local SQLite."""
    conn = get_connection()
    try:
        # 1. Get all orphan league IDs
        cursor = conn.execute("SELECT league_id FROM leagues")
        db_ids = {row[0] for row in cursor.fetchall()}
        orphans = db_ids - valid_ids
        
        if not orphans:
            logger.info("No orphan leagues found in SQLite.")
            return

        logger.info(f"Found {len(orphans)} orphan leagues in SQLite: {list(orphans)[:5]}...")

        if dry_run:
            logger.info("[DRY RUN] Would delete orphans from SQLite.")
            return

        # 2. Cascade delete
        for l_id in orphans:
            logger.info(f"Purging league: {l_id}")
            
            # Find fixtures to delete associated predictions/odds
            f_cursor = conn.execute("SELECT fixture_id FROM schedules WHERE league_id = ?", (l_id,))
            fixtures = [row[0] for row in f_cursor.fetchall()]
            
            if fixtures:
                # Delete predictions
                placeholders = ', '.join(['?'] * len(fixtures))
                conn.execute(f"DELETE FROM predictions WHERE fixture_id IN ({placeholders})", fixtures)
                # Delete match_odds
                conn.execute(f"DELETE FROM match_odds WHERE fixture_id IN ({placeholders})", fixtures)
                # Delete live_scores
                conn.execute(f"DELETE FROM live_scores WHERE fixture_id IN ({placeholders})", fixtures)
                # Delete schedules
                conn.execute("DELETE FROM schedules WHERE league_id = ?", (l_id,))

            # Delete league itself
            conn.execute("DELETE FROM leagues WHERE league_id = ?", (l_id,))
            
        # 3. Clean up teams (delete if they have no league_ids or only orphan league_ids)
        # This is a bit complex due to JSON mapping, but for P1 we focus on the core.
        # Simple approach: delete teams that aren't in ANY remaining league's schedules.
        conn.execute("""
            DELETE FROM teams 
            WHERE team_id NOT IN (SELECT home_team_id FROM schedules)
              AND team_id NOT IN (SELECT away_team_id FROM schedules)
        """)

        conn.commit()
        logger.info("SQLite purge complete.")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"SQLite purge failed: {e}")
    finally:
        conn.close()

def purge_supabase(valid_ids: Set[str], dry_run: bool = False):
    """Purge orphans from Supabase."""
    supabase = get_supabase_client()
    if not supabase:
        logger.warning("Supabase client not available. Skipping cloud purge.")
        return

    try:
        # 1. Get all orphan league IDs from Supabase
        response = supabase.table("leagues").select("league_id").execute()
        db_ids = {row['league_id'] for row in response.data}
        orphans = list(db_ids - valid_ids)

        if not orphans:
            logger.info("No orphan leagues found in Supabase.")
            return

        logger.info(f"Found {len(orphans)} orphan leagues in Supabase.")

        if dry_run:
            logger.info("[DRY RUN] Would delete orphans from Supabase.")
            return

        # 2. Cascade delete in Supabase
        # Note: Supabase RLS and Foreign Keys might handle some of this, 
        # but we do it manually to be safe.
        for l_id in orphans:
            logger.info(f"Purging Supabase league: {l_id}")
            
            # Find fixtures
            f_resp = supabase.table("schedules").select("fixture_id").eq("league_id", l_id).execute()
            fixtures = [row['fixture_id'] for row in f_resp.data]
            
            if fixtures:
                # Delete predictions
                supabase.table("predictions").delete().in_("fixture_id", fixtures).execute()
                # Delete match_odds
                supabase.table("match_odds").delete().in_("fixture_id", fixtures).execute()
                # Delete live_scores
                supabase.table("live_scores").delete().in_("fixture_id", fixtures).execute()
                # Delete schedules
                supabase.table("schedules").delete().eq("league_id", l_id).execute()

            # Delete league itself
            supabase.table("leagues").delete().eq("league_id", l_id).execute()
            
        logger.info("Supabase purge complete.")

    except Exception as e:
        logger.error(f"Supabase purge failed: {e}")

def run_purge(dry_run: bool = False):
    """Execute full purge."""
    logger.info(f"Starting purge pass (dry_run={dry_run})...")
    valid_ids = load_valid_league_ids()
    if not valid_ids:
        logger.error("No valid IDs found. Aborting purge to prevent total data loss.")
        return

    purge_sqlite(valid_ids, dry_run)
    purge_supabase(valid_ids, dry_run)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Purge orphan leagues from LeoBook DBs.")
    parser.add_argument("--dry-run", action="store_true", help="Don't perform actual deletion.")
    args = parser.parse_args()
    
    run_purge(dry_run=args.dry_run)
