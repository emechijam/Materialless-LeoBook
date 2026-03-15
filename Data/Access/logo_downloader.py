# logo_downloader.py: Low-level logo and flag download workers.
# Part of LeoBook Data — Access Layer

import os
import re
import zipfile
import tempfile
import requests
from typing import Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REQUEST_TIMEOUT = 20
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
}


class _PlaywrightPool:
    """Minimal Playwright browser pool for logo scraping."""

    def __init__(self, max_workers: int = 3):
        self.max_workers = max_workers
        self._browsers = []

    async def acquire(self):
        """Acquire a browser page from the pool."""
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_context(
            user_agent=DOWNLOAD_HEADERS["User-Agent"],
            viewport={"width": 1280, "height": 800},
        ).then(lambda ctx: ctx.new_page())
        self._browsers.append((pw, browser))
        return page

    async def shutdown(self):
        for pw, browser in self._browsers:
            try:
                await browser.close()
                await pw.stop()
            except Exception:
                pass
        self._browsers.clear()


def _build_session() -> requests.Session:
    """Build a requests session with standard LeoBook headers."""
    s = requests.Session()
    s.headers.update(DOWNLOAD_HEADERS)
    return s


def _scrape_via_requests(url: str, dest_path: str) -> bool:
    """Attempt to download a resource via requests. Returns True on success."""
    abs_dest = os.path.join(BASE_DIR, dest_path) if not os.path.isabs(dest_path) else dest_path
    if os.path.exists(abs_dest):
        return True
    try:
        os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
        session = _build_session()
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200 and len(resp.content) > 100:
            with open(abs_dest, "wb") as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False


def _download_league_zip(zip_url: str, extract_to: str) -> int:
    """Download a ZIP file of league logos and extract. Returns count of extracted files."""
    abs_extract = os.path.join(BASE_DIR, extract_to) if not os.path.isabs(extract_to) else extract_to
    os.makedirs(abs_extract, exist_ok=True)
    try:
        session = _build_session()
        resp = session.get(zip_url, timeout=30)
        if resp.status_code != 200:
            return 0
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = tmp.name
        count = 0
        with zipfile.ZipFile(tmp_path, "r") as zf:
            for member in zf.namelist():
                if member.lower().endswith((".png", ".svg", ".jpg", ".webp")):
                    zf.extract(member, abs_extract)
                    count += 1
        os.unlink(tmp_path)
        return count
    except Exception:
        return 0


def _download_country(url: str, dest_path: str) -> bool:
    """Download a single country flag. Returns True on success."""
    return _scrape_via_requests(url, dest_path)
