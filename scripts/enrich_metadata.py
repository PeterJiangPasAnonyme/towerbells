#!/usr/bin/env python3
"""Build site_index table with searchable/filterable metadata from sites + list pages."""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.config import BASE_URL, DB_PATH
from scraper.fetch import fetch
from scraper.instrument_types import normalize_instrument_type
from scraper.institution_types import normalize_institution_type
from scraper.denominations import normalize_denomination
from scraper.bellfounders import normalize_founder_text, join_founder_parts, canonical_founder_name
from scraper.fdy_parse import load_founders_by_page_from_html_pages
from scraper.display_titles import display_title_for_site
from scraper.list_page_parse import parse_grouped_list_page

CONTINENT_BY_COUNTRY: dict[str, str] = {
    "USA": "North America",
    "CANADA": "North America",
    "MEXICO": "North America",
    "BERMUDA": "North America",
    "PUERTO RICO": "North America",
    "GUATEMALA": "North America",
    "HONDURAS": "North America",
    "EL SALVADOR": "North America",
    "NICARAGUA": "North America",
    "CUBA": "North America",
    "BRAZIL": "South America",
    "ARGENTINA": "South America",
    "URUGUAY": "South America",
    "VENEZUELA": "South America",
    "SURINAME": "South America",
    "NED.ANTIL.": "South America",
    "ENGLAND": "Europe",
    "SCOTLAND": "Europe",
    "N IRELAND": "Europe",
    "IRELAND": "Europe",
    "WALES": "Europe",
    "BELGIUM": "Europe",
    "FRANCE": "Europe",
    "GERMANY": "Europe",
    "NETHERLANDS": "Europe",
    "ITALY": "Europe",
    "SPAIN": "Europe",
    "PORTUGAL": "Europe",
    "SWITZERLAND": "Europe",
    "AUSTRIA": "Europe",
    "DENMARK": "Europe",
    "SWEDEN": "Europe",
    "NORWAY": "Europe",
    "FINLAND": "Europe",
    "POLAND": "Europe",
    "CZECH REP.": "Europe",
    "LUXEMBOURG": "Europe",
    "LITHUANIA": "Europe",
    "UKRAINE": "Europe",
    "RUSSIA": "Europe",
    "BOSNIA": "Europe",
    "AUSTRALIA": "Asia-Pacific",
    "NEW ZEALAND": "Asia-Pacific",
    "JAPAN": "Asia-Pacific",
    "KOREA": "Asia-Pacific",
    "CHINA": "Asia-Pacific",
    "PHILIPPINES": "Asia-Pacific",
    "EGYPT": "Africa & Mideast",
    "S AFRICA": "Africa & Mideast",
    "REUNION IS.": "Africa & Mideast",
}

FOUNDERS = [
    "Gillett & Johnston",
    "Royal Eijsbouts",
    "Eijsbouts",
    "Petit & Fritsen",
    "Taylor",
    "Whitechapel",
    "Paccard",
    "Hemony",
    "Wauthy",
    "Meeks, Watson & Co",
    "Meeks & Watson",
    "Meeks",
    "Watson",
    "Meneely",
    "McShane",
    "Schilling",
    "Michigan",
    "Buckeye",
    "Verdin",
    "Olmsted",
    "Bollée",
    "VanBergen",
    "vanBergen",
    "Van Aerschodt",
    "vanAerschodt",
    "Vanden Gheyn",
    "vandenGheyn",
    "Stuckstede",
    "Muer",
    "Holbrook",
    "Mallory",
    "Mears",
    "Warner",
    "Grosschmidt",
    "Karl Greve",
    "Perner",
    "Rincker",
]

SITE_INDEX_SCHEMA = """
CREATE TABLE IF NOT EXISTS site_index (
    site_id TEXT PRIMARY KEY,
    continent TEXT,
    country_code TEXT,
    state_province TEXT,
    installation_year INTEGER,
    bourdon_pitch TEXT,
    transposition_semitones INTEGER,
    range_classification TEXT,
    denomination TEXT,
    institution_type TEXT,
    bellfounder TEXT,
    carillon_events TEXT,
    instrument_type TEXT,
    bell_count INTEGER,
    latitude REAL,
    longitude REAL,
    short_name TEXT,
    full_title TEXT,
    search_text TEXT
);
"""

GROUPED_LIST_TYPES = {
    "denom": "denomination",
    "instype": "institution_type",
    "kr": "range_classification",
}


from scraper.bourdon_pitch import parse_bourdon_pitch(transposition: str) -> int | None:
    if not transposition:
        return None
    m = re.search(r"(up|down)\s+(\d+)\s+semitone", transposition, re.I)
    if not m:
        return None
    semitones = int(m.group(2))
    return semitones if m.group(1).lower() == "up" else -semitones


def extract_installation_year(
    prior_history: str,
    yr_suffix: str | None,
) -> int | None:
    if yr_suffix:
        m = re.match(r"(\d{4})", yr_suffix.strip())
        if m:
            return int(m.group(1))
    for text in (prior_history or "",):
        for pat in (
            r"In (\d{4}), the complete instrument",
            r"installed in (\d{4})",
            r"first installed in (\d{4})",
        ):
            m = re.search(pat, text, re.I)
            if m:
                return int(m.group(1))
    return None


