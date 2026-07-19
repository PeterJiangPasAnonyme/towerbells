#!/usr/bin/env python3
"""Preview structured location display and list edge-case site IDs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.display_titles import build_site_display
from scraper.location_display import (
    LL_LINE_RE,
    MOBILE_RE,
    STORAGE_RE,
    FORMERLY_RE,
    GENERIC_TOWER_RE,
)
from server.db import connect

EXAMPLE_IDS = [
    "BCVICTNC",
    "ILCHICUC",
    "BEARSTPC",
    "BEGENTBF",
    "BEBRXLPM",
    "ATINNSJ1A",
    "BETLTSHH",
    "BEANTWSM",
]


def classify_site(site: dict, display: dict) -> list[str]:
    tags: list[str] = []
    text = site.get("location_text") or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    loc = display.get("location") or {}
    building = loc.get("building") or {}

    if not text.strip():
        tags.append("empty")
    if any(LL_LINE_RE.match(line) for line in lines):
        tags.append("has_ll_raw")
    if site.get("latitude") is None or site.get("longitude") is None:
        tags.append("no_coordinates")
    if MOBILE_RE.search(text):
        tags.append("mobile")
    if STORAGE_RE.search(text):
        tags.append("storage")
    if FORMERLY_RE.search(text):
        tags.append("formerly")
    if any(GENERIC_TOWER_RE.match(line) for line in lines):
        tags.append("generic_tower")
    if re.search(r"\([^)]+\)", text):
        tags.append("parenthetical")
    if not loc.get("has_content"):
        tags.append("empty_display")
    if building.get("line") and display.get("title"):
        if building["line"].lower() in display["title"].lower():
            tags.append("building_matched_title")
    if site.get("location_display_override"):
        tags.append("override")
    if loc.get("edge_case"):
        tags.append("edge_case")
    if len(lines) <= 2 and not STORAGE_RE.search(text):
        tags.append("minimal")
    if re.search(r"Czechoslovakia|Yugoslavia|formerly part of", text, re.I):
        tags.append("historic_country")
    if re.search(r",\s*[^,\n]+\s*\([^)]+\),\s*[^,\n]+\s*,", text):
        tags.append("bilingual_locality")
    return tags


def format_display(display: dict) -> str:
    loc = display.get("location") or {}
    parts: list[str] = []
    if loc.get("badge"):
        parts.append(f"badge: {loc['badge']}")
    building = loc.get("building") or {}
    if building.get("line"):
        parts.append(f"building: {building['line']}")
    if building.get("translation"):
        parts.append(f"translation: {building['translation']}")
    for line in loc.get("address_lines") or []:
        parts.append(f"addr: {line}")
    if loc.get("city_region"):
        parts.append(f"city_region: {loc['city_region']}")
    if loc.get("country"):
        parts.append(f"country: {loc['country']}")
    edge = loc.get("edge_case") or {}
    if edge.get("summary"):
        parts.append(f"edge: {edge['summary']}")
    for note in loc.get("notes") or []:
        parts.append(f"note: {note[:100]}{'…' if len(note) > 100 else ''}")
    if loc.get("maps_url"):
        parts.append("maps: yes")
    return "\n    ".join(parts) if parts else "(empty)"


def main() -> None:
    conn = connect()
    rows = conn.execute(
        "SELECT site_id, location_text, latitude, longitude, country_code, state_province, "
        "full_title, short_name, location_display_override FROM sites ORDER BY site_id"
    ).fetchall()
    conn.close()

    edge_cases: dict[str, list[str]] = {}

    print("=== EXAMPLES ===\n")
    for site_id in EXAMPLE_IDS:
        row = next((r for r in rows if r["site_id"] == site_id), None)
        if not row:
            print(f"{site_id}: not found\n")
            continue
        site = dict(row)
        display = build_site_display(site)
        print(f"{site_id} — {display['title']}")
        print(f"  subtitle: {display['subtitle']}")
        print(f"    {format_display(display)}\n")

    for row in rows:
        site = dict(row)
        display = build_site_display(site)
        tags = classify_site(site, display)
        interesting = [
            tag
            for tag in tags
            if tag
            not in {"has_ll_raw", "parenthetical", "building_matched_title"}
            or tag in {"empty", "empty_display", "override", "no_coordinates", "storage", "mobile", "edge_case"}
        ]
        if len(interesting) > 1 or (interesting and interesting != ["has_ll_raw"]):
            for tag in interesting:
                edge_cases.setdefault(tag, []).append(site["site_id"])

    print("=== EDGE CASES (search by site_id) ===\n")
    for tag in sorted(edge_cases):
        ids = edge_cases[tag]
        print(f"{tag} ({len(ids)})")
        print("  " + ", ".join(ids[:40]))
        if len(ids) > 40:
            print(f"  … and {len(ids) - 40} more")
        print()


if __name__ == "__main__":
    main()
