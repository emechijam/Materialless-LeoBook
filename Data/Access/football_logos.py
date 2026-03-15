# football_logos.py: Football logo and country flag download orchestration.
# Part of LeoBook Data — Access Layer
# CLI: python -m Data.Access.football_logos [options]

import argparse
import asyncio
import os
import re
from typing import Optional

from Data.Access.logo_downloader import (
    _PlaywrightPool, _build_session, _download_league_zip,
    _scrape_via_requests, _download_country, BASE_DIR,
)

LOGOS_DIR = os.path.join("Data", "Store", "logos")
COUNTRIES_DIR = os.path.join("Data", "Store", "logos", "countries")


def _upload_to_supabase(local_path: str, bucket: str, remote_name: str) -> str:
    """Upload a local file to Supabase Storage. Returns public URL or empty string."""
    try:
        from Data.Access.supabase_client import get_supabase_client
        client = get_supabase_client()
        if not client:
            return ""
        sb_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        abs_path = os.path.join(BASE_DIR, local_path) if not os.path.isabs(local_path) else local_path
        if not os.path.exists(abs_path):
            return ""
        with open(abs_path, "rb") as f:
            client.storage.from_(bucket).upload(
                path=remote_name, file=f,
                file_options={"cache-control": "3600", "upsert": "true"}
            )
        return f"{sb_url}/storage/v1/object/public/{bucket}/{remote_name}"
    except Exception:
        return ""


def _refresh_country_list() -> list:
    """Fetch the current country list from the LeoBook country.json."""
    import json
    country_json = os.path.join(BASE_DIR, "Data", "Store", "country.json")
    if not os.path.exists(country_json):
        return []
    with open(country_json, "r", encoding="utf-8") as f:
        return json.load(f)


def download_all_logos(limit: Optional[int] = None) -> int:
    """Download league logo packs from standard sources.

    Sources: worldfootball.net zip packs + direct CDN.
    Returns total number of logo files downloaded.
    """
    os.makedirs(os.path.join(BASE_DIR, LOGOS_DIR), exist_ok=True)
    total = 0

    # Known logo pack URLs — extend as new sources are found
    logo_pack_urls = [
        # Add verified logo pack ZIP URLs here as league coverage grows
    ]

    session = _build_session()
    for idx, (url, extract_subdir) in enumerate(logo_pack_urls, 1):
        if limit and idx > limit:
            break
        dest = os.path.join(LOGOS_DIR, extract_subdir)
        count = _download_league_zip(url, dest)
        print(f"  [Logos] Pack {idx}: {count} files -> {dest}")
        total += count

    return total


def download_all_countries(limit: Optional[int] = None) -> int:
    """Download country flag images from country.json sources.

    Returns total number of flags downloaded.
    """
    os.makedirs(os.path.join(BASE_DIR, COUNTRIES_DIR), exist_ok=True)
    countries = _refresh_country_list()
    if limit:
        countries = countries[:limit]

    downloaded = 0
    for c in countries:
        flag_url = c.get("flag_url") or c.get("flag")
        name = c.get("name") or c.get("iso2") or "unknown"
        slug = re.sub(r"[^\w]", "_", name.lower()).strip("_")
        dest = os.path.join(COUNTRIES_DIR, f"{slug}.png")
        if flag_url and _download_country(flag_url, dest):
            downloaded += 1

    print(f"  [Flags] {downloaded}/{len(countries)} country flags downloaded")
    return downloaded


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download football logos and country flags")
    parser.add_argument("--logos",     action="store_true", help="Download league logo packs")
    parser.add_argument("--countries", action="store_true", help="Download country flags")
    parser.add_argument("--limit",     type=int, default=None, help="Limit entries processed")
    args = parser.parse_args()

    if args.logos or (not args.logos and not args.countries):
        download_all_logos(limit=args.limit)
    if args.countries or (not args.logos and not args.countries):
        download_all_countries(limit=args.limit)
