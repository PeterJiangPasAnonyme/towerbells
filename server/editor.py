"""Admin helpers for manual database curation."""

from __future__ import annotations

import sqlite3
from typing import Any

from scraper.bellfounders import canonicalize_founder_field, join_founder_parts, split_founder_parts
from scraper.bourdon_pitch import canonical_bourdon_pitch
from scraper.display_titles import display_title_for_site
from server.db import connect, get_site, row_to_dict
from server.display_sync import sync_site_index_display

INDEX_EDITABLE = {
    "bellfounder",
    "installation_year",
    "denomination",
    "institution_type",
    "range_classification",
    "bourdon_pitch",
    "transposition_semitones",
    "instrument_type",
    "latitude",
    "longitude",
}

SITE_EDITABLE = {
    "remarks",
    "prior_history",
    "technical_data",
    "short_name",
    "full_title",
    "display_title_override",
    "location_text",
    "location_display_override",
    "schedule_display_override",
    "contact_display_override",
    "carillonist_display_override",
    "latitude",
    "longitude",
}


def _normalize_site_id(site_id: str) -> str:
    return site_id.strip().upper()


def _milestone_prefix(site_id: str) -> str:
    site_id = _normalize_site_id(site_id)
    return site_id.rstrip("0123456789")


def _matching_site_ids(conn: sqlite3.Connection, site_id: str, *, apply_to_milestones: bool) -> list[str]:
    site_id = _normalize_site_id(site_id)
    if not apply_to_milestones:
        return [site_id]
    prefix = _milestone_prefix(site_id)
    rows = conn.execute(
        "SELECT site_id FROM site_index WHERE site_id = ? OR site_id LIKE ? ORDER BY site_id",
        (site_id, f"{prefix}%"),
    ).fetchall()
    return [row["site_id"] for row in rows]


def admin_search(q: str, *, limit: int = 50) -> list[dict[str, Any]]:
    q = q.strip()
    if not q:
        return []

    conn = connect()
    try:
        pattern = f"%{q}%"
        rows = conn.execute(
            """
            SELECT i.site_id, i.short_name, i.full_title, i.bellfounder, i.country_code,
                   i.installation_year, s.display_title_override, s.full_title AS sites_full_title,
                   s.location_text
            FROM site_index i
            INNER JOIN sites s ON s.site_id = i.site_id
            WHERE i.site_id LIKE ?
               OR i.short_name LIKE ?
               OR i.full_title LIKE ?
               OR s.display_title_override LIKE ?
               OR s.full_title LIKE ?
               OR i.bellfounder LIKE ?
               OR i.search_text LIKE ?
            ORDER BY
                CASE WHEN i.site_id = ? THEN 0
                     WHEN i.site_id LIKE ? THEN 1
                     WHEN i.short_name LIKE ? THEN 2
                     ELSE 3 END,
                i.short_name COLLATE NOCASE
            LIMIT ?
            """,
            (
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                pattern,
                q.upper(),
                f"{q.upper()}%",
                pattern,
                limit,
            ),
        ).fetchall()
        results = []
        for row in rows:
            item = row_to_dict(row)
            if item.get("sites_full_title"):
                item["full_title"] = item["sites_full_title"]
            item["display_title"] = display_title_for_site(item)
            results.append(item)
        return results
    finally:
        conn.close()


def get_editable_site(site_id: str) -> dict[str, Any] | None:
    site_id = _normalize_site_id(site_id)
    data = get_site(site_id)
    if not data:
        return None

    prefix = _milestone_prefix(site_id)
    conn = connect()
    try:
        related = conn.execute(
            """
            SELECT site_id, installation_year, bellfounder
            FROM site_index
            WHERE site_id = ? OR site_id LIKE ?
            ORDER BY site_id
            """,
            (site_id, f"{prefix}%"),
        ).fetchall()
    finally:
        conn.close()

    return {
        **data,
        "milestone_prefix": prefix,
        "related_rows": [row_to_dict(row) for row in related],
    }


def _coerce_index_value(field: str, value: Any) -> Any:
    if field in {"installation_year", "transposition_semitones", "bell_count"}:
        if value in (None, ""):
            return None
        return int(value)
    if field in {"latitude", "longitude"}:
        if value in (None, ""):
            return None
        return float(value)
    if field == "bellfounder":
        text = str(value or "").strip()
        if not text:
            return None
        return canonicalize_founder_field(text) or None
    if field == "bourdon_pitch":
        text = str(value or "").strip()
        if not text:
            return None
        return canonical_bourdon_pitch(text) or None
    text = str(value).strip() if value is not None else ""
    return text or None


def update_site_records(
    site_id: str,
    *,
    index_fields: dict[str, Any] | None = None,
    site_fields: dict[str, Any] | None = None,
    apply_to_milestones: bool = False,
) -> dict[str, Any]:
    site_id = _normalize_site_id(site_id)
    index_fields = index_fields or {}
    site_fields = site_fields or {}

    unknown_index = set(index_fields) - INDEX_EDITABLE
    unknown_site = set(site_fields) - SITE_EDITABLE
    if unknown_index or unknown_site:
        raise ValueError(f"Unknown fields: {sorted(unknown_index | unknown_site)}")

    conn = connect()
    try:
        target_ids = _matching_site_ids(conn, site_id, apply_to_milestones=apply_to_milestones)
        if not target_ids:
            raise ValueError("Site not found")

        index_updates = {
            field: _coerce_index_value(field, value)
            for field, value in index_fields.items()
        }
        site_updates = {
            field: (str(value).strip() or None if value is not None else None)
            for field, value in site_fields.items()
        }

        if index_updates:
            set_clause = ", ".join(f"{field} = ?" for field in index_updates)
            values = list(index_updates.values())
            for target_id in target_ids:
                conn.execute(
                    f"UPDATE site_index SET {set_clause} WHERE site_id = ?",
                    (*values, target_id),
                )

        if site_updates:
            set_clause = ", ".join(f"{field} = ?" for field in site_updates)
            values = list(site_updates.values())
            for target_id in target_ids:
                conn.execute(
                    f"UPDATE sites SET {set_clause} WHERE site_id = ?",
                    (*values, target_id),
                )

        title_related = {"display_title_override", "full_title", "short_name", "location_text"}
        if site_updates and title_related.intersection(site_updates):
            for target_id in target_ids:
                sync_site_index_display(conn, target_id)

        conn.commit()
        return {
            "updated_site_ids": target_ids,
            "index_fields": index_updates,
            "site_fields": site_updates,
        }
    finally:
        conn.close()
