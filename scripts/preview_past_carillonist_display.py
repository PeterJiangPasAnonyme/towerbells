#!/usr/bin/env python3
"""Preview past carillonist timeline display and list flagged entries."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.display_titles import build_site_display
from scraper.past_carillonist_display import build_past_carillonist_display, collect_past_carillonist_flags
from server.db import DB_PATH, row_to_dict

INTERESTING_FLAGS = {
    "placeholder_unknown",
    "placeholder_none",
    "placeholder_other",
    "cross_reference",
    "partial_dates",
    "no_year",
    "carillon_silent",
    "dedication",
    "ampersand_names",
    "colon_separator",
    "circa_date",
}


def load_sites(site_ids: list[str] | None = None) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if site_ids:
        placeholders = ",".join("?" for _ in site_ids)
        rows = conn.execute(
            f"SELECT * FROM sites WHERE site_id IN ({placeholders}) ORDER BY site_id",
            site_ids,
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM sites WHERE past_carillonists IS NOT NULL AND trim(past_carillonists) != '' ORDER BY site_id"
        ).fetchall()
    return [row_to_dict(row) for row in rows]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_ids", nargs="*", help="Optional site IDs to preview")
    parser.add_argument("--json", action="store_true", help="Print full display JSON")
    parser.add_argument("--flags-only", action="store_true", help="Print flagged entries only")
    args = parser.parse_args()

    sites = load_sites(args.site_ids or None)
    if not sites:
        print("No matching sites with past carillonists text.")
        return

    if args.flags_only:
        flags = collect_past_carillonist_flags(sites)
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in flags:
            if row["flag"] in INTERESTING_FLAGS:
                grouped[row["flag"]].append(row)

        print("Flagged past carillonist entries\n")
        for flag in sorted(grouped):
            print(f"## {flag} ({len(grouped[flag])})")
            for item in grouped[flag]:
                raw = (item.get("raw") or "").replace("\n", " / ")
                print(f"  - {item['site_id']} [{item.get('entry_id')}]: {raw[:120]}")
            print()
        return

    for site in sites:
        display = build_site_display(site)
        past = display["past_carillonists"]
        print(f"=== {site['site_id']} ===")
        if not past.get("has_content"):
            print("(empty)")
            continue
        for timeline in past.get("timelines") or []:
            label = timeline.get("label") or "appointments"
            print(f"  timeline: {label} ({timeline['year_min']}–{timeline['year_max']})")
            for entry in timeline.get("entries") or []:
                flags = ",".join(entry.get("flags") or []) or "-"
                print(
                    f"    {entry.get('date_label')} | {entry.get('person_name')} "
                    f"{entry.get('lifespan') or ''} {entry.get('cert_label') or ''} [{flags}]"
                )
        if past.get("unknown_time"):
            print("  time unknown:")
            for entry in past["unknown_time"]:
                flags = ",".join(entry.get("flags") or []) or "-"
                print(f"    {entry.get('person_name')} [{flags}]")
        if args.json:
            print(json.dumps(past, indent=2, ensure_ascii=False))
        print()


if __name__ == "__main__":
    main()
