#!/usr/bin/env python3
"""Merge milestone site aliases, build carillon_events, and remove duplicate rows."""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.carillon_events import (
    canonical_site_id,
    events_from_line_suffix,
    events_to_json,
    merge_events,
    primary_installation_year,
)
from scraper.config import DB_PATH

EVENT_LIST_TYPES = {"fdy", "yr", "yrhistory"}


def _rebuild_search_text(conn: sqlite3.Connection, site_id: str, bellfounder: str | None) -> str:
    site = conn.execute("SELECT * FROM sites WHERE site_id = ?", (site_id,)).fetchone()
    index = conn.execute(
        "SELECT denomination, institution_type FROM site_index WHERE site_id = ?",
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
        bellfounder or "",
    ]
    return " ".join(part for part in parts if part)


def _collect_group_events(conn: sqlite3.Connection, site_ids: list[str]) -> list[dict]:
    events = []
    for site_id in site_ids:
        rows = conn.execute(
            """
            SELECT le.line_suffix, lp.list_type
            FROM list_entries le
            JOIN list_pages lp ON lp.id = le.list_page_id
            WHERE le.site_id = ?
            """,
            (site_id,),
        ).fetchall()
        for row in rows:
            if row["list_type"] not in EVENT_LIST_TYPES:
                continue
            events.extend(events_from_line_suffix(row["line_suffix"]))
    return merge_events(events)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("ALTER TABLE site_index ADD COLUMN carillon_events TEXT")
    except sqlite3.OperationalError:
        pass

    groups: dict[str, list[str]] = defaultdict(list)
    for row in conn.execute("SELECT site_id, page_filename FROM sites ORDER BY site_id"):
        groups[row["page_filename"]].append(row["site_id"])

    duplicate_groups = {page: ids for page, ids in groups.items() if len(ids) > 1}
    canonical_by_site = {}
    for page, ids in groups.items():
        canonical = canonical_site_id(ids)
        for site_id in ids:
            canonical_by_site[site_id] = canonical

    updated_events = 0
    reassigned_lists = 0
    deleted_sites = 0
    deleted_index = 0
    deleted_lists = 0

    for page_filename, site_ids in sorted(groups.items()):
        canonical = canonical_site_id(site_ids)
        events = _collect_group_events(conn, site_ids)

        if canonical not in site_ids:
            site_ids = [canonical, *site_ids]

        canonical_site = conn.execute("SELECT site_id FROM sites WHERE site_id = ?", (canonical,)).fetchone()
        if canonical_site is None:
            fallback = site_ids[0]
            conn.execute(
                "UPDATE sites SET site_id = ? WHERE site_id = ?",
                (canonical, fallback),
            )
            conn.execute(
                "UPDATE site_index SET site_id = ? WHERE site_id = ?",
                (canonical, fallback),
            )
            conn.execute(
                "UPDATE list_entries SET site_id = ? WHERE site_id = ?",
                (canonical, fallback),
            )

        index = conn.execute("SELECT installation_year FROM site_index WHERE site_id = ?", (canonical,)).fetchone()
        installation_year = primary_installation_year(events) or (
            index["installation_year"] if index is not None else None
        )
        events_json = events_to_json(events)
        conn.execute(
            """
            UPDATE site_index
            SET carillon_events = ?, installation_year = ?
            WHERE site_id = ?
            """,
            (events_json, installation_year, canonical),
        )
        if events:
            updated_events += 1

        for site_id in site_ids:
            if site_id == canonical:
                continue

            rows = conn.execute(
                """
                SELECT le.id, le.list_page_id, le.line_suffix
                FROM list_entries le
                WHERE le.site_id = ?
                """,
                (site_id,),
            ).fetchall()
            for row in rows:
                existing = conn.execute(
                    """
                    SELECT id FROM list_entries
                    WHERE list_page_id = ? AND site_id = ?
                    """,
                    (row["list_page_id"], canonical),
                ).fetchone()
                if existing:
                    conn.execute("DELETE FROM list_entries WHERE id = ?", (row["id"],))
                    deleted_lists += 1
                else:
                    conn.execute(
                        "UPDATE list_entries SET site_id = ? WHERE id = ?",
                        (canonical, row["id"]),
                    )
                    reassigned_lists += 1

            conn.execute("DELETE FROM site_index WHERE site_id = ?", (site_id,))
            conn.execute("DELETE FROM sites WHERE site_id = ?", (site_id,))
            deleted_index += 1
            deleted_sites += 1

    for row in conn.execute("SELECT site_id, bellfounder FROM site_index"):
        conn.execute(
            "UPDATE site_index SET search_text = ? WHERE site_id = ?",
            (_rebuild_search_text(conn, row["site_id"], row["bellfounder"]), row["site_id"]),
        )

    conn.commit()

    remaining_sites = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
    remaining_suffix = conn.execute(
        "SELECT COUNT(*) FROM sites WHERE site_id GLOB '*[0-9]'"
    ).fetchone()[0]
    with_events = conn.execute(
        "SELECT COUNT(*) FROM site_index WHERE carillon_events IS NOT NULL AND carillon_events != '[]'"
    ).fetchone()[0]

    print(f"Duplicate page groups: {len(duplicate_groups)}")
    print(f"Canonical rows updated with events: {updated_events}")
    print(f"List entries reassigned: {reassigned_lists}")
    print(f"Duplicate list entries removed: {deleted_lists}")
    print(f"Duplicate sites removed: {deleted_sites}")
    print(f"Remaining sites: {remaining_sites}")
    print(f"Remaining suffix site ids: {remaining_suffix}")
    print(f"Sites with carillon_events: {with_events}")

    sample = conn.execute(
        """
        SELECT site_id, installation_year, carillon_events
        FROM site_index
        WHERE site_id IN ('BEBRGGHT', 'VAARLING', 'BEANTWSM')
        ORDER BY site_id
        """
    ).fetchall()
    print("\nSamples:")
    for row in sample:
        events = json.loads(row["carillon_events"] or "[]")
        print(f"  {row['site_id']} ({row['installation_year']}): {len(events)} events")
        for event in events[:4]:
            print(f"    {event['year']} {event['code']} -> {event['type']}")
        if len(events) > 4:
            print("    ...")
    conn.close()


if __name__ == "__main__":
    main()
