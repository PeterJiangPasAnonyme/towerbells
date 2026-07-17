#!/usr/bin/env python3
"""Replace site_index.bellfounder values from towerbells.org fdy index pages."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.bellfounders import join_founder_parts, split_founder_parts
from scraper.config import DB_PATH
from scraper.fetch import fetch
from scraper.fdy_parse import load_founders_by_page_from_html_pages


def _load_fdy_pages(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT filename FROM list_pages
        WHERE list_type = 'fdy'
        ORDER BY filename
        """
    ).fetchall()
    pages: dict[str, str] = {}
    for (filename,) in rows:
        try:
            pages[filename] = fetch(filename)
        except RuntimeError as exc:
            print(f"SKIP {filename}: {exc}")
    return pages


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        pages = _load_fdy_pages(conn)
        print(f"Loaded {len(pages)} fdy index pages")
        founders_by_page = load_founders_by_page_from_html_pages(pages)
        print(f"Found founders for {len(founders_by_page)} site pages")

        site_rows = conn.execute(
            "SELECT site_id, page_filename FROM sites"
        ).fetchall()
        page_by_site = {
            row["site_id"]: row["page_filename"].rsplit(".", 1)[0].upper()
            for row in site_rows
            if row["page_filename"]
        }

        updated = 0
        cleared = 0
        for site_id in conn.execute("SELECT site_id FROM site_index"):
            site_id = site_id[0]
            page_stem = page_by_site.get(site_id)
            founders = founders_by_page.get(page_stem or "", [])
            founder_value = join_founder_parts(founders) if founders else None
            conn.execute(
                "UPDATE site_index SET bellfounder = ? WHERE site_id = ?",
                (founder_value, site_id),
            )
            if founder_value:
                updated += 1
            else:
                cleared += 1

        conn.commit()

        print(f"Updated with founders: {updated}")
        print(f"Cleared (not on fdy indexes): {cleared}")

        samples = conn.execute(
            """
            SELECT site_id, short_name, bellfounder
            FROM site_index
            WHERE site_id IN ('VAARLING', 'FRBRGSTW', 'BECHMYPP', 'TXLUBBOC1', 'ILCHICUC')
               OR site_id LIKE 'VAARLING%'
            ORDER BY site_id
            """
        ).fetchall()
        print("\nSamples:")
        for row in samples:
            print(f"  {row['site_id']}: {row['bellfounder']}")

        facet_count = conn.execute(
            "SELECT COUNT(DISTINCT bellfounder) FROM site_index WHERE bellfounder IS NOT NULL AND bellfounder != ''"
        ).fetchone()[0]
        print(f"\nDistinct bellfounder strings: {facet_count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
