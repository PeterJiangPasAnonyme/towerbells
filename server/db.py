"""SQLite query helpers for the TowerBells search API."""

from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any

from scraper.carillon_events import (
    EVENT_TYPE_OPTIONS,
    events_from_json,
    normalize_year_event_types,
)
from scraper.display_titles import build_site_display, display_title_for_site, format_site_subtitle
from scraper.bourdon_pitch import sort_bourdon_pitch_facets
from scraper.instrument_types import normalize_instrument_type
from scraper.bellfounders import MIN_FOUNDER_FACET_COUNT, split_founder_parts
from server.geo_labels import format_country, format_region
from server.range_classifications import (
    RANGE_CLASSIFICATION_LEGEND,
    sort_range_classification_facets,
)

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "towerbells.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(sites)")}
    if "location_display_override" not in columns:
        conn.execute("ALTER TABLE sites ADD COLUMN location_display_override TEXT")
    if "display_title_override" not in columns:
        conn.execute("ALTER TABLE sites ADD COLUMN display_title_override TEXT")
    if "schedule_display_override" not in columns:
        conn.execute("ALTER TABLE sites ADD COLUMN schedule_display_override TEXT")
    if "contact_display_override" not in columns:
        conn.execute("ALTER TABLE sites ADD COLUMN contact_display_override TEXT")
    if "carillonist_display_override" not in columns:
        conn.execute("ALTER TABLE sites ADD COLUMN carillonist_display_override TEXT")
    if "past_carillonist_display_override" not in columns:
        conn.execute("ALTER TABLE sites ADD COLUMN past_carillonist_display_override TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS geocode_cache (
            cache_key TEXT PRIMARY KEY,
            city TEXT,
            region TEXT,
            country_code TEXT,
            country_name TEXT,
            payload TEXT,
            fetched_at REAL
        )
        """
    )
    conn.commit()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


def _col(table_alias: str, column: str) -> str:
    return f"{table_alias}.{column}" if table_alias else column


def _bellfounder_part_clause(bellfounder: str, *, table_alias: str = "site_index") -> tuple[str, list[Any]]:
    """Match one semicolon-separated founder part exactly (same rule as facet counts)."""
    founder = bellfounder.strip()
    col = _col(table_alias, "bellfounder")
    clause = f"({col} = ? OR {col} LIKE ? OR {col} LIKE ? OR {col} LIKE ?)"
    params = [
        founder,
        f"{founder}; %",
        f"%; {founder}",
        f"%; {founder}; %",
    ]
    return clause, params


def _year_event_filter_clause(
    *,
    year_min: int | None,
    year_max: int | None,
    year_event_types: list[str] | None,
    table_alias: str = "site_index",
) -> tuple[str, list[Any]]:
    if year_min is None and year_max is None:
        return "", []

    event_types = normalize_year_event_types(year_event_types)
    type_placeholders = ", ".join("?" for _ in event_types)
    params: list[Any] = [*event_types]
    events_col = _col(table_alias, "carillon_events")

    event_conditions = [f"json_extract(evt.value, '$.type') IN ({type_placeholders})"]
    if year_min is not None:
        event_conditions.append("CAST(json_extract(evt.value, '$.year') AS INTEGER) >= ?")
        params.append(year_min)
    if year_max is not None:
        event_conditions.append("CAST(json_extract(evt.value, '$.year') AS INTEGER) <= ?")
        params.append(year_max)

    event_where = " AND ".join(event_conditions)
    clauses = [
        f"""
        EXISTS (
            SELECT 1
            FROM json_each(COALESCE({events_col}, '[]')) AS evt
            WHERE {event_where}
        )
        """
    ]

    if "installed" in event_types:
        fallback_parts = [f"{_col(table_alias, 'installation_year')} IS NOT NULL"]
        fallback_params: list[Any] = []
        if year_min is not None:
            fallback_parts.append(f"{_col(table_alias, 'installation_year')} >= ?")
            fallback_params.append(year_min)
        if year_max is not None:
            fallback_parts.append(f"{_col(table_alias, 'installation_year')} <= ?")
            fallback_params.append(year_max)
        fallback_parts.append(
            f"({_col(table_alias, 'carillon_events')} IS NULL OR "
            f"{_col(table_alias, 'carillon_events')} = '' OR "
            f"{_col(table_alias, 'carillon_events')} = '[]')"
        )
        clauses.append(f"({' AND '.join(fallback_parts)})")
        params.extend(fallback_params)

    return f"({' OR '.join(clauses)})", params


def build_search_clauses(
    *,
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    year_event_types: list[str] | None = None,
    bellfounder: str | None = None,
    bourdon_pitch: str | None = None,
    transposition: int | None = None,
    range_class: str | None = None,
    denomination: str | None = None,
    institution_type: str | None = None,
    instrument_type: str | None = None,
    map_only: bool = False,
    exclude: set[str] | None = None,
    table_alias: str = "site_index",
) -> tuple[list[str], list[Any]]:
    exclude = exclude or set()
    clauses = ["1=1"]
    params: list[Any] = []

    def col(name: str) -> str:
        return f"{table_alias}.{name}"

    if q.strip() and "q" not in exclude:
        clauses.append(f"{col('search_text')} LIKE ?")
        params.append(f"%{q.strip()}%")
    if continent and "continent" not in exclude:
        clauses.append(f"{col('continent')} = ?")
        params.append(continent)
    if country and "country" not in exclude:
        clauses.append(f"{col('country_code')} = ?")
        params.append(country)
    if state and "state" not in exclude:
        clauses.append(f"{col('state_province')} = ?")
        params.append(state)
    if (year_min is not None or year_max is not None) and "year_min" not in exclude and "year_max" not in exclude:
        year_clause, year_params = _year_event_filter_clause(
            year_min=year_min,
            year_max=year_max,
            year_event_types=year_event_types,
            table_alias=table_alias,
        )
        clauses.append(year_clause)
        params.extend(year_params)
    if bourdon_pitch and "bourdon_pitch" not in exclude:
        clauses.append(f"{col('bourdon_pitch')} = ?")
        params.append(bourdon_pitch)
    if transposition is not None and "transposition" not in exclude:
        clauses.append(f"{col('transposition_semitones')} = ?")
        params.append(transposition)
    if range_class and "range_class" not in exclude:
        clauses.append(f"{col('range_classification')} = ?")
        params.append(range_class)
    if denomination and "denomination" not in exclude:
        clauses.append(f"{col('denomination')} = ?")
        params.append(denomination)
    if institution_type and "institution_type" not in exclude:
        clauses.append(f"{col('institution_type')} = ?")
        params.append(institution_type)
    if instrument_type and "instrument_type" not in exclude:
        clauses.append(f"LOWER({col('instrument_type')}) = LOWER(?)")
        params.append(instrument_type)
    if bellfounder and "bellfounder" not in exclude:
        part_clause, part_params = _bellfounder_part_clause(bellfounder, table_alias=table_alias)
        clauses.append(part_clause)
        params.extend(part_params)
    if map_only and "map_only" not in exclude:
        clauses.append(f"{col('latitude')} IS NOT NULL AND {col('longitude')} IS NOT NULL")

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
    year_event_types: list[str] | None = None,
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
        year_event_types=year_event_types,
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
        for part in split_founder_parts(row["bellfounder"]):
            counts[part] += 1
    return [
        {"value": value, "label": value, "count": count}
        for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].lower()))
        if count >= MIN_FOUNDER_FACET_COUNT
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
    year_event_types: list[str] | None = None,
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
        year_event_types=year_event_types,
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
        bourdon_pitches = sort_bourdon_pitch_facets(
            _facet_rows(conn, "bourdon_pitch", bp_clauses, bp_params, order="value")
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
        range_classifications = sort_range_classification_facets(
            _facet_rows(conn, "range_classification", rc_clauses, rc_params)
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
                SELECT
                    MIN(CAST(json_extract(evt.value, '$.year') AS INTEGER)),
                    MAX(CAST(json_extract(evt.value, '$.year') AS INTEGER))
                FROM site_index
                JOIN json_each(COALESCE(site_index.carillon_events, '[]')) AS evt
                WHERE json_extract(evt.value, '$.type') = 'installed'
                """
            ).fetchone()
        )
        if year_range[0] is None:
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
        "year_event_types": EVENT_TYPE_OPTIONS,
        "range_classification_legend": RANGE_CLASSIFICATION_LEGEND,
    }


