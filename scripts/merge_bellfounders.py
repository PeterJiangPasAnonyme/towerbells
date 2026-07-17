#!/usr/bin/env python3
"""Merge bellfounder family variants and drop founders with fewer than 5 sites."""

from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.bellfounders import (
    MIN_FOUNDER_FACET_COUNT,
    canonicalize_founder_field,
    join_founder_parts,
    split_founder_parts,
)
from scraper.config import DB_PATH

MIN_FOUNDER_SITES = MIN_FOUNDER_FACET_COUNT


def _count_founder_parts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in conn.execute(
        "SELECT bellfounder FROM site_index WHERE bellfounder IS NOT NULL AND bellfounder != ''"
    ):
        for part in split_founder_parts(row[0]):
            counts[part] += 1
    return dict(counts)


def _strip_rare_founders(value: str | None, rare: set[str]) -> str | None:
    parts = [part for part in split_founder_parts(value) if part not in rare]
    if not parts:
        return None
    return join_founder_parts(parts)


def _rebuild_search_text(
    conn: sqlite3.Connection,
    site_id: str,
    bellfounder: str | None,
) -> str:
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


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        merged_updates = 0
        for row in conn.execute(
            "SELECT site_id, bellfounder FROM site_index WHERE bellfounder IS NOT NULL AND bellfounder != ''"
        ):
            canonical = canonicalize_founder_field(row["bellfounder"])
            if canonical != row["bellfounder"]:
                conn.execute(
                    "UPDATE site_index SET bellfounder = ?, search_text = ? WHERE site_id = ?",
                    (
                        canonical or None,
                        _rebuild_search_text(conn, row["site_id"], canonical or None),
                        row["site_id"],
                    ),
                )
                merged_updates += 1

        counts = _count_founder_parts(conn)
        rare = {name for name, count in counts.items() if count < MIN_FOUNDER_SITES}
        print(f"Merged rows updated: {merged_updates}")
        print(f"Founders before rare cleanup: {len(counts)}")
        print(f"Founders with <{MIN_FOUNDER_SITES} sites (will be stripped): {len(rare)}")

        stripped_sites = 0
        cleared_sites = 0
        for row in conn.execute("SELECT site_id, bellfounder FROM site_index"):
            original = row["bellfounder"]
            if not original:
                continue
            updated = _strip_rare_founders(original, rare)
            if updated == original:
                continue
            conn.execute(
                "UPDATE site_index SET bellfounder = ?, search_text = ? WHERE site_id = ?",
                (
                    updated,
                    _rebuild_search_text(conn, row["site_id"], updated),
                    row["site_id"],
                ),
            )
            stripped_sites += 1
            if updated is None:
                cleared_sites += 1

        final_counts = _count_founder_parts(conn)
        conn.commit()

        print(f"Sites updated during rare-founder cleanup: {stripped_sites}")
        print(f"Sites with bellfounder fully cleared: {cleared_sites}")
        print(f"Founders remaining: {len(final_counts)}")
        print(f"All remaining founders have >={MIN_FOUNDER_SITES} sites: {all(c >= MIN_FOUNDER_SITES for c in final_counts.values())}")

        print("\nMerged family totals:")
        for name in ("Waghevens", "Witlockx", "Noorden & DeGrave", "Vanden Gheyn", "Van Aerschodt"):
            print(f"  {name}: {final_counts.get(name, 0)}")

        print("\nRemaining founders:")
        for name, count in sorted(final_counts.items(), key=lambda item: (-item[1], item[0].lower())):
            print(f"  {name} ({count})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
