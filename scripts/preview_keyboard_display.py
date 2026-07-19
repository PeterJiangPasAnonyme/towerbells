#!/usr/bin/env python3
"""Preview parsed keyboard display for selected sites."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.display_titles import build_site_display
from scraper.keyboard_display import build_keyboard_display

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "towerbells.db"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_ids", nargs="*", help="Site IDs to preview")
    parser.add_argument("--flags-only", action="store_true", help="Print compact summary only")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    site_ids = args.site_ids
    if not site_ids:
        site_ids = ["ILCHICUC", "ONTOROMC", "INBLOOM1A", "BCVICTNC"]

    for site_id in site_ids:
        row = conn.execute("SELECT * FROM sites WHERE site_id = ?", (site_id.upper(),)).fetchone()
        if not row:
            print(f"{site_id}: not found")
            continue
        site = dict(row)
        keyboard = build_keyboard_display(site)
        if args.flags_only:
            hands = keyboard.get("hands") or {}
            pedals = keyboard.get("pedals") or {}
            hcount = len([key for key in (hands.get("keys") or []) if not key.get("gap")])
            pcount = len([key for key in (pedals.get("keys") or []) if not key.get("gap")])
            print(
                f"{site_id}: badge={keyboard.get('transposition_badge')} "
                f"hands={hands.get('low')}-{hands.get('high')}:{hcount} "
                f"pedals={pedals.get('low')}-{pedals.get('high')}:{pcount} "
                f"missing={keyboard.get('missing_bass_notes')}"
            )
            continue

        display = build_site_display(site)
        print(f"=== {site_id} ===")
        print(json.dumps(display["keyboard"], indent=2, sort_keys=True))
        print()


if __name__ == "__main__":
    main()
