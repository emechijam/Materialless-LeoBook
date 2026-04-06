# fs_league_images.py: Crest image download and Supabase Storage upload.
# Part of LeoBook Modules — Flashscore

import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Set

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Config ────────────────────────────────────────────────────────────────────
DOWNLOAD_WORKERS = 8
REQUEST_TIMEOUT = 15

# ── Thread pool ───────────────────────────────────────────────────────────────
executor = ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS)

# ── Supabase storage globals ──────────────────────────────────────────────────
_supabase_storage = None
_supabase_url = ""
_uploaded_crests: Set[str] = set()


def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "_", s)
    return s.strip("_")


def _download_image(url: str, dest_path: str) -> str:
    if not url or url.startswith("data:"):
        return ""
    abs_dest = os.path.join(BASE_DIR, dest_path) if not os.path.isabs(dest_path) else dest_path
    if os.path.exists(abs_dest):
        return dest_path
    try:
        os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Referer": "https://www.flashscore.com/",
        })
        if resp.status_code == 200 and len(resp.content) > 100:
            with open(abs_dest, "wb") as f:
                f.write(resp.content)
            return dest_path
    except Exception:
        pass
    return ""


def schedule_image_download(url: str, dest_path: str):
    return executor.submit(_download_image, url, dest_path)


def _init_supabase_storage():
    """Initialise Supabase Storage using the service-role key.

    Supabase Storage uses bucket policies, NOT Postgres RLS.
    The scoped SUPABASE_SYNC_KEY JWT has no Storage access and returns
    400 on every upload — the service-role key is required here.
    """
    global _supabase_storage, _supabase_url
    if _supabase_storage is not None:
        return _supabase_storage, _supabase_url
    try:
        from Data.Access.supabase_client import get_supabase_storage_client
        client = get_supabase_storage_client()
        if client:
            _supabase_storage = client.storage
            _supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
            try:
                existing = {b.name for b in _supabase_storage.list_buckets()}
                for bucket in ("league-crests", "team-crests", "flags"):
                    if bucket not in existing:
                        _supabase_storage.create_bucket(bucket, options={"public": True})
            except Exception:
                pass
            return _supabase_storage, _supabase_url
    except Exception:
        pass
    _supabase_storage = False
    return None, ""


def upload_crest_to_supabase(local_path: str, bucket: str, remote_name: str) -> str:
    key = f"{bucket}/{remote_name}"
    if key in _uploaded_crests:
        storage, sb_url = _init_supabase_storage()
        return f"{sb_url}/storage/v1/object/public/{key}" if sb_url else ""
    storage, sb_url = _init_supabase_storage()
    if not storage or not sb_url:
        return ""
    abs_path = os.path.join(BASE_DIR, local_path) if not os.path.isabs(local_path) else local_path
    if not os.path.exists(abs_path):
        return ""
    public_url = f"{sb_url}/storage/v1/object/public/{bucket}/{remote_name}"
    try:
        with open(abs_path, "rb") as f:
            storage.from_(bucket).upload(
                path=remote_name, file=f,
                file_options={"cache-control": "3600", "upsert": "true"},
            )
        _uploaded_crests.add(key)
        return public_url
    except Exception as e:
        err = str(e).lower()
        # 400/409 "already exists" — file is already in storage, just return the URL
        if "already" in err or "duplicate" in err or "400" in err or "409" in err:
            _uploaded_crests.add(key)  # Cache so we skip next time
            return public_url
        return ""
