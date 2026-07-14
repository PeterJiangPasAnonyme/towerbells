"""SQLite query helpers for the TowerBells search API."""

from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from scraper.instrument_types import normalize_instrument_type
from server.geo_labels import format_country, format_region

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "towerbells.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def build_search_clauses(
    *,
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
    map_only: bool = False,
    exclude: set[str] | None = None,
) -> tuple[list[str], list[Any]]:
    exclude = exclude or set()
    clauses = ["1=1"]
    params: list[Any] = []

    if q.strip() and "q" not in exclude:
        clauses.append("search_text LIKE ?")
        params.append(f"%{q.strip()}%")
    if continent and "continent" not in exclude:
        clauses.append("continent = ?")
        params.append(continent)
    if country and "country" not in exclude:
        clauses.append("country_code = ?")
        params.append(country)
    if state and "state" not in exclude:
        clauses.append("state_province = ?")
        params.append(state)
    if year_min is not None and "year_min" not in exclude:
        clauses.append("installation_year >= ?")
        params.append(year_min)
    if year_max is not None and "year_max" not in exclude:
        clauses.append("installation_year <= ?")
        params.append(year_max)
    if bourdon_pitch and "bourdon_pitch" not in exclude:
        clauses.append("bourdon_pitch = ?")
        params.append(bourdon_pitch)
    if transposition is not None and "transposition" not in exclude:
        clauses.append("transposition_semitones = ?")
        params.append(transposition)
    if range_class and "range_class" not in exclude:
        clauses.append("range_classification = ?")
        params.append(range_class)
    if denomination and "denomination" not in exclude:
        clauses.append("denomination = ?")
        params.append(denomination)
    if institution_type and "institution_type" not in exclude:
        clauses.append("institution_type = ?")
        params.append(institution_type)
    if instrument_type and "instrument_type" not in exclude:
        clauses.append("LOWER(instrument_type) = LOWER(?)")
        params.append(instrument_type)
    if bellfounder and "bellfounder" not in exclude:
        clauses.append("bellfounder LIKE ?")
        params.append(f"%{bellfounder}%")
    if map_only and "map_only" not in exclude:
        clauses.append("latitude IS NOT NULL AND longitude IS NOT NULL")

    return clauses, params


def _facet_rows(
    conn: sqlite3.Connection,
    column: str,
    clauses: list[str],
    params: list[Any],
    *,
    extra_where: str = "",
    country_for_regions: str | None = None,
    order: str = "count",
) -> list[dict[str, Any]]:
    where = " AND ".join(clauses)
    if extra_where:
        where = f"{where} AND {extra_where}" if where else extra_where

    if order == "value":
        order_clause = f"ORDER BY {column} ASC"
    elif order == "value_int":
        order_clause = f"ORDER BY CAST({column} AS INTEGER) ASC"
    else:
        order_clause = "ORDER BY count DESC, value ASC"

    rows = conn.execute(
        f"""
        SELECT {column} AS value, COUNT(*) AS count
        FROM site_index
        WHERE {where} AND {column} IS NOT NULL AND {column} != ''
        GROUP BY {column}
        {order_clause}
        """,
        params,
    ).fetchall()

    items: list[dict[str, Any]] = []
    for row in rows:
        value = row["value"]
        if column == "continent":
            label = value
        elif column == "country_code":
            label = format_country(value)
        elif column == "state_province":
            label = format_region(country_for_regions or "", value)
        else:
            label = value
        items.append({"value": value, "label": label, "count": row["count"]})
    return items


def get_location_facets(
    *,
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
) -> dict[str, Any]:
    base = dict(
        q=q,
        continent=continent,
        country=country,
        state=state,
        year_min=year_min,
        year_max=year_max,
        bellfounder=bellfounder,
        bourdon_pitch=bourdon_pitch,
        transposition=transposition,
        range_class=range_class,
        denomination=denomination,
        institution_type=institution_type,
        instrument_type=instrument_type,
    )

    conn = connect()
    try:
        c_clauses, c_params = build_search_clauses(**base, exclude={"continent"})
        continents = _facet_rows(conn, "continent", c_clauses, c_params)

        co_clauses, co_params = build_search_clauses(**base, exclude={"country"})
        countries = _facet_rows(conn, "country_code", co_clauses, co_params)

        states: list[dict[str, Any]] = []
        show_states = False
        if country:
            s_clauses, s_params = build_search_clauses(**base, exclude={"state"})
            states = _facet_rows(
                conn,
                "state_province",
                s_clauses,
                s_params,
                country_for_regions=country,
            )
            # Only offer subdivision filter when country has 2+ distinct regions
            show_states = len(states) >= 2

        return {
            "continents": continents,
            "countries": countries,
            "states": states if show_states else [],
            "show_states": show_states,
        }
    finally:
        conn.close()


