"""Keep site_index display fields in sync with sites table title overrides."""

from __future__ import annotations

import sqlite3

from scraper.display_titles import display_title_for_site
from server.db import row_to_dict


def rebuild_search_text(site: dict, index: dict, *, title: str) -> str:
    parts = [
        site.get("site_id"),
        site.get("short_name"),
        title,
        site.get("location_text"),
        site.get("carillonist"),
        site.get("remarks"),
        index.get("denomination"),
        index.get("institution_type"),
        index.get("bellfounder"),
    ]
    return " ".join(str(part) for part in parts if part)


def sync_site_index_display(conn: sqlite3.Connection, site_id: str) -> None:
    site_row = conn.execute("SELECT * FROM sites WHERE site_id = ?", (site_id,)).fetchone()
    index_row = conn.execute("SELECT * FROM site_index WHERE site_id = ?", (site_id,)).fetchone()
    if not site_row or not index_row:
        return

    site = row_to_dict(site_row)
    index = row_to_dict(index_row)
    title = display_title_for_site(site)
    search_text = rebuild_search_text(site, index, title=title)
    conn.execute(
        "UPDATE site_index SET full_title = ?, search_text = ? WHERE site_id = ?",
        (title, search_text, site_id),
    )


def sync_all_site_index_display(conn: sqlite3.Connection) -> int:
    rows = conn.execute("SELECT site_id FROM sites ORDER BY site_id").fetchall()
    for row in rows:
        sync_site_index_display(conn, row["site_id"])
    return len(rows)
