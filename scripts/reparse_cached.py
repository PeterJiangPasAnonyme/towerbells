#!/usr/bin/env python3
"""Re-parse cached raw HTML into SQLite without network requests."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.config import BASE_URL, DB_PATH, RAW_HTML_DIR
from scraper.db import connect, upsert_site
from scraper.parse_site import parse_site_page


def main() -> None:
    conn = connect(DB_PATH)
    scraped_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    files = sorted(RAW_HTML_DIR.glob("*.htm"))
    for i, path in enumerate(files, start=1):
        site_id = path.stem.upper()
        page_filename = f"{site_id}.HTM"
        html = path.read_text(encoding="utf-8", errors="replace")
        parsed = parse_site_page(site_id, html, page_filename, f"{BASE_URL}{page_filename}")
        upsert_site(conn, parsed, scraped_at)
        if i % 200 == 0 or i == len(files):
            print(f"[reparse {i}/{len(files)}] {site_id}", flush=True)
    conn.commit()
    print(f"Reparsed {len(files)} sites from {RAW_HTML_DIR}")


if __name__ == "__main__":
    main()
