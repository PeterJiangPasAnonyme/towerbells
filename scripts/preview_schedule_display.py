#!/usr/bin/env python3
"""Preview structured schedule display and list example site IDs."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.display_titles import build_site_display
from scraper.schedule_display import build_schedule_display
from server.db import connect

EXAMPLE_GROUPS = {
    "Schedule unknown (badge)": ["NJPLAINF", "NLDRDRCC"],
    "No regular schedule (badge)": ["BEBRXLPM", "PAPHI39B"],
    "Simple weekly": ["AUCNBRNC", "ALBIRMFP"],
    "Seasonal calendars": ["VAARLING", "BEBRGGHT"],
    "School-term + summer": ["ILCHICUC"],
    "Prose fallback": ["FLLKWALE", "MDFREDBP"],
    "Complex mixed": ["FRDOUAIH"],
}


def summarize(display: dict) -> str:
    schedule = display.get("schedule") or {}
    parts = [schedule.get("mode", "?")]
    if schedule.get("badge"):
        parts.append(f"badge={schedule['badge']}")
    if schedule.get("calendars"):
        parts.append(f"{len(schedule['calendars'])} calendar(s)")
    if schedule.get("prose"):
        parts.append("prose")
    return ", ".join(parts)


def active_days(calendar: dict) -> list[str]:
    days = calendar.get("days") or {}
    return [day for day, times in days.items() if times]


def main() -> None:
    conn = connect()
    rows = conn.execute("SELECT * FROM sites ORDER BY site_id").fetchall()
    conn.close()

    counts = Counter()
    edge_cases: dict[str, list[str]] = {}

    for row in rows:
        site = dict(row)
        schedule = build_schedule_display(site)
        counts[schedule["mode"]] += 1
        if schedule.get("badge") == "Schedule unknown":
            edge_cases.setdefault("unknown", []).append(site["site_id"])
        elif schedule.get("badge") == "No regular schedule":
            edge_cases.setdefault("irregular", []).append(site["site_id"])
        elif schedule["mode"] == "structured" and len(schedule.get("calendars") or []) > 1:
            edge_cases.setdefault("multi_calendar", []).append(site["site_id"])
        elif schedule["mode"] == "prose":
            edge_cases.setdefault("prose", []).append(site["site_id"])

    print("=== COUNTS ===")
    for mode, count in counts.most_common():
        print(f"  {mode}: {count}")

    print("\n=== EXAMPLES (open /carillon/SITE_ID) ===\n")
    for label, site_ids in EXAMPLE_GROUPS.items():
        print(label)
        for site_id in site_ids:
            site = next(dict(r) for r in rows if r["site_id"] == site_id)
            display = build_site_display(site)
            schedule = display["schedule"]
            print(f"  {site_id} — {summarize(display)}")
            for index, calendar in enumerate(schedule.get("calendars") or [], start=1):
                cond = calendar.get("condition") or "(no condition)"
                print(f"    [{index}] {cond}: {', '.join(active_days(calendar))}")
            if schedule.get("prose"):
                prose = schedule["prose"].replace("\n", " ")[:90]
                print(f"    prose: {prose}{'…' if len(schedule['prose']) > 90 else ''}")
        print()

    print("=== EDGE CASE LISTS ===\n")
    for label, ids in edge_cases.items():
        print(f"{label} ({len(ids)})")
        print("  " + ", ".join(ids[:35]))
        if len(ids) > 35:
            print(f"  … and {len(ids) - 35} more")
        print()


if __name__ == "__main__":
    main()
