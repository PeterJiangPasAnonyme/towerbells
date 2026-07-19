#!/usr/bin/env python3
"""Report location display fixes and edge cases needing review."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.display_titles import build_site_display, display_title_for_site
from scraper.location_display import build_location_display, _looks_like_church_name
from server.db import connect

BASE_URL = "http://127.0.0.1:8000/carillon"


def format_location_panel(loc: dict) -> str:
    lines: list[str] = []
    building = loc.get("building") or {}
    if building.get("line"):
        lines.append(f"**{building['line']}**")
    if building.get("translation"):
        lines.append(f"*{building['translation']}*")
    for addr in loc.get("address_lines") or []:
        lines.append(addr)
    if loc.get("city_region"):
        lines.append(loc["city_region"])
    if loc.get("country"):
        lines.append(loc["country"])
    for note in loc.get("notes") or []:
        lines.append(f"_{note}_")
    edge = loc.get("edge_case") or {}
    if edge.get("summary"):
        lines.append(f"[edge: {edge['summary']}]")
    if loc.get("maps_url"):
        lines.append("Open in Maps ↗")
    return " → ".join(lines) if lines else "(empty)"


def raw_has_split_address(text: str) -> bool:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("LL:")]
    for index in range(len(raw_lines) - 1):
        nxt = raw_lines[index + 1]
        if nxt.startswith(",") or (
            nxt
            and nxt[0].islower()
            and nxt.split()[0].lower() in {"and", "near", "at", "between", "or", "opposite"}
        ):
            return True
    return False


def main() -> None:
    conn = connect()
    rows = conn.execute(
        "SELECT site_id, location_text, page_url, location_display_override FROM sites ORDER BY site_id"
    ).fetchall()

    former_rows: list[dict] = []
    address_rows: list[dict] = []
    church_rows: list[dict] = []

    for row in rows:
        site_row = dict(
            conn.execute("SELECT * FROM sites WHERE site_id = ?", (row["site_id"],)).fetchone()
        )
        loc = build_site_display(site_row)["location"]
        building = loc.get("building") or {}

        rename_notes = [
            note
            for note in loc.get("notes") or []
            if " was known as " in note or re.search(r"\bwas formerly\b", note, re.I)
        ]
        if rename_notes or (
            building.get("translation")
            and re.search(r"\b(?:was|formerly|previously)\b", building["translation"], re.I)
        ):
            former_rows.append(
                {
                    "site_id": row["site_id"],
                    "url": f"{BASE_URL}/{row['site_id']}",
                    "notes": rename_notes,
                    "translation": building.get("translation"),
                    "display": format_location_panel(loc),
                }
            )

        if raw_has_split_address(row["location_text"] or ""):
            addrs = loc.get("address_lines") or []
            if any(
                " near " in addr.lower()
                or re.search(r"between .+ and ", addr, re.I)
                for addr in addrs
            ):
                address_rows.append(
                    {
                        "site_id": row["site_id"],
                        "url": f"{BASE_URL}/{row['site_id']}",
                        "address_lines": addrs,
                        "display": format_location_panel(loc),
                    }
                )

        if not row["location_display_override"] and building.get("line"):
            auto_loc = build_location_display(
                site_row,
                page_title=display_title_for_site(site_row),
                override=None,
            )
            auto_building = auto_loc.get("building") or {}
            if auto_building.get("line") and _looks_like_church_name(auto_building["line"]):
                raw_first = next(
                    (
                        line.strip()
                        for line in (row["location_text"] or "").splitlines()
                        if line.strip() and not line.startswith("LL:")
                    ),
                    "",
                )
                if re.search(
                    r"\b(?:Church|Cathedral|Chapel|Kerk|Église|Eglise|Presbyterian|Lutheran|Baptist)\b",
                    raw_first,
                    re.I,
                ):
                    church_rows.append(
                        {
                            "site_id": row["site_id"],
                            "url": f"{BASE_URL}/{row['site_id']}",
                            "source_url": row["page_url"],
                            "building": auto_building.get("line"),
                            "display": format_location_panel(auto_loc),
                        }
                    )

    conn.close()

    out = ROOT / "data" / "location_display_fixes.md"
    parts = [
        "# Location display fixes",
        "",
        f"**Former-name notes:** {len(former_rows)} sites",
        f"**Merged address lines:** {len(address_rows)} sites",
        f"**Church names moved to building:** {len(church_rows)} sites",
        "",
        "## Church names moved from address to building",
        "",
        "Denomination labels in parentheses or after `·` are stripped from the building line.",
        "",
    ]
    for item in church_rows:
        parts.append(f"### [{item['site_id']}]({item['url']})")
        parts.append(f"- Building: {item['building']}")
        if item.get("source_url"):
            parts.append(f"- Source: {item['source_url']}")
        parts.append(f"- **Location tab:** {item['display']}")
        parts.append("")

    parts.extend(["## Former names moved from translation to notes", ""])
    for item in former_rows:
        parts.append(f"### [{item['site_id']}]({item['url']})")
        for note in item["notes"]:
            parts.append(f"- Note: {note}")
        if item["translation"]:
            parts.append(f"- Still in translation (check): {item['translation']}")
        parts.append(f"- **Location tab:** {item['display']}")
        parts.append("")

    parts.extend(["## Merged split address lines", ""])
    for item in address_rows:
        parts.append(f"### [{item['site_id']}]({item['url']})")
        for addr in item["address_lines"]:
            parts.append(f"- {addr}")
        parts.append(f"- **Location tab:** {item['display']}")
        parts.append("")

    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"Church building sites: {len(church_rows)}")


if __name__ == "__main__":
    main()
