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
    "vanBergen",
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


def parse_bourdon_pitch(heaviest_pitch: str) -> str:
    if not heaviest_pitch:
        return ""
    m = re.search(
        r"\b(A#|B|C#|D#|F#|G#|C|D|E|F|G|A)\b",
        heaviest_pitch,
        re.I,
    )
    return m.group(1).upper() if m else ""


def parse_transposition_semitones(transposition: str) -> int | None:
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


def extract_bellfounder(prior_history: str, technical_data: str, retuned_by: str) -> str:
    text = " ".join(filter(None, [prior_history, technical_data, retuned_by]))
    found: list[str] = []
    for founder in FOUNDERS:
        if founder.lower() in text.lower() and founder not in found:
            found.append(founder)
    # Prefer original maker from prior_history first sentence
    m = re.search(r"made by\s+(.+?)(?:\n|$)", prior_history or "", re.I)
    if m:
        primary = m.group(1).strip()
        if primary and primary not in found:
            found.insert(0, primary)
    return "; ".join(found[:3])


def parse_grouped_list_page(html: str) -> dict[str, str]:
    """Map site_id -> current section label from denom/instype/kr list pages."""
    mapping: dict[str, str] = {}
    current_group = "Unknown"

    parts = re.split(r"<A\s+NAME=([^>\s]+)[^>]*>", html, flags=re.I)
    for i in range(1, len(parts), 2):
        anchor = parts[i].strip()
        content = parts[i + 1] if i + 1 < len(parts) else ""

        site_match = re.search(r"HREF=([A-Z0-9_]+\.HTM)", content, re.I)
        if site_match:
            site_id = site_match.group(1).rsplit(".", 1)[0].upper()
            mapping[site_id] = current_group
            continue

        # Skip in-page site anchor names (same tag carries HREF on kr/denom pages)
        if re.match(r"^[A-Z]{2}[A-Z0-9]{4,8}$", anchor, re.I):
            continue

        header = re.sub(r"<[^>]+>", " ", content)
        header = re.sub(r"\s+", " ", header).strip()
        if not header or len(header) > 120:
            continue
        if re.search(r"\d+\s+instruments", header, re.I):
            continue
        if header.lower().startswith("group "):
            current_group = header.split("-")[0].strip()
        elif header and not header.lower().startswith("location"):
            current_group = header

    # Fallback: line-by-line scan for pages where section headers aren't split cleanly
    if not mapping:
        for line in html.splitlines():
            header_match = re.search(
                r"<A NAME=[^>]+></A>\s*(?:<B>)?\s*(Group \d+[a-z]?\+?[^<]*)",
                line,
                re.I,
            )
            if header_match:
                current_group = header_match.group(1).split("-")[0].strip()
                continue
            denom_header = re.search(
                r"<A NAME=[A-Z0-9]+></A>\s*<B>([^<]+)</B>",
                line,
                re.I,
            )
            if denom_header:
                current_group = denom_header.group(1).strip()
                continue
            site_match = re.search(
                r"<A NAME=(\w+) HREF=(\w+\.HTM)",
                line,
                re.I,
            )
            if site_match:
                mapping[site_match.group(1).upper()] = current_group

    return mapping


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
        grouped = parse_grouped_list_page(html)
        for site_id, label in grouped.items():
            combined.setdefault(site_id, {})[field] = label
        print(f"{filename}: {len(grouped)} sites tagged ({field})")

    return combined


def build_search_text(row: sqlite3.Row, extra: dict[str, str]) -> str:
    parts = [
        row["site_id"],
        row["short_name"],
        row["full_title"],
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
        founder = extract_bellfounder(
            site["prior_history"] or "",
            site["technical_data"] or "",
            site["retuned_by"] or "",
        )
        continent = CONTINENT_BY_COUNTRY.get(site["country_code"] or "", "Other")
        search_text = build_search_text(site, {**extra, "bellfounder": founder})

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
                extra.get("denomination"),
                extra.get("institution_type"),
                founder or None,
                normalize_instrument_type(site["instrument_type"]) or None,
                site["bell_count"],
                site["latitude"],
                site["longitude"],
                site["short_name"],
                site["full_title"],
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
