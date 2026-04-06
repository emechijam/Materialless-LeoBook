# supabase_client.py: Supabase client factory for the LeoBook sync layer.
# Part of LeoBook Data — Access Layer
#
# Functions: get_supabase_client()
#
# KEY HIERARCHY (checked in order):
#   1. SUPABASE_SYNC_KEY  — Scoped JWT for the leobook_sync role (preferred).
#                           Respects RLS. Use after running supabase_rls_setup.sql.
#   2. SUPABASE_SERVICE_KEY — Admin key that bypasses RLS entirely (fallback).
#                             Safe for a private backend but over-privileged.
#                             Logs a warning when used.
#
# To migrate from service key → scoped key:
#   1. Run Data/Access/supabase_rls_setup.sql in the Supabase SQL Editor.
#   2. Generate a JWT for the leobook_sync role.
#   3. Add SUPABASE_SYNC_KEY=<jwt> to .env.
#   4. Remove SUPABASE_SERVICE_KEY from .env once sync is confirmed working.

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Singleton instance
_client: Optional[Client] = None


def get_supabase_client() -> Optional[Client]:
    """
    Return a cached Supabase client.

    Prefers SUPABASE_SYNC_KEY (scoped, RLS-aware) over SUPABASE_SERVICE_KEY
    (admin, bypasses RLS). Falls back to the service key with a warning so
    existing deployments keep working without any .env changes.

    Returns None if neither key nor the URL is configured.
    """
    global _client
    if _client:
        return _client

    # Load environment variables
    # Check root .env first, then leobookapp/.env for robustness
    load_dotenv()
    if not os.getenv("SUPABASE_SYNC_KEY"):
        # If running from root, leobookapp/.env might contain the keys
        sub_env = os.path.join(os.getcwd(), "leobookapp", ".env")
        if os.path.exists(sub_env):
            load_dotenv(sub_env, override=True)

    url = os.getenv("SUPABASE_URL")
    if not url:
        logger.warning("[!] SUPABASE_URL missing. Sync disabled.")
        return None

    # Prefer scoped sync key; fall back to full-admin service key
    sync_key     = os.getenv("SUPABASE_SYNC_KEY")
    service_key  = os.getenv("SUPABASE_SERVICE_KEY")

    if sync_key:
        key = sync_key
        logger.info("[Supabase] Using scoped SUPABASE_SYNC_KEY (RLS-aware).")
    elif service_key:
        key = service_key
        logger.warning(
            "[Supabase] Using SUPABASE_SERVICE_KEY (admin — bypasses RLS). "
            "Run Data/Access/supabase_rls_setup.sql and set SUPABASE_SYNC_KEY "
            "to replace this with a scoped key."
        )
        print(
            "  [Supabase] WARNING: connecting with SERVICE_KEY (bypasses RLS). "
            "See Data/Access/supabase_rls_setup.sql to switch to a scoped key."
        )
    else:
        logger.warning(
            "[!] Neither SUPABASE_SYNC_KEY nor SUPABASE_SERVICE_KEY is set. Sync disabled."
        )
        return None

    try:
        _client = create_client(url, key)
        return _client
    except Exception as e:
        logger.error(f"[x] Failed to initialize Supabase client: {e}")
        return None