def load_fdy_founders_by_page(conn: sqlite3.Connection) -> dict[str, list[str]]:
    rows = conn.execute(
        "SELECT filename FROM list_pages WHERE list_type = 'fdy' ORDER BY filename"
    ).fetchall()
    pages: dict[str, str] = {}
    for (filename,) in rows:
        try:
            pages[filename] = fetch(filename)
        except RuntimeError as exc:
            print(f"SKIP fdy {filename}: {exc}")
    return load_founders_by_page_from_html_pages(pages)


def lookup_fdy_founder(page_filename: str | None, founders_by_page: dict[str, list[str]]) -> str:
    if not page_filename:
        return ""
    page_stem = page_filename.rsplit(".", 1)[0].upper()
    founders = founders_by_page.get(page_stem, [])
    return join_founder_parts(founders)


def extract_bellfounder(prior_history: str, technical_data: str, retuned_by: str) -> str:
    prior_history = normalize_founder_text(prior_history)
    technical_data = normalize_founder_text(technical_data)
    retuned_by = normalize_founder_text(retuned_by)
    text = " ".join(filter(None, [prior_history, technical_data, retuned_by]))
    found: list[str] = []
    for founder in FOUNDERS:
        if founder.lower() in text.lower() and founder not in found:
            found.append(founder)
    m = re.search(r"made by\s+(.+?)(?:\n|$)", prior_history or "", re.I)
    if m:
        primary = canonical_founder_name(m.group(1))
        if primary and primary not in found:
            found.insert(0, primary)
    return join_founder_parts(found[:3])


def load_grouped_metadata(conn: sqlite3.Connection) -> dict[str, dict[str, str]]:
    """Load denomination, institution type, range class from all regional list pages."""
    combined: dict[str, dict[str, str]] = {}
    pages = conn.execute(
        """
        SELECT filename, list_type FROM list_pages
        WHERE list_type IN ('denom', 'instype', 'kr')
        """
    ).fetchall()

    for filename, list_type in pages:
        field = GROUPED_LIST_TYPES[list_type]
        try:
            html = fetch(filename)
        except RuntimeError as exc:
            print(f"SKIP {filename}: {exc}")
            continue
        grouped = parse_grouped_list_page(html, list_type=list_type)
        for site_id, label in grouped.items():
            combined.setdefault(site_id, {})[field] = label
        print(f"{filename}: {len(grouped)} sites tagged ({field})")

    return combined


def build_search_text(
    row: sqlite3.Row,
    extra: dict[str, str],
    *,
    title: str | None = None,
) -> str:
    parts = [
        row["site_id"],
        row["short_name"],
        title or row["full_title"],
        row["location_text"],
        row["carillonist"],
        row["remarks"],
        extra.get("denomination", ""),
        extra.get("institution_type", ""),
        extra.get("bellfounder", ""),
    ]
    return " ".join(p for p in parts if p)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SITE_INDEX_SCHEMA)
    conn.execute("DELETE FROM site_index")

    grouped = load_grouped_metadata(conn)
    founders_by_page = load_fdy_founders_by_page(conn)

    yr_by_site = {
        r["site_id"]: r["line_suffix"]
        for r in conn.execute(
            """
            SELECT le.site_id, le.line_suffix
            FROM list_entries le
            JOIN list_pages lp ON lp.id = le.list_page_id
            WHERE lp.list_type = 'yr'
            """
        )
    }

    sites = conn.execute("SELECT * FROM sites").fetchall()
    rows: list[tuple] = []

    for site in sites:
        site_id = site["site_id"]
        extra = grouped.get(site_id, {})
        year = extract_installation_year(site["prior_history"], yr_by_site.get(site_id))
        bourdon = parse_bourdon_pitch(site["heaviest_pitch"] or "")
        transposition = parse_transposition_semitones(site["transposition"] or "")
        founder = lookup_fdy_founder(site["page_filename"], founders_by_page) or None
        continent = CONTINENT_BY_COUNTRY.get(site["country_code"] or "", "Other")
        display_title = display_title_for_site(dict(site))
        search_text = build_search_text(
            site,
            {**extra, "bellfounder": founder},
            title=display_title,
        )

        rows.append(
            (
                site_id,
                continent,
                site["country_code"],
                site["state_province"],
                year,
                bourdon,
                transposition,
                extra.get("range_classification"),
                normalize_denomination(extra.get("denomination"), site["country_code"]),
                normalize_institution_type(extra.get("institution_type")),
                founder or None,
                normalize_instrument_type(site["instrument_type"]) or None,
                site["bell_count"],
                site["latitude"],
                site["longitude"],
                site["short_name"],
                display_title,
                search_text,
            )
        )

    conn.executemany(
        """
        INSERT INTO site_index (
            site_id, continent, country_code, state_province, installation_year,
            bourdon_pitch, transposition_semitones, range_classification,
            denomination, institution_type, bellfounder, instrument_type,
            bell_count, latitude, longitude, short_name, full_title, search_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM site_index").fetchone()[0]
    with_coords = conn.execute(
        "SELECT COUNT(*) FROM site_index WHERE latitude IS NOT NULL"
    ).fetchone()[0]
    print(f"site_index: {count} rows, {with_coords} with coordinates")
    conn.close()


if __name__ == "__main__":
    main()
