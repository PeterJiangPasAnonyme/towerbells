"""Structured location display for carillon detail pages."""

from __future__ import annotations

import json
import re
from typing import Any

from scraper.reverse_geocode import lookup_locality_from_coordinates
from server.geo_labels import format_country, format_region

LL_LINE_RE = re.compile(r"^LL:\s", re.I)
GENERIC_TOWER_RE = re.compile(r"^(North|South|East|West)\s+tower$", re.I)
MOBILE_RE = re.compile(r"\bmobile\b|\btravelling\b|\btraveling\b", re.I)
STORAGE_RE = re.compile(r"\bin storage\b|\bfor sale\b", re.I)
FORMERLY_RE = re.compile(r"\bformerly\b|formerly part of", re.I)
PAREN_ONLY_RE = re.compile(r"^\([^)]+\)\s*$")
ADDRESS_HINT_RE = re.compile(
    r"(?:"
    r"\bat\b|"
    r"\d{1,5}(?:st|nd|rd|th)\s+(?:Street|St\.?|Avenue|Ave\.?|Drive|Dr\.?|Road|Rd\.?|"
    r"Boulevard|Blvd\.?|Lane|Ln\.?|Way|Place|Parade|Parkway|Pkwy\.?|Circle|Crescent|"
    r"Close|Terrace|Highway|Hwy\.?)\b|"
    r"\d{1,5}[A-Za-z]?\s+(?:North|South|East|West|[NSEW]\.?)\s+\w+|"
    r"(?<![A-Za-z])(?:Street|St\.|Avenue|Ave\.|Drive|Dr\.|Road|Rd\.|Boulevard|Blvd\.|"
    r"Lane|Ln\.|Highway|Hwy\.|Route|Terrace|Circle|Crescent|Close|Parade|Parkway|Pkwy\.)\b|"
    r"(?:Rue |Straat|steenweg|Kerkstraat|Boulevard |Governors Drive|Woodlawn Avenue|"
    r"Pennsylvania Avenue|Jefferson Davis Highway|Chapman Avenue|Rodney Street|"
    r"North Robinson|Shartel Avenue|King'?s Parade|Place du |Domplatz|Kerkplein|Grote Markt|"
    r"Markt |Platz|Square |plassen|plass|\bgate\b|\bweg\b|\bstrasse\b|\bstraße\b)"
    r")",
    re.I,
)

COUNTRY_TOKENS = [
    "United States",
    "USA",
    "Netherlands",
    "Belgium",
    "France",
    "Germany",
    "Canada",
    "England",
    "Scotland",
    "Northern Ireland",
    "N Ireland",
    "Ireland",
    "Denmark",
    "Sweden",
    "Norway",
    "Finland",
    "Austria",
    "Switzerland",
    "Italy",
    "Spain",
    "Portugal",
    "Poland",
    "Czech Republic",
    "Czechoslovakia",
    "Australia",
    "New Zealand",
    "Japan",
    "China",
    "Brazil",
    "Argentina",
    "Mexico",
    "Bosnia and Herzegovina",
    "Bosnia",
    "Russia",
    "Ukraine",
    "Luxembourg",
    "Lithuania",
    "Hungary",
    "Romania",
    "Slovenia",
    "Croatia",
    "South Africa",
    "Egypt",
    "Philippines",
    "South Korea",
    "Korea",
    "Puerto Rico",
    "Bermuda",
    "Netherlands Antilles",
    "Réunion",
    "Reunion",
    "Guatemala",
    "Honduras",
    "El Salvador",
    "Nicaragua",
    "Cuba",
    "Uruguay",
    "Venezuela",
    "Suriname",
]

COUNTRY_RAW_TO_CODE: dict[str, str] = {
    "usa": "USA",
    "united states": "USA",
    "netherlands": "NETHERLANDS",
    "belgium": "BELGIUM",
    "france": "FRANCE",
    "germany": "GERMANY",
    "canada": "CANADA",
    "england": "ENGLAND",
    "scotland": "SCOTLAND",
    "northern ireland": "N IRELAND",
    "n ireland": "N IRELAND",
    "ireland": "IRELAND",
    "denmark": "DENMARK",
    "sweden": "SWEDEN",
    "norway": "NORWAY",
    "finland": "FINLAND",
    "austria": "AUSTRIA",
    "switzerland": "SWITZERLAND",
    "italy": "ITALY",
    "spain": "SPAIN",
    "portugal": "PORTUGAL",
    "poland": "POLAND",
    "czech republic": "CZECH REP.",
    "czechoslovakia": "CZECH REP.",
    "australia": "AUSTRALIA",
    "new zealand": "NEW ZEALAND",
    "japan": "JAPAN",
    "china": "CHINA",
    "brazil": "BRAZIL",
    "argentina": "ARGENTINA",
    "mexico": "MEXICO",
    "bosnia and herzegovina": "BOSNIA",
    "bosnia": "BOSNIA",
    "russia": "RUSSIA",
    "ukraine": "UKRAINE",
    "luxembourg": "LUXEMBOURG",
    "lithuania": "LITHUANIA",
    "south africa": "S AFRICA",
    "egypt": "EGYPT",
    "philippines": "PHILIPPINES",
    "south korea": "KOREA",
    "korea": "KOREA",
    "puerto rico": "PUERTO RICO",
    "bermuda": "BERMUDA",
    "netherlands antilles": "NED.ANTIL.",
}


