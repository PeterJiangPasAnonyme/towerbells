#!/usr/bin/env python3
"""Backfill state_province from location text for NL, BE, DK and sync site_index."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.config import DB_PATH
from scraper.province_extract import extract_province


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    updated = 0
    skipped: list[tuple[str, str]] = []

    for row in conn.execute(
        "SELECT site_id, country_code, state_province, location_text FROM sites"
    ):
        province = extract_province(
            row["country_code"],
            row["location_text"] or "",
            row["state_province"] or "",
        )
        if not province:
            continue
        if province == (row["state_province"] or ""):
            continue
        conn.execute(
            "UPDATE sites SET state_province = ? WHERE site_id = ?",
            (province, row["site_id"]),
        )
        updated += 1

    # Report sites we couldn't assign (NL/BE only)
    for row in conn.execute(
        """
        SELECT site_id, country_code, location_text FROM sites
        WHERE country_code IN ('NETHERLANDS', 'BELGIUM') AND (state_province IS NULL OR state_province = '')
        """
    ):
        skipped.append((row["site_id"], (row["location_text"] or "")[:80]))

    conn.execute(
        """
        UPDATE site_index
        SET state_province = (SELECT state_province FROM sites WHERE sites.site_id = site_index.site_id)
        """
    )
    conn.commit()

    for country in ("NETHERLANDS", "BELGIUM", "DENMARK", "SCOTLAND"):
        n = conn.execute(
            """
            SELECT COUNT(DISTINCT state_province) FROM site_index
            WHERE country_code = ? AND state_province != ''
            """,
            (country,),
        ).fetchone()[0]
        total = conn.execute(
            "SELECT COUNT(*) FROM site_index WHERE country_code = ?", (country,)
        ).fetchone()[0]
        print(f"{country}: {n} provinces, {total} sites")

    print(f"Updated {updated} site records")
    if skipped:
        print(f"Could not assign province ({len(skipped)}):")
        for sid, loc in skipped:
            print(f"  {sid}: {loc!r}")

    conn.close()


if __name__ == "__main__":
    main()