def _instrument_type_facet_rows(
    conn: sqlite3.Connection,
    clauses: list[str],
    params: list[Any],
) -> list[dict[str, Any]]:
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT instrument_type
        FROM site_index
        WHERE {where} AND instrument_type IS NOT NULL AND instrument_type != ''
        """,
        params,
    ).fetchall()
    counts: Counter[str] = Counter()
    for row in rows:
        normalized = normalize_instrument_type(row["instrument_type"])
        if normalized:
            counts[normalized] += 1
    return [
        {"value": value, "label": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
    ]


def _founder_facet_rows(
    conn: sqlite3.Connection,
    clauses: list[str],
    params: list[Any],
) -> list[dict[str, Any]]:
    where = " AND ".join(clauses)
    rows = conn.execute(
        f"""
        SELECT bellfounder
        FROM site_index
        WHERE {where} AND bellfounder IS NOT NULL AND bellfounder != ''
        """,
        params,
    ).fetchall()
    counts: Counter[str] = Counter()
    for row in rows:
        for part in str(row["bellfounder"]).split(";"):
            name = part.strip()
            if name:
                counts[name] += 1
    return [
        {"value": value, "label": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
    ]


def _transposition_label(value: int) -> str:
    return f"+{value}" if value > 0 else str(value)


def get_filter_facets(
    *,
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
) -> dict[str, Any]:
    base = dict(
        q=q,
        continent=continent,
        country=country,
        state=state,
        year_min=year_min,
        year_max=year_max,
        bellfounder=bellfounder,
        bourdon_pitch=bourdon_pitch,
        transposition=transposition,
        range_class=range_class,
        denomination=denomination,
        institution_type=institution_type,
        instrument_type=instrument_type,
    )

    conn = connect()
    try:
        it_clauses, it_params = build_search_clauses(**base, exclude={"instrument_type"})
        instrument_types = _instrument_type_facet_rows(conn, it_clauses, it_params)

        bp_clauses, bp_params = build_search_clauses(**base, exclude={"bourdon_pitch"})
        bourdon_pitches = _facet_rows(
            conn, "bourdon_pitch", bp_clauses, bp_params, order="value"
        )

        tr_clauses, tr_params = build_search_clauses(**base, exclude={"transposition"})
        transposition_rows = _facet_rows(
            conn, "transposition_semitones", tr_clauses, tr_params, order="value_int"
        )
        transposition_semitones = [
            {
                "value": str(row["value"]),
                "label": _transposition_label(int(row["value"])),
                "count": row["count"],
            }
            for row in transposition_rows
        ]

        rc_clauses, rc_params = build_search_clauses(**base, exclude={"range_class"})
        range_classifications = _facet_rows(
            conn, "range_classification", rc_clauses, rc_params
        )

        bf_clauses, bf_params = build_search_clauses(**base, exclude={"bellfounder"})
        bellfounders = _founder_facet_rows(conn, bf_clauses, bf_params)

        dn_clauses, dn_params = build_search_clauses(**base, exclude={"denomination"})
        denominations = _facet_rows(conn, "denomination", dn_clauses, dn_params)

        inst_clauses, inst_params = build_search_clauses(**base, exclude={"institution_type"})
        institution_types = _facet_rows(
            conn, "institution_type", inst_clauses, inst_params
        )

        return {
            "instrument_types": instrument_types,
            "bourdon_pitches": bourdon_pitches,
            "transposition_semitones": transposition_semitones,
            "range_classifications": range_classifications,
            "bellfounders": bellfounders,
            "denominations": denominations,
            "institution_types": institution_types,
        }
    finally:
        conn.close()


def get_filter_options() -> dict[str, Any]:
    conn = connect()
    try:
        year_range = list(
            conn.execute(
                """
                SELECT MIN(installation_year), MAX(installation_year)
                FROM site_index WHERE installation_year IS NOT NULL
                """
            ).fetchone()
        )
    finally:
        conn.close()

    return {
        **get_filter_facets(),
        "year_range": year_range,
    }


def search_sites(
    *,
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
    map_only: bool = False,
    limit: int = 5000,
) -> dict[str, Any]:
    clauses, params = build_search_clauses(
        q=q,
        continent=continent,
        country=country,
        state=state,
        year_min=year_min,
        year_max=year_max,
        bellfounder=bellfounder,
        bourdon_pitch=bourdon_pitch,
        transposition=transposition,
        range_class=range_class,
        denomination=denomination,
        institution_type=institution_type,
        instrument_type=instrument_type,
        map_only=map_only,
    )
    where = " AND ".join(clauses)
    conn = connect()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM site_index WHERE {where}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT site_id, short_name, full_title, continent, country_code,
                   state_province, installation_year, bourdon_pitch,
                   transposition_semitones, range_classification, denomination,
                   institution_type, bellfounder, instrument_type, bell_count,
                   latitude, longitude
            FROM site_index
            WHERE {where}
            ORDER BY full_title, short_name
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        with_coords = sum(1 for r in rows if r["latitude"] is not None)
        return {
            "total": total,
            "returned": len(rows),
            "with_coordinates": with_coords,
            "results": [row_to_dict(r) for r in rows],
        }
    finally:
        conn.close()


def get_site(site_id: str) -> dict[str, Any] | None:
    conn = connect()
    try:
        site = conn.execute("SELECT * FROM sites WHERE site_id = ?", (site_id.upper(),)).fetchone()
        if not site:
            return None
        index = conn.execute(
            "SELECT * FROM site_index WHERE site_id = ?", (site_id.upper(),)
        ).fetchone()
        lists = conn.execute(
            """
            SELECT lp.filename, lp.region, lp.list_type, le.rank, le.display_name, le.line_suffix
            FROM list_entries le
            JOIN list_pages lp ON lp.id = le.list_page_id
            WHERE le.site_id = ?
            ORDER BY lp.list_type, le.rank
            """,
            (site_id.upper(),),
        ).fetchall()
        return {
            "site": row_to_dict(site),
            "index": row_to_dict(index) if index else None,
            "list_appearances": [row_to_dict(r) for r in lists],
        }
    finally:
        conn.close()
