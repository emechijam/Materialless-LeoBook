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

def delete_leagues_from_sqlite(conn, league_ids: List[str], dry_run: bool = False):
    """Core logic to delete specific leagues and their data from SQLite."""
    if not league_ids:
        return

    logger.info(f"Purging {len(league_ids)} leagues from SQLite...")
    if dry_run:
        logger.info("[DRY RUN] Would delete leagues from SQLite.")
        return

    try:
        for l_id in league_ids:
            logger.info(f"Purging league: {l_id}")
            # Find fixtures
            f_cursor = conn.execute("SELECT fixture_id FROM schedules WHERE league_id = ?", (l_id,))
            fixtures = [row[0] for row in f_cursor.fetchall()]
            
            if fixtures:
                placeholders = ', '.join(['?'] * len(fixtures))
                # Delete associated data
                for table in ["predictions", "match_odds", "live_scores"]:
                    conn.execute(f"DELETE FROM {table} WHERE fixture_id IN ({placeholders})", fixtures)
                conn.execute("DELETE FROM schedules WHERE league_id = ?", (l_id,))

            # Delete league itself
            conn.execute("DELETE FROM leagues WHERE league_id = ?", (l_id,))
        
        # Cleanup teams: remove teams no longer in ANY schedule
        conn.execute("""
            DELETE FROM teams 
            WHERE team_id NOT IN (SELECT home_team_id FROM schedules)
              AND team_id NOT IN (SELECT away_team_id FROM schedules)
        """)
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"SQLite deletion failed: {e}")

def purge_sqlite(valid_ids: Set[str], dry_run: bool = False):
    """Purge orphans from local SQLite."""
    conn = get_connection()
    try:
        # 1. Get all orphan league IDs
        cursor = conn.execute("SELECT league_id FROM leagues")
        db_ids = {row[0] for row in cursor.fetchall()}
        orphans = list(db_ids - valid_ids)
        
        if not orphans:
            logger.info("No orphan leagues found in SQLite.")
            return

        delete_leagues_from_sqlite(conn, orphans, dry_run)
        logger.info("SQLite purge complete.")
        
    except Exception as e:
        logger.error(f"SQLite purge process failed: {e}")
    finally:
        conn.close()

def delete_leagues_from_supabase(league_ids: List[str], dry_run: bool = False):
    """Core logic to delete specific leagues and their data from Supabase."""
    if not league_ids:
        return

    supabase = get_supabase_client()
    if not supabase:
        logger.warning("Supabase client not available. Skipping cloud purge.")
        return

    logger.info(f"Purging {len(league_ids)} leagues from Supabase.")
    if dry_run:
        logger.info("[DRY RUN] Would delete leagues from Supabase.")
        return

    try:
        for l_id in league_ids:
            logger.info(f"Purging Supabase league: {l_id}")
            # Find fixtures
            f_resp = supabase.table("schedules").select("fixture_id").eq("league_id", l_id).execute()
            fixtures = [row['fixture_id'] for row in f_resp.data]
            
            if fixtures:
                # Chunk deletions if needed
                for i in range(0, len(fixtures), 50):
                    chunk = fixtures[i:i + 50]
                    for table in ["predictions", "match_odds", "live_scores"]:
                        supabase.table(table).delete().in_("fixture_id", chunk).execute()
                supabase.table("schedules").delete().eq("league_id", l_id).execute()

            # Delete league itself
            supabase.table("leagues").delete().eq("league_id", l_id).execute()
    except Exception as e:
        logger.error(f"Supabase deletion failed: {e}")

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

        delete_leagues_from_supabase(orphans, dry_run)
        logger.info("Supabase purge complete.")

    except Exception as e:
        logger.error(f"Supabase purge process failed: {e}")

def purge_by_contract(violator_ids: List[str], dry_run: bool = False):
    """Purge leagues identified as contract violators."""
    if not violator_ids:
        logger.info("No contract violators to purge.")
        return

    logger.info(f"Starting contract-based purge for {len(violator_ids)} leagues...")
    conn = get_connection()
    try:
        delete_leagues_from_sqlite(conn, violator_ids, dry_run)
        delete_leagues_from_supabase(violator_ids, dry_run)
    finally:
        conn.close()

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
