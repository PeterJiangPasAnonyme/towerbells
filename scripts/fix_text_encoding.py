#!/usr/bin/env python3
"""Decode HTML entities and fix mojibake in existing database text fields."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.bellfounders import canonicalize_founder_field, join_founder_parts, split_founder_parts
from scraper.config import DB_PATH
from scraper.text import decode_html_text, decode_json_text_values

SITE_TEXT_COLUMNS = [
    "short_name",
    "full_title",
    "location_text",
    "carillonist",
    "past_carillonists",
    "contact",
    "schedule",
    "remarks",
    "technical_data",
    "instrument_type",
    "heaviest_pitch",
    "keyboard_range",
    "transposition",
    "missing_bass_semitone",
    "practice_console",
    "retuned_by",
    "prior_history",
    "auxiliary_mechanisms",
    "tower_details",
    "status_text",
    "textual_data_updated",
    "technical_data_updated",
    "page_built_date",
]

INDEX_TEXT_COLUMNS = [
    "short_name",
    "full_title",
    "search_text",
    "bellfounder",
    "denomination",
    "institution_type",
    "range_classification",
    "bourdon_pitch",
    "instrument_type",
    "state_province",
]

LIST_TEXT_COLUMNS = ["display_name", "line_suffix"]


def _decode_value(column: str, value: str | None) -> str | None:
    if value is None:
        return None
    if column == "sections_json":
        return decode_json_text_values(value)
    if column == "bellfounder":
        return canonicalize_founder_field(decode_html_text(value)) or None
    decoded = decode_html_text(value)
    return decoded or None


def _update_table(
    conn: sqlite3.Connection,
    table: str,
    key_column: str,
    columns: list[str],
) -> int:
    rows = conn.execute(f"SELECT {key_column}, {', '.join(columns)} FROM {table}").fetchall()
    updated = 0
    for row in rows:
        key = row[0]
        changes: dict[str, str | None] = {}
        for index, column in enumerate(columns, start=1):
            original = row[index]
            if original is None:
                continue
            decoded = _decode_value(column, original)
            if decoded != original:
                changes[column] = decoded
        if not changes:
            continue
        set_clause = ", ".join(f"{column} = ?" for column in changes)
        conn.execute(
            f"UPDATE {table} SET {set_clause} WHERE {key_column} = ?",
            (*changes.values(), key),
        )
        updated += 1
    return updated


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        site_updates = _update_table(conn, "sites", "site_id", SITE_TEXT_COLUMNS)
        sections_updates = 0
        for site_id, sections_json in conn.execute(
            "SELECT site_id, sections_json FROM sites WHERE sections_json IS NOT NULL AND sections_json != ''"
        ):
            decoded = decode_json_text_values(sections_json)
            if decoded != sections_json:
                conn.execute(
                    "UPDATE sites SET sections_json = ? WHERE site_id = ?",
                    (decoded, site_id),
                )
                sections_updates += 1

        index_updates = _update_table(conn, "site_index", "site_id", INDEX_TEXT_COLUMNS)
        list_updates = _update_table(conn, "list_entries", "id", LIST_TEXT_COLUMNS)

        conn.commit()
        print(f"sites rows updated: {site_updates}")
        print(f"sites sections_json updated: {sections_updates}")
        print(f"site_index rows updated: {index_updates}")
        print(f"list_entries rows updated: {list_updates}")

        remaining = conn.execute(
            """
            SELECT COUNT(*) FROM sites
            WHERE full_title LIKE '%&%' OR remarks LIKE '%&%' OR full_title LIKE '%Ã%'
            """
        ).fetchone()[0]
        print(f"sites with remaining entity/mojibake markers: {remaining}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
