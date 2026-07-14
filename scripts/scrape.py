#!/usr/bin/env python3
"""Scrape towerbells.org traditional carillon data into SQLite."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.config import BASE_URL, DATA_DIR, DB_PATH, RAW_HTML_DIR
from scraper.db import connect, replace_list_entries, upsert_list_page, upsert_site
from scraper.discover import discover_list_pages, discover_site_ids, parse_list_page
from scraper.fetch import fetch
from scraper.parse_site import parse_site_page

PROGRESS_PATH = DATA_DIR / "scrape_progress.json"


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_progress(
    phase: str,
    current: int,
    total: int,
    site_id: str | None = None,
) -> None:
    PROGRESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "phase": phase,
        "current": current,
        "total": total,
        "site_id": site_id,
        "updated_at": now_iso(),
    }
    PROGRESS_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def scrape_lists(conn, *, limit: int | None = None) -> int:
    scraped_at = now_iso()
    pages = discover_list_pages()
    if limit is not None:
        pages = pages[:limit]

    total = len(pages)
    for i, page in enumerate(pages, start=1):
        try:
            meta, entries = parse_list_page(page.filename)
        except RuntimeError as exc:
            print(f"[lists {i}/{total}] SKIP {page.filename}: {exc}", flush=True)
            write_progress("lists", i, total, page.filename)
            continue

        list_page_id = upsert_list_page(
            conn,
            meta.filename,
            meta.region,
            meta.list_type,
            len(entries),
            scraped_at,
        )
        replace_list_entries(
            conn,
            list_page_id,
            [(e.site_id, e.display_name, e.rank, e.line_suffix) for e in entries],
            scraped_at,
        )
        print(f"[lists {i}/{total}] {page.filename}: {len(entries)} entries", flush=True)
        write_progress("lists", i, total, page.filename)

    conn.commit()
    return total


def scrape_sites(conn, *, limit: int | None = None, cache_html: bool = True) -> int:
    scraped_at = now_iso()
    site_pages = discover_site_ids()
    items = sorted(site_pages.items())
    if limit is not None:
        items = items[:limit]

    total = len(items)
    for i, (site_id, page_filename) in enumerate(items, start=1):
        page_url = f"{BASE_URL}{page_filename}"
        try:
            html = fetch(page_filename)
        except RuntimeError as exc:
            print(f"[sites {i}/{total}] SKIP {site_id}: {exc}", flush=True)
            write_progress("sites", i, total, site_id)
            continue

        if cache_html:
            (RAW_HTML_DIR / page_filename.lower()).write_text(html, encoding="utf-8")

        parsed = parse_site_page(site_id, html, page_filename, page_url)
        upsert_site(conn, parsed, scraped_at)

        label = parsed.full_title or parsed.short_name or site_id
        print(f"[sites {i}/{total}] {site_id}: {label}", flush=True)
        write_progress("sites", i, total, site_id)

    conn.commit()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DB_PATH, help="SQLite database path")
    parser.add_argument(
        "--phase",
        choices=("lists", "sites", "all"),
        default="all",
        help="Which scrape phase to run",
    )
    parser.add_argument("--limit", type=int, default=None, help="Limit pages scraped (for testing)")
    parser.add_argument("--no-cache", action="store_true", help="Do not save raw HTML files")
    args = parser.parse_args()

    conn = connect(args.db)
    print(f"Database: {args.db}")

    if args.phase in ("lists", "all"):
        scrape_lists(conn, limit=args.limit)

    if args.phase in ("sites", "all"):
        scrape_sites(conn, limit=args.limit, cache_html=not args.no_cache)

    counts = conn.execute(
        "SELECT (SELECT COUNT(*) FROM sites) AS sites, (SELECT COUNT(*) FROM list_pages) AS lists, "
        "(SELECT COUNT(*) FROM list_entries) AS entries"
    ).fetchone()
    print(
        f"Done. sites={counts['sites']} list_pages={counts['lists']} list_entries={counts['entries']}"
    )


if __name__ == "__main__":
    main()