def parse_location_override(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _normalize_key(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").lower()).strip(" .,;-")
    text = re.sub(r"[^\w\s]", "", text)
    return text


def _lines_without_coords(location_text: str) -> list[str]:
    lines: list[str] = []
    for raw in (location_text or "").splitlines():
        line = raw.strip()
        if line and not LL_LINE_RE.match(line):
            lines.append(line)
    return lines


def _country_code_from_raw(country_raw: str | None, fallback: str) -> str:
    if fallback:
        return fallback.upper()
    if not country_raw:
        return ""
    return COUNTRY_RAW_TO_CODE.get(country_raw.strip().lower(), country_raw.upper())


def _combine_at_lines(address_lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in address_lines:
        if line.lower().startswith("at ") and merged:
            merged[-1] = f"{merged[-1]} {line}"
        else:
            merged.append(line)
    return merged


def _merge_broken_locality_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if (
            index + 1 < len(lines)
            and line.rstrip().endswith(",")
            and _find_locality_index([lines[index + 1]]) is not None
        ):
            merged.append(f"{line.rstrip()} {lines[index + 1].strip()}")
            index += 2
            continue
        merged.append(line)
        index += 1
    return merged


def _find_locality_index(lines: list[str]) -> int | None:
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        for token in sorted(COUNTRY_TOKENS, key=len, reverse=True):
            if re.search(rf",\s*{re.escape(token)}\s*$", line, re.I):
                return index
            if re.fullmatch(re.escape(token), line, re.I):
                return index
    return None


def _split_locality_line(line: str) -> tuple[str | None, str | None, str | None]:
    text = line.strip()
    country_raw = None
    for token in sorted(COUNTRY_TOKENS, key=len, reverse=True):
        match = re.search(rf",\s*({re.escape(token)})\s*$", text, re.I)
        if match:
            country_raw = match.group(1)
            text = text[: match.start()].strip()
            break
    if country_raw is None:
        for token in COUNTRY_TOKENS:
            if re.fullmatch(re.escape(token), text, re.I):
                return None, None, token
        return None, None, None

    parts = [part.strip() for part in text.split(",") if part.strip()]
    if not parts:
        return None, None, country_raw
    if len(parts) == 1:
        return parts[0], None, country_raw
    return parts[0], parts[-1], country_raw


def _parse_city_part(city: str) -> tuple[str, str | None]:
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", city.strip())
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return city.strip(), None


def _is_duplicate_of_title(text: str, page_title: str) -> bool:
    if not text or not page_title:
        return False
    if _looks_like_address(text):
        return False
    left = _normalize_key(text.replace("—", " ").replace("/", " "))
    right = _normalize_key(page_title)
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 8 and left in right:
        return True
    if len(right) >= 8 and right in left:
        return True
    if len(left) >= 10 and len(right) >= 10 and (left in right or right in left):
        return True
    return False


def _is_institution_qualifier(line: str) -> bool:
    return (
        bool(re.match(r"^.+\([^)]+\)\s*$", line.strip()))
        and not _looks_like_address(line)
        and not FORMERLY_RE.search(line)
    )


def _format_locality_line(
    city: str | None,
    city_alt: str | None,
    region_from_text: str | None,
    *,
    country_code: str,
    state_province: str,
) -> str | None:
    """Build 'City, Province, Country' (province omitted when not applicable)."""
    display_parts: list[str] = []

    city_key = _normalize_key(city or "")
    alt_key = _normalize_key(city_alt or "")
    if city:
        if city_alt and alt_key != city_key:
            display_parts.append(f"{city} ({city_alt})")
        else:
            display_parts.append(city)
    elif city_alt:
        display_parts.append(city_alt)

    region = format_region(country_code, state_province or region_from_text or "")
    if not region and region_from_text:
        region = region_from_text.strip()
    region_key = _normalize_key(region)
    country = format_country(country_code)
    country_key = _normalize_key(country)

    if region and region_key not in {city_key, alt_key, country_key}:
        display_parts.append(region)

    if country:
        display_parts.append(country)

    return ", ".join(display_parts) if display_parts else None


def _expand_partial_locality(
    locality: str,
    *,
    country_code: str,
    state_province: str,
) -> str:
    """Ensure saved locality strings include country (and region when obvious)."""
    text = locality.strip()
    if not text:
        return text

    country = format_country(country_code)
    if country and _normalize_key(country) in _normalize_key(text):
        return text

    parts = [part.strip() for part in text.split(",") if part.strip()]
    region = format_region(country_code, state_province)
    if len(parts) == 1 and region and _normalize_key(region) not in _normalize_key(text):
        return f"{parts[0]}, {region}, {country}" if country else f"{parts[0]}, {region}"
    if country:
        return f"{text}, {country}"
    return text


def _looks_like_address(line: str) -> bool:
    return bool(ADDRESS_HINT_RE.search(line))


def _format_badge(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", str(text).strip())
    if not cleaned:
        return None
    return cleaned.title()


def _format_location_name(text: str | None) -> str | None:
    """Title-case location names without disturbing mixed-case proper nouns."""
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", str(text).strip())
    if not cleaned:
        return None

    def title_token(token: str) -> str:
        if not token:
            return token
        if token.isupper() and len(token) > 1:
            return token
        if token.islower():
            return token[:1].upper() + token[1:]
        return token

    def title_segment(segment: str) -> str:
        return " ".join(title_token(word) for word in segment.split())

    for sep in (" / ", " — ", " – "):
        if sep in cleaned:
            return sep.join(title_segment(part) for part in cleaned.split(sep))
    return title_segment(cleaned)


def _detect_badge(lines: list[str]) -> str | None:
    joined = "\n".join(lines)
    if STORAGE_RE.search(joined):
        for line in lines:
            if STORAGE_RE.search(line):
                cleaned = line.strip()
                if PAREN_ONLY_RE.match(cleaned):
                    return _format_badge(cleaned.strip("()"))
                return _format_badge(cleaned)
        return "In Storage"
    if MOBILE_RE.search(joined) or any(re.fullmatch(r"\(mobile\)", line, re.I) for line in lines):
        return "Mobile Carillon"
    return None


def _merge_note_lines(lines: list[str], start: int) -> tuple[str, int]:
    parts = [lines[start].strip()]
    index = start + 1
    open_parens = parts[0].count("(") - parts[0].count(")")
    while index < len(lines) and open_parens > 0:
        parts.append(lines[index].strip())
        open_parens += lines[index].count("(") - lines[index].count(")")
        index += 1
    return re.sub(r"\s+", " ", " ".join(parts)).strip(), index


def _maps_url(latitude: float | None, longitude: float | None) -> str | None:
    if latitude is None or longitude is None:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"


def _dedupe_aka_against_address(
    also_known_as: list[str],
    address_lines: list[str],
) -> list[str]:
    if not also_known_as or not address_lines:
        return also_known_as
    address_blob = _normalize_key(" ".join(address_lines))
    kept: list[str] = []
    for item in also_known_as:
        item_key = _normalize_key(item)
        if item_key and item_key in address_blob:
            continue
        kept.append(item)
    return kept


def _location_has_content(location: dict[str, Any]) -> bool:
    return bool(
        location.get("name")
        or location.get("also_known_as")
        or location.get("address_lines")
        or location.get("locality")
        or location.get("notes")
    )


def _apply_override(
    result: dict[str, Any],
    override: dict[str, Any] | None,
    *,
    country_code: str = "",
    state_province: str = "",
) -> dict[str, Any]:
    if not override:
        return result

    # Saved override is authoritative — never merge with auto-parsed location_text.
    display: dict[str, Any] = {
        "badge": None,
        "name": None,
        "also_known_as": [],
        "address_lines": [],
        "locality": None,
        "notes": [],
        "maps_url": None if override.get("hide_maps") else result.get("maps_url"),
        "has_content": False,
    }

    if override.get("hide_name"):
        display["name"] = None
    elif "name" in override:
        name = override["name"]
        display["name"] = _format_location_name(str(name).strip() if name else None)

    if "badge" in override:
        badge = override["badge"]
        display["badge"] = _format_badge(str(badge).strip() if badge else None)
    else:
        display["badge"] = result.get("badge")

    if "locality" in override:
        locality = override["locality"]
        text = str(locality).strip() if locality else ""
        display["locality"] = (
            _expand_partial_locality(text, country_code=country_code, state_province=state_province)
            if text
            else None
        )

    for key in ("also_known_as", "notes", "address_lines"):
        if key in override and isinstance(override[key], list):
            display[key] = [str(item).strip() for item in override[key] if str(item).strip()]

    display["also_known_as"] = _dedupe_aka_against_address(
        display.get("also_known_as") or [],
        display.get("address_lines") or [],
    )

    display["has_content"] = _location_has_content(display)
    return display


def build_location_display(
    site: dict,
    *,
    page_title: str = "",
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return structured location fields for the detail page."""
    location_text = site.get("location_text") or ""
    country_code = _country_code_from_raw(None, site.get("country_code") or "")
    state_province = site.get("state_province") or ""

    lines = _merge_broken_locality_lines(_lines_without_coords(location_text))
    badge = _detect_badge(lines)

    locality_index = _find_locality_index(lines)
    city = city_alt = region_from_text = None
    if locality_index is not None:
        city, region_from_text, country_raw = _split_locality_line(lines[locality_index])
        country_code = _country_code_from_raw(country_raw, country_code)
        if city:
            city, city_alt = _parse_city_part(city)
        content_lines = lines[:locality_index] + lines[locality_index + 1 :]
    else:
        content_lines = lines

    content_lines = [
        line
        for line in content_lines
        if not re.fullmatch(r"\(mobile\)", line.strip(), re.I)
        and not (
            badge
            and STORAGE_RE.search(badge)
            and STORAGE_RE.search(line)
            and not _looks_like_address(line)
            and _find_locality_index([line]) is None
        )
    ]

    name: str | None = None
    also_known_as: list[str] = []
    address_lines: list[str] = []
    notes: list[str] = []

    index = 0
    name_parts: list[str] = []
    while index < len(content_lines):
        line = content_lines[index]
        if FORMERLY_RE.search(line) or line.startswith("("):
            break
        if PAREN_ONLY_RE.match(line):
            break
        if _is_institution_qualifier(line):
            break
        if _looks_like_address(line):
            break
        if GENERIC_TOWER_RE.match(line) and index + 1 < len(content_lines):
            name_parts.append(f"{line} — {content_lines[index + 1]}")
            index += 2
            continue
        name_parts.append(line)
        index += 1

    if name_parts:
        name = _format_location_name(" / ".join(name_parts))
        if _is_duplicate_of_title(name or "", page_title):
            name = None

    if (
        index < len(content_lines)
        and _is_institution_qualifier(content_lines[index])
    ):
        qualifier = content_lines[index].strip()
        if not _is_duplicate_of_title(qualifier, page_title):
            also_known_as.append(qualifier)
        index += 1

    while index < len(content_lines):
        line = content_lines[index]
        if PAREN_ONLY_RE.match(line):
            note = line.strip()
            if note.startswith("(") and note.endswith(")"):
                note = note[1:-1].strip()
            if note and not _is_duplicate_of_title(note, page_title):
                also_known_as.append(note)
            index += 1
            continue
        if FORMERLY_RE.search(line) or (
            line.startswith("(") and not PAREN_ONLY_RE.match(line)
        ):
            note, index = _merge_note_lines(content_lines, index)
            if note:
                notes.append(note)
            continue
        if _is_institution_qualifier(line):
            if not _is_duplicate_of_title(line, page_title):
                also_known_as.append(line.strip())
            index += 1
            continue
        if _is_duplicate_of_title(line, page_title):
            index += 1
            continue
        address_lines.append(line)
        index += 1

    also_known_as = [
        item
        for item in also_known_as
        if not _is_duplicate_of_title(item, page_title)
        and _normalize_key(item) != _normalize_key(badge or "")
    ]

    address_lines = _combine_at_lines(address_lines)

    also_known_as = _dedupe_aka_against_address(also_known_as, address_lines)

    latitude = site.get("latitude")
    longitude = site.get("longitude")
    if (not city or locality_index is None) and latitude is not None and longitude is not None:
        geo = lookup_locality_from_coordinates(latitude, longitude)
        if geo:
            city = city or geo.get("city") or None
            if not state_province:
                state_province = geo.get("region") or state_province
            if not country_code:
                country_code = _country_code_from_raw(
                    geo.get("country_name"),
                    geo.get("country_code") or "",
                )

    locality = _format_locality_line(
        city,
        city_alt,
        region_from_text,
        country_code=country_code,
        state_province=state_province,
    )

    result = {
        "badge": badge,
        "name": name,
        "also_known_as": also_known_as,
        "address_lines": address_lines,
        "locality": locality,
        "notes": notes,
        "maps_url": _maps_url(site.get("latitude"), site.get("longitude")),
        "has_content": False,
    }

    result["has_content"] = _location_has_content(result)

    return _apply_override(
        result,
        override,
        country_code=country_code,
        state_province=state_province,
    )
