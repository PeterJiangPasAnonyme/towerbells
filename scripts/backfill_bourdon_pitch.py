#!/usr/bin/env python3
"""Re-extract bourdon_pitch in site_index from sites.heaviest_pitch."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.bourdon_pitch import parse_bourdon_pitch
from scraper.config import DB_PATH


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    updated = 0
    changed = 0
    with_accidentals = 0

    for row in conn.execute(
        """
        SELECT s.site_id, s.heaviest_pitch, i.bourdon_pitch
        FROM sites s
        JOIN site_index i ON i.site_id = s.site_id
        """
    ):
        parsed = parse_bourdon_pitch(row["heaviest_pitch"]) or None
        if parsed and "#" in parsed:
            with_accidentals += 1
        if parsed != row["bourdon_pitch"]:
            conn.execute(
                "UPDATE site_index SET bourdon_pitch = ? WHERE site_id = ?",
                (parsed, row["site_id"]),
            )
            changed += 1
        updated += 1

    conn.commit()
    conn.close()

    print(f"Sites processed: {updated}")
    print(f"bourdon_pitch values changed: {changed}")
    print(f"Entries with sharp bourdon: {with_accidentals}")


if __name__ == "__main__":
    main()
