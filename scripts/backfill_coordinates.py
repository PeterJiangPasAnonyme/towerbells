#!/usr/bin/env python3
"""Backfill lat/lon from towerbells.org atlas XML and cached site pages."""

from __future__ import annotations

import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scraper.config import DB_PATH, RAW_HTML_DIR, REQUEST_DELAY_SECONDS
from scraper.fetch import fetch
from scraper.parse_site import parse_coordinates_from_text

ATLAS_XML_BASE = "http://www.towerbells.org/data/atlas/xml/"
REGION_INDEX_FILES = ["XMWW.xml", "XMNA.xml", "XMEU.xml", "XMAF.xml", "XMAP.xml", "XMSA.xml"]


def _site_id_from_x(x_tag: str) -> str:
    return Path(x_tag.strip()).stem.upper()


def _coords_from_towerbell(elem: ET.Element) -> tuple[float | None, float | None]:
    ll_text = ""
    ll_elem = elem.find("ll")
    if ll_elem is not None and ll_elem.text:
        ll_text = ll_elem.text
    lat, lon = parse_coordinates_from_text(ll_text)
    if lat is not None:
        return lat, lon

    lat_attr = elem.get("lat")
    lng_attr = elem.get("lng")
    if not lat_attr or not lng_attr:
        return None, None

    lat = float(lat_attr)
    lng = float(lng_attr)
    if ll_text:
        if re.search(r"\bS\s", ll_text, re.I):
            lat = -abs(lat)
        if re.search(r"\bW\s", ll_text, re.I):
            lng = -abs(lng)
    else:
        # US/Canada state files use west longitudes without sign in attrs
        lng = -abs(lng)
    return lat, lng


def parse_atlas_xml(xml_text: str) -> dict[str, tuple[float, float]]:
    """Return {SITE_ID: (lat, lon)} from a belldata XML file."""
    coords: dict[str, tuple[float, float]] = {}
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return coords

    for elem in root.iter("towerbell"):
        x_elem = elem.find("x")
        if x_elem is None or not x_elem.text:
            continue
        site_id = _site_id_from_x(x_elem.text)
        lat, lon = _coords_from_towerbell(elem)
        if lat is None or lon is None:
            continue
        coords[site_id] = (lat, lon)
    return coords


def discover_subdivision_xml_files() -> set[str]:
    """Discover XM*.xml files referenced from regional index files."""
    files = set(REGION_INDEX_FILES)
    queue = list(REGION_INDEX_FILES)
    seen: set[str] = set()

    while queue:
        name = queue.pop()
        if name in seen:
            continue
        seen.add(name)
        try:
            xml_text = fetch(f"{ATLAS_XML_BASE}{name}", delay=True)
        except RuntimeError:
            continue
        for sc in re.findall(r'<ctrpt[^>]+sc="([A-Z0-9]{2,3})"[^>]+sub="site"', xml_text):
            sub_file = f"XM{sc}.xml"
            if sub_file not in seen:
                files.add(sub_file)
                queue.append(sub_file)
    return files


def coords_from_cached_html(site_id: str) -> tuple[float | None, float | None]:
    path = RAW_HTML_DIR / f"{site_id.lower()}.htm"
    if not path.exists():
        return None, None
    return parse_coordinates_from_text(path.read_text(encoding="utf-8", errors="replace"))


def sync_site_index_coords(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE site_index
        SET latitude = (SELECT latitude FROM sites WHERE sites.site_id = site_index.site_id),
            longitude = (SELECT longitude FROM sites WHERE sites.site_id = site_index.site_id)
        """
    )


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    known_sites = {
        r[0] for r in conn.execute("SELECT site_id FROM sites")
    }
    missing_before = conn.execute(
        "SELECT COUNT(*) FROM sites WHERE latitude IS NULL"
    ).fetchone()[0]
    print(f"Sites in DB: {len(known_sites)}, missing coords: {missing_before}")

    atlas_coords: dict[str, tuple[float, float]] = {}
    xml_files = sorted(discover_subdivision_xml_files())
    print(f"Fetching {len(xml_files)} atlas XML files…")

    for i, filename in enumerate(xml_files, start=1):
        try:
            xml_text = fetch(f"{ATLAS_XML_BASE}{filename}", delay=True)
        except RuntimeError as exc:
            print(f"  SKIP {filename}: {exc}")
            continue
        found = parse_atlas_xml(xml_text)
        atlas_coords.update(found)
        if i % 10 == 0 or i == len(xml_files):
            print(f"  [{i}/{len(xml_files)}] cumulative sites in atlas: {len(atlas_coords)}")

    updated_atlas = 0
    for site_id, (lat, lon) in atlas_coords.items():
        if site_id not in known_sites:
            continue
        row = conn.execute(
            "SELECT latitude FROM sites WHERE site_id = ?", (site_id,)
        ).fetchone()
        if row and row[0] is not None:
            continue
        conn.execute(
            "UPDATE sites SET latitude = ?, longitude = ? WHERE site_id = ?",
            (lat, lon, site_id),
        )
        updated_atlas += 1

    updated_html = 0
    for (site_id,) in conn.execute("SELECT site_id FROM sites WHERE latitude IS NULL"):
        lat, lon = coords_from_cached_html(site_id)
        if lat is None:
            continue
        conn.execute(
            "UPDATE sites SET latitude = ?, longitude = ? WHERE site_id = ?",
            (lat, lon, site_id),
        )
        updated_html += 1

    sync_site_index_coords(conn)
    conn.commit()

    missing_after = conn.execute(
        "SELECT COUNT(*) FROM sites WHERE latitude IS NULL"
    ).fetchone()[0]
    with_coords = conn.execute(
        "SELECT COUNT(*) FROM sites WHERE latitude IS NOT NULL"
    ).fetchone()[0]
    print(
        f"Done. atlas updates: {updated_atlas}, html updates: {updated_html}, "
        f"with coords: {with_coords}, still missing: {missing_after}"
    )
    conn.close()


if __name__ == "__main__":
    main()