def search_sites(
    *,
    q: str = "",
    continent: str | None = None,
    country: str | None = None,
    state: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    year_event_types: list[str] | None = None,
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
        year_event_types=year_event_types,
        bellfounder=bellfounder,
        bourdon_pitch=bourdon_pitch,
        transposition=transposition,
        range_class=range_class,
        denomination=denomination,
        institution_type=institution_type,
        instrument_type=instrument_type,
        map_only=map_only,
        table_alias="i",
    )
    where = " AND ".join(clauses)
    conn = connect()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM site_index i INNER JOIN sites s ON s.site_id = i.site_id WHERE {where}",
            params,
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT i.site_id, i.short_name, i.continent, i.country_code,
                   i.state_province, i.installation_year, i.bourdon_pitch,
                   i.transposition_semitones, i.range_classification, i.denomination,
                   i.institution_type, i.bellfounder, i.instrument_type, i.bell_count,
                   i.latitude, i.longitude,
                   s.full_title, s.display_title_override, s.location_text,
                   s.location_display_override
            FROM site_index i
            INNER JOIN sites s ON s.site_id = i.site_id
            WHERE {where}
            ORDER BY i.full_title, i.short_name
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        with_coords = sum(1 for r in rows if r["latitude"] is not None)
        results = []
        for row in rows:
            item = row_to_dict(row)
            title = display_title_for_site(item)
            item["display_title"] = title
            item["display_subtitle"] = format_site_subtitle(
                country_code=item.get("country_code"),
                state_province=item.get("state_province"),
                bell_count=item.get("bell_count"),
                installation_year=item.get("installation_year"),
                bourdon_pitch=item.get("bourdon_pitch"),
            )
            results.append(item)
        return {
            "total": total,
            "returned": len(results),
            "with_coordinates": with_coords,
            "results": results,
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
        index_data = row_to_dict(index) if index else None
        if index_data is not None:
            index_data["carillon_events"] = events_from_json(index_data.get("carillon_events"))
        site_data = row_to_dict(site)

        def _lookup_site(site_id: str) -> dict[str, Any] | None:
            row = conn.execute("SELECT * FROM sites WHERE site_id = ?", (site_id.upper(),)).fetchone()
            return row_to_dict(row) if row else None

        return {
            "site": site_data,
            "index": index_data,
            "display": build_site_display(site_data, index=index_data, get_site=_lookup_site),
            "list_appearances": [row_to_dict(r) for r in lists],
        }
    finally:
        conn.close()
