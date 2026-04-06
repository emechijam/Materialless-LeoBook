#!/usr/bin/env python3
# generate_sync_jwt.py
#
# Generates a Supabase JWT for the 'leobook_sync' role.
# Requires SUPABASE_JWT_SECRET to be set in your environment (from Dashboard).
#
# Usage: python Scripts/generate_sync_jwt.py

import os
import time
import jwt
from dotenv import load_dotenv

def generate_jwt():
    # Load from project-root .env (up one dir from Scripts)
    env_path = os.path.join(os.path.dirname(__file__), "..", "leobookapp", ".env")
    load_dotenv(env_path)

    secret = os.getenv("SUPABASE_JWT_SECRET")
    
    if not secret:
        print("\n[!] ERROR: SUPABASE_JWT_SECRET not found in .env.")
        print("Please find it in Supabase Dashboard (Settings -> API -> JWT Settings) and add it to leobookapp/.env as:")
        print("SUPABASE_JWT_SECRET=your_secret_here\n")
        return

    # Standard Supabase claim structure
    payload = {
        "role": "leobook_sync",
        "iss": "supabase",
        "iat": int(time.time()),
        # Optional: set an 'exp' (expiry) if you want the key to expire. 
        # Default for sync/service keys in Supabase is usually set very high or never.
        # "exp": int(time.time()) + (3600 * 24 * 365) # 1 year
    }

    try:
        token = jwt.encode(payload, secret, algorithm="HS256")
        print("\n--- Scoped Sync JWT Generated Successfully ---")
        print("Copy the following line into your leobookapp/.env file:")
        print("-" * 50)
        print(f"SUPABASE_SYNC_KEY={token}")
        print("-" * 50)
        print("\nThen you can remove SUPABASE_SERVICE_KEY (or leave it as fallback).")
        print("The sync daemon will now run with restricted 'leobook_sync' permissions.\n")
    except Exception as e:
        print(f"[x] Error encoding JWT: {e}")

if __name__ == "__main__":
    generate_jwt()
