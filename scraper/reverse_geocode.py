"""Reverse geocoding with SQLite cache (Nominatim / OpenStreetMap)."""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "towerbells.db"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "TowerBellsExplorer/1.0 (local research; contact: local)"
ISO2_TO_COUNTRY_CODE: dict[str, str] = {
    "us": "USA",
    "ca": "CANADA",
    "mx": "MEXICO",
    "gb": "ENGLAND",
    "nl": "NETHERLANDS",
    "be": "BELGIUM",
    "fr": "FRANCE",
    "de": "GERMANY",
    "it": "ITALY",
    "es": "SPAIN",
    "pt": "PORTUGAL",
    "at": "AUSTRIA",
    "ch": "SWITZERLAND",
    "dk": "DENMARK",
    "se": "SWEDEN",
    "no": "NORWAY",
    "fi": "FINLAND",
    "pl": "POLAND",
    "cz": "CZECH REP.",
    "au": "AUSTRALIA",
    "nz": "NEW ZEALAND",
    "jp": "JAPAN",
    "kr": "KOREA",
    "cn": "CHINA",
    "br": "BRAZIL",
    "ar": "ARGENTINA",
    "lu": "LUXEMBOURG",
    "ie": "IRELAND",
    "ba": "BOSNIA",
    "za": "S AFRICA",
    "ph": "PHILIPPINES",
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_geocode_cache(conn: sqlite3.Connection) -> None:
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


def _cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 4)},{round(lon, 4)}"


def _pick_city(address: dict[str, Any]) -> str | None:
    for key in (
        "city",
        "town",
        "village",
        "municipality",
        "hamlet",
        "suburb",
        "county",
    ):
        value = address.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _pick_region(address: dict[str, Any]) -> str | None:
    for key in ("state", "province", "region", "state_district", "county"):
        value = address.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _fetch_nominatim(lat: float, lon: float) -> dict[str, Any] | None:
    query = urllib.parse.urlencode(
        {
            "lat": lat,
            "lon": lon,
            "format": "json",
            "addressdetails": 1,
            "zoom": 10,
        }
    )
    request = urllib.request.Request(
        f"{NOMINATIM_URL}?{query}",
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None


def lookup_locality_from_coordinates(
    latitude: float | None,
    longitude: float | None,
    *,
    conn: sqlite3.Connection | None = None,
) -> dict[str, str] | None:
    """Return {city, region, country_code, country_name} from coordinates."""
    if latitude is None or longitude is None:
        return None

    own_conn = conn is None
    if own_conn:
        conn = _connect()
    assert conn is not None
    _ensure_geocode_cache(conn)

    key = _cache_key(latitude, longitude)
    cached = conn.execute(
        "SELECT city, region, country_code, country_name FROM geocode_cache WHERE cache_key = ?",
        (key,),
    ).fetchone()
    if cached:
        if own_conn:
            conn.close()
        return {
            "city": cached["city"] or "",
            "region": cached["region"] or "",
            "country_code": cached["country_code"] or "",
            "country_name": cached["country_name"] or "",
        }

    payload = _fetch_nominatim(latitude, longitude)
    if not payload:
        if own_conn:
            conn.close()
        return None

    address = payload.get("address") or {}
    city = _pick_city(address)
    region = _pick_region(address)
    iso2 = (address.get("country_code") or "").lower()
    country_code = ISO2_TO_COUNTRY_CODE.get(iso2, iso2.upper())
    country_name = address.get("country") or ""

    conn.execute(
        """
        INSERT OR REPLACE INTO geocode_cache
            (cache_key, city, region, country_code, country_name, payload, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            key,
            city,
            region,
            country_code,
            country_name,
            json.dumps(payload, ensure_ascii=False),
            time.time(),
        ),
    )
    conn.commit()

    if own_conn:
        conn.close()

    return {
        "city": city or "",
        "region": region or "",
        "country_code": country_code or "",
        "country_name": country_name or "",
    }
