#!/usr/bin/env python3
"""Clean embedded addresses and coordinates out of stored full_title fields."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.config import DB_PATH
from scraper.display_titles import display_title_for_site


def rebuild_search_text(conn: sqlite3.Connection, site_id: str) -> str:
    site = conn.execute("SELECT * FROM sites WHERE site_id = ?", (site_id,)).fetchone()
    index = conn.execute(
        "SELECT denomination, institution_type, bellfounder FROM site_index WHERE site_id = ?",
        (site_id,),
    ).fetchone()
    if site is None or index is None:
        return ""

    parts = [
        site["site_id"],
        site["short_name"],
        site["full_title"],
        site["location_text"],
        site["carillonist"],
        site["remarks"],
        index["denomination"] or "",
        index["institution_type"] or "",
        index["bellfounder"] or "",
    ]
    return " ".join(part for part in parts if part)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM sites ORDER BY site_id").fetchall()
    updated = 0

    for row in rows:
        site = dict(row)
        cleaned = display_title_for_site(site)
        if cleaned == (site.get("full_title") or ""):
            continue

        site_id = site["site_id"]
        conn.execute(
            "UPDATE sites SET full_title = ? WHERE site_id = ?",
            (cleaned, site_id),
        )
        conn.execute(
            "UPDATE site_index SET full_title = ? WHERE site_id = ?",
            (cleaned, site_id),
        )
        conn.execute(
            "UPDATE site_index SET search_text = ? WHERE site_id = ?",
            (rebuild_search_text(conn, site_id), site_id),
        )
        updated += 1
        print(f"{site_id}: {site.get('full_title', '')[:80]}")
        print(f"  -> {cleaned}")

    conn.commit()
    conn.close()
    print(f"\nUpdated {updated} / {len(rows)} site titles.")


if __name__ == "__main__":
    main()
