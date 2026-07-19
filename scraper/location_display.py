"""Structured location display for carillon detail pages."""

from __future__ import annotations

import json
import re
from typing import Any

from scraper.reverse_geocode import lookup_locality_from_coordinates
from scraper.text import format_display_text
from server.geo_labels import CA_PROVINCE_NAMES, US_STATE_NAMES, format_country, format_region

LL_LINE_RE = re.compile(r"^LL:\s", re.I)
GENERIC_TOWER_RE = re.compile(r"^(North|South|East|West)\s+tower$", re.I)
MOBILE_RE = re.compile(r"\bmobile\b|\btravelling\b|\btraveling\b", re.I)
STORAGE_RE = re.compile(r"\bin storage\b|\bfor sale\b", re.I)
FORMERLY_RE = re.compile(r"\bformerly\b|formerly part of", re.I)
_BUILDING_RENAME_RE = re.compile(
    r"^(?:was\b|formerly\b|previously(?:\s+known\s+as)?\b|originally\b)",
    re.I,
)
_ADDRESS_CONTINUATION_START_RE = re.compile(
    r"^(?:,\s*)?(?:and|or|near|at|between|opposite|beside|adjacent to|&)\b",
    re.I,
)
PAREN_ONLY_RE = re.compile(r"^\([^)]+\)\s*$")
_STREET_ABBR_RE = (
    r"(?<![A-Za-z])(?:St|Dr|Rd|Ave|Ln|Blvd|Pkwy|Hwy)\.(?=\s|$|[,;)])"
)
_ADDRESS_CORE_RE = (
    r"(?:"
    r"\bat\b|"
    r"\d{1,5}(?:st|nd|rd|th)\s+(?:and|&)\s+|"
    r"\d{1,5}(?:st|nd|rd|th)\s+(?:Street|St\.?|Avenue|Ave\.?|Drive|Dr\.?|Road|Rd\.?|"
    r"Boulevard|Blvd\.?|Lane|Ln\.?|Way|Place|Parade|Parkway|Pkwy\.?|Circle|Crescent|"
    r"Close|Terrace|Highway|Hwy\.?)\b|"
    r"\d{1,5}[A-Za-z]?\s+(?:North|South|East|West|[NSEW]\.?)\s+\w+|"
    r"(?<![A-Za-z])(?:Street|Streets|Road|Roads|Avenue|Avenues|Drive|Drives|"
    r"Boulevard|Boulevards|Lane|Lanes|Highway|Highways|Route|Terrace|Circle|Crescent|"
    r"Close|Parade|Parkway|Way|Ways)\b|"
    + _STREET_ABBR_RE
    + r"|"
    r"(?:\b(?:and|&)\b.*\b(?:Street|St\.|Streets|Road|Rd\.|Avenue|Ave\.|Drive|Dr\.|"
    r"Place|Lane|Way|Court|Markt|plein|laan|vej|gade|straße|strasse)\b|"
    r"\b(?:Street|St\.|Streets|Road|Rd\.|Avenue|Ave\.|Drive|Dr\.|Place|Lane|Way|Court|"
    r"Markt|plein|laan|vej|gade|straße|strasse)\b.*\b(?:and|&)\b)|"
    r"(?:Rue |Straat|steenweg|Kerkstraat|Boulevard |Governors Drive|Woodlawn Avenue|"
    r"Pennsylvania Avenue|Jefferson Davis Highway|Chapman Avenue|Rodney Street|"
    r"North Robinson|Shartel Avenue|King'?s Parade|Place du |Domplatz|Kerkplein|Grote Markt|"
    r"straße|strasse|\bPlatz\b|\bSquare\b|plassen|plass|\bgate\b|\bweg\b)"
    r")"
)
_ADDRESS_CONTINUATION_RE = (
    r"(?:"
    r"\bnear\b|"
    r"\bnr\s+\w|"
    r"\bCourt\b|\bCourts\b|"
    r"\bMarkt\b|\bTorvet\b|\bplein\b|\blaan\b|\bvej\b|\bvägen\b|\bgade\b|"
    r"\w*markt\b|\w*vej\b|\w*vägen\b|\w*gade\b|\w*laan\b|\w*poort\b|"
    r"\bPlace\b"
    r")"
)
ADDRESS_HINT_RE = re.compile(_ADDRESS_CORE_RE + r"|" + _ADDRESS_CONTINUATION_RE, re.I)
ADDRESS_CORE_RE = re.compile(_ADDRESS_CORE_RE, re.I)
ADDRESS_CONTINUATION_RE = re.compile(_ADDRESS_CONTINUATION_RE, re.I)
INSTITUTION_CONTEXT_RE = re.compile(
    r"(?:"
    r"\b(?:University|Seminary|Institute|Academy)\b|"
    r"\b(?:Main\s+)?Campus\b|"
    r"\bcampus\s+center\b|"
    r"\b\w+\s+College\b(?!\s+(?:Hall|Building|Tower|Mall|Street|Avenue|Drive|Road|and|&))"
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
    "Brasil",
    "Brazil",
    "Eire",
]

_US_STATE_CODES = set(US_STATE_NAMES)
_CA_PROVINCE_CODES = set(CA_PROVINCE_NAMES)
_US_STATE_NAMES_LOWER = {name.lower(): code for code, name in US_STATE_NAMES.items()}
_CA_PROVINCE_NAMES_LOWER = {name.lower(): code for code, name in CA_PROVINCE_NAMES.items()}

_ENGLISH_HINT_RE = re.compile(
    r"\b(?:the|of|and|church|chapel|tower|university|street|saint|st\.|our|lady|"
    r"cross|holy|memorial|building|school|college|avenue|road|drive|place|park|"
    r"cathedral|abbey|parliament|center|centre|blood|peace|was|formerly|town)\b",
    re.I,
)
_DENOM_PAREN_RE = re.compile(
    r"^(?:RC|PCUSA|TEC|LCMS|UCC|ABC|NCSU|USA|Episcopal|Mosaic|PC\(USA\)|"
    r"Reformed Church in America|Christian Science)$",
    re.I,
)
_DENOMINATION_LABELS = frozenset(
    {
        "rc",
        "r c",
        "pcusa",
        "pc usa",
        "pc(usa)",
        "tec",
        "lcms",
        "ucc",
        "abc",
        "ncsu",
        "usa",
        "elca",
        "elcic",
        "umc",
        "episcopal",
        "anglican",
        "lutheran",
        "baptist",
        "methodist",
        "presbyterian",
        "presbyterian or reformed",
        "catholic",
        "roman catholic",
        "mosaic",
        "christian science",
        "christian",
        "reformed church in america",
        "united church of christ",
        "church of christ",
        "non denominational",
        "non-denominational",
        "quaker",
        "mormon",
        "masonic",
        "n h",
        "r k",
        "r k kerk",
        "r.c.",
        "r.c",
        "n.h.",
        "n.h",
        "n.h.kerk",
        "r.k.kerk",
        "r.k.",
        "r.k",
        "o.l.v.",
        "o.l.v",
    }
)
_ADDRESS_FOOTNOTE_RE = re.compile(r"^[*†=#]|(?:^|\s)=\s")
_CHURCH_NAME_RE = re.compile(
    r"\b(?:"
    r"church|chapel|cathedral|basilica|abbey|minster|priory|shrine|"
    r"kerk|toren|kirke|domkirke|dom|"
    r"église|eglise|"
    r"kirche|"
    r"presbyterian|episcopal|anglican|lutheran|baptist|methodist|catholic|"
    r"congregational|unitarian|orthodox|evangelical|reformed"
    r")\b",
    re.I,
)


def _is_address_footnote(text: str) -> bool:
    cleaned = text.strip().strip("()")
    return bool(cleaned and _ADDRESS_FOOTNOTE_RE.search(cleaned))


def _is_denomination_label(text: str) -> bool:
    cleaned = text.strip().strip("()")
    if not cleaned:
        return False
    if _DENOM_PAREN_RE.fullmatch(cleaned):
        return True
    return _normalize_key(cleaned) in _DENOMINATION_LABELS


def _looks_like_church_name(line: str) -> bool:
    stripped = line.strip()
    if not stripped or not _CHURCH_NAME_RE.search(stripped):
        return False
    if re.match(r"^(?:Ned\.|R\.?\s?K\.?|R\.?C\.?|N\.?H\.?|O\.?l\.?v\.?)", stripped, re.I):
        return False
    if re.search(r"\bkerkhof\b", stripped, re.I):
        return False
    if re.search(r"\b(?:between| at )\b", stripped, re.I):
        return False
    if re.match(
        r"^(?:Rue|Straat|Street|Road|Avenue|Drive|Lane|Way|Place du|Place de|Boulevard|Blvd)\b",
        stripped,
        re.I,
    ):
        return False
    if re.search(r"\b(?:de L['\u2019]|du |des |d['\u2019])\s*(?:Église|Eglise)\b", stripped, re.I):
        return False
    return bool(
        re.search(
            r"(?:"
            r"\b(?:Church|Chapel|Cathedral|Basilica|Abbey|Kerk|kerk|Toren|Kirke|Domkirke|Dom)\b"
            r"|^(?:Église|Eglise|St\.|Sint-|Onze |Notre |Christ |Holy |First |Grace |Shrine )"
            r")",
            stripped,
            re.I,
        )
    )


def _strip_denomination_parenthetical(line: str) -> str:
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", line.strip())
    if not match:
        return line.strip()
    primary, inner = match.group(1).strip(), match.group(2).strip()
    if _is_denomination_label(inner):
        return primary
    return line.strip()


def _clean_denomination_markers(text: str) -> str:
    """Remove denomination tags such as (RC), · RC, or inline RC Church labels."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned

    cleaned = _strip_denomination_parenthetical(cleaned)

    if " · " in cleaned:
        parts = [_clean_denomination_markers(part) for part in cleaned.split(" · ")]
        parts = [part.strip() for part in parts if part.strip() and not _is_denomination_label(part)]
        cleaned = " · ".join(parts)

    cleaned = re.sub(r"\s+RC(?=\s+Church\b)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s+RC\s*$", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\s*\(\s*RC\s*\)", "", cleaned, flags=re.I)

    return re.sub(r"\s+", " ", cleaned).strip(" ,·")


def _parse_church_building_line(line: str) -> tuple[str | None, str | None]:
    """Return a church building line with denominations removed."""
    stripped = line.strip()
    if not stripped:
        return None, None

    parts = [part.strip() for part in re.split(r"\s*·\s*", stripped) if part.strip()]
    kept: list[str] = []
    for part in parts:
        cleaned = _strip_denomination_parenthetical(part)
        if _is_denomination_label(cleaned):
            continue
        if cleaned:
            kept.append(cleaned)

    if not kept:
        return None, None

    if len(kept) == 1:
        primary, translation, former = _extract_building_parenthetical(kept[0])
        if former:
            return primary, None
        if translation and _is_denomination_label(translation):
            return primary, None
        return primary, translation

    return _join_bilingual_parts(kept), None


def _promote_church_address_to_building(
    building: dict[str, str | None],
    address_lines: list[str],
) -> tuple[dict[str, str | None], list[str]]:
    if not address_lines or building.get("line"):
        return building, address_lines

    first = address_lines[0].strip()
    if not _looks_like_church_name(first):
        return building, address_lines

    parsed_name, parsed_translation = _parse_church_building_line(first)
    if not parsed_name:
        return building, address_lines

    updated = dict(building)
    updated["line"] = parsed_name
    if parsed_translation and not updated.get("translation"):
        updated["translation"] = parsed_translation
    return updated, address_lines[1:]


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


def _should_merge_address_line(previous: str, line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(","):
        return True
    previous_trimmed = previous.rstrip()
    if previous_trimmed.endswith(",") or re.search(r"\b(?:between|at|near|and|&)\s*$", previous_trimmed, re.I):
        return True
    if _ADDRESS_CONTINUATION_START_RE.match(stripped):
        return True
    if stripped[0].islower() and re.match(
        r"^(?:near|at|between|and|or|opposite|beside|adjacent to)\b",
        stripped,
        re.I,
    ):
        return True
    return False


def _merge_address_lines(address_lines: list[str]) -> list[str]:
    merged: list[str] = []
    for line in _combine_at_lines(address_lines):
        stripped = line.strip()
        if not stripped:
            continue
        if merged and _should_merge_address_line(merged[-1], stripped):
            previous = merged[-1].rstrip()
            continuation = stripped.lstrip(",").strip()
            if previous.endswith(",") or re.search(r"\b(?:between|at|near|and|&)\s*$", previous, re.I):
                merged[-1] = f"{previous} {continuation}"
            else:
                merged[-1] = f"{previous}, {continuation}"
        else:
            merged.append(stripped)
    return merged


def _is_address_like_text(text: str) -> bool:
    cleaned = text.strip().strip("()")
    if not cleaned:
        return False
    if _looks_like_address(cleaned):
        return True
    if re.search(r"\bbetween\b.+\b(?:and|&)\b", cleaned, re.I):
        return True
    if re.match(r"^(?:near|at|opposite|beside|adjacent to)\b", cleaned, re.I):
        return True
    return False


def _is_building_rename_text(text: str) -> bool:
    cleaned = re.sub(r"\s+", " ", text.strip().strip("()"))
    if not cleaned:
        return False
    return bool(_BUILDING_RENAME_RE.match(cleaned))


def _parse_former_name_fragment(text: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", text.strip().strip("()"))
    for pattern in (
        r"^was\s*:?\s*(.+)$",
        r"^formerly\s+(.+)$",
        r"^previously known as\s+(.+)$",
        r"^previously\s+(.+)$",
        r"^originally\s+(.+)$",
    ):
        match = re.match(pattern, cleaned, re.I)
        if match:
            return match.group(1).strip()
    return None


def _format_former_name_note(current_name: str | None, former_text: str) -> str:
    cleaned = re.sub(r"\s+", " ", former_text.strip().strip("()"))
    current = re.sub(r"\s+", " ", (current_name or "").strip())

    inline = re.match(
        r"^(.+?)\s*\((?:was|formerly)\s*:?\s*(.+?)\)\s*$",
        cleaned,
        re.I,
    )
    if inline:
        subject = inline.group(1).strip()
        former = inline.group(2).strip()
        return f"{subject} was known as {former}"

    if re.match(r"^formerly part of\b", cleaned, re.I):
        suffix = cleaned[0].lower() + cleaned[1:] if cleaned else cleaned
        return f"{current} was {suffix}" if current else cleaned

    former = _parse_former_name_fragment(cleaned) or cleaned
    if current:
        return f"{current} was known as {former}"
    return f"Was known as {former}"


def _normalize_former_name_notes(
    building: dict[str, str | None],
    notes: list[str],
) -> tuple[dict[str, str | None], list[str]]:
    building = dict(building)
    line = building.get("line")
    translation = building.get("translation")
    normalized_notes: list[str] = []

    if translation and _is_building_rename_text(translation):
        normalized_notes.append(_format_former_name_note(line, translation))
        building["translation"] = None
    elif translation:
        pass

    for note in notes:
        text = re.sub(r"\s+", " ", note.strip())
        if not text:
            continue
        if _is_building_rename_text(text) or re.search(r"\bpreviously known as\b", text, re.I):
            formatted = _format_former_name_note(line, text)
            if formatted not in normalized_notes:
                normalized_notes.append(formatted)
            continue
        if text not in normalized_notes:
            normalized_notes.append(text)

    return building, normalized_notes


def _is_locality_continuation_line(line: str) -> bool:
    """True when a trailing-comma line continues a split city/locality block."""
    stripped = line.strip()
    return bool(stripped.endswith(",") and not _looks_like_address(stripped.rstrip(",")))


def _merge_broken_locality_lines(lines: list[str]) -> list[str]:
    if not lines:
        return lines

    merged: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if (
            index + 1 < len(lines)
            and _is_locality_continuation_line(line)
            and _find_locality_index([lines[index + 1]]) is not None
        ):
            merged.append(f"{line.rstrip()} {lines[index + 1].strip()}")
            index += 2
            continue
        merged.append(line)
        index += 1

    result: list[str] = []
    index = 0
    while index < len(merged):
        if not _is_locality_continuation_line(merged[index]):
            result.append(merged[index])
            index += 1
            continue

        start = index
        while index < len(merged) and _is_locality_continuation_line(merged[index]):
            index += 1
        if index < len(merged) and _find_locality_index([merged[index]]) is not None:
            chunk = " ".join(part.strip() for part in merged[start : index + 1])
            result.append(chunk)
            index += 1
        else:
            result.extend(merged[start:index])
    return result


def _region_suffix_token(text: str) -> str | None:
    suffix = text.strip()
    if not suffix:
        return None
    suffix_upper = suffix.upper()
    if suffix_upper in _US_STATE_CODES or suffix_upper in _CA_PROVINCE_CODES:
        return suffix_upper
    suffix_lower = suffix.lower()
    if suffix_lower in _US_STATE_NAMES_LOWER:
        return _US_STATE_NAMES_LOWER[suffix_lower]
    if suffix_lower in _CA_PROVINCE_NAMES_LOWER:
        return _CA_PROVINCE_NAMES_LOWER[suffix_lower]
    return None


def _find_locality_index(lines: list[str]) -> int | None:
    for index in range(len(lines) - 1, -1, -1):
        line = lines[index]
        for token in sorted(COUNTRY_TOKENS, key=len, reverse=True):
            if re.search(rf",\s*{re.escape(token)}\s*$", line, re.I):
                return index
            if re.fullmatch(re.escape(token), line, re.I):
                return index
        if "," in line:
            parts = _split_on_commas_outside_parens(line.strip())
            if len(parts) >= 2 and _region_suffix_token(parts[-1]):
                return index
    return None


def _split_on_commas_outside_parens(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


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
        parts = _split_on_commas_outside_parens(text)
        if len(parts) >= 2:
            region_token = _region_suffix_token(parts[-1])
            if region_token:
                city = ", ".join(parts[:-1]).strip()
                return city or None, region_token, None
        return None, None, None

    parts = _split_on_commas_outside_parens(text)
    if not parts:
        return None, None, country_raw
    if len(parts) == 1:
        return parts[0], None, country_raw
    return parts[0], parts[-1], country_raw


def _parse_city_part(city: str) -> tuple[str, list[str]]:
    """Return primary city label and alternate names from parentheses or slashes."""
    text = city.strip().strip(")").strip()
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", text)
    if match:
        primary = match.group(1).strip()
        alts = [part.strip().strip(")").strip() for part in re.split(r"[,;/]", match.group(2)) if part.strip()]
        return primary, alts
    open_match = re.match(r"^(.+?)\s*\(([^)]+)$", text)
    if open_match:
        primary = open_match.group(1).strip()
        alts = [part.strip().strip(")").strip() for part in re.split(r"[,;/]", open_match.group(2)) if part.strip()]
        return primary, alts
    if " / " in text:
        parts = [part.strip() for part in text.split(" / ") if part.strip()]
        if parts:
            return parts[0], parts[1:]
    return text, []


def _is_english_text(text: str) -> bool:
    cleaned = text.strip().strip("()")
    if not cleaned:
        return False
    if _is_denomination_label(cleaned):
        return False
    if re.fullmatch(r"[A-Z]{2,6}", cleaned):
        return False
    if _ENGLISH_HINT_RE.search(cleaned):
        return True
    if cleaned.isascii() and len(cleaned.split()) >= 2:
        if not re.search(r"[àáâãäåæçèéêëìíîïñòóôõöùúûüý]", cleaned, re.I):
            return True
    return False


def _join_bilingual_parts(parts: list[str]) -> str:
    seen_keys: set[str] = set()
    kept: list[str] = []
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            continue
        key = _normalize_key(cleaned)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        kept.append(cleaned)
    return " · ".join(kept)


def _bilingual_line(primary: str, alternates: list[str]) -> str:
    if " / " in primary:
        return _join_bilingual_parts([part.strip() for part in primary.split(" / ") if part.strip()])
    parts = [primary.strip()]
    english = [alt for alt in alternates if _is_english_text(alt) and not _is_denomination_label(alt)]
    others = [alt for alt in alternates if not _is_english_text(alt) and not _is_denomination_label(alt)]
    for alt in english + others:
        if _normalize_key(alt) != _normalize_key(primary):
            parts.append(alt.strip())
    return _join_bilingual_parts(parts)


def _format_address_display(line: str) -> str:
    stripped = line.strip()
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", stripped)
    if match:
        primary, inner = match.group(1).strip(), match.group(2).strip()
        alts = [part.strip() for part in re.split(r"[,;/]", inner) if part.strip()]
        alts = [alt for alt in alts if not _is_denomination_label(alt)]
        if _is_denomination_label(inner):
            return _format_address_display(primary)
        if alts:
            return _bilingual_line(primary, alts)
    if " / " in stripped:
        return _join_bilingual_parts([part.strip() for part in stripped.split(" / ") if part.strip()])
    return stripped


def _normalize_building_part(text: str) -> str:
    cleaned = re.sub(r"\s*/\s*", ", ", text.strip())
    return re.sub(r"\s+", " ", cleaned)


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
    if len(right) > len(left) * 1.4:
        return False
    if len(left) >= 12 and left in right and len(left) / len(right) >= 0.65:
        return True
    if len(right) >= 12 and right in left and len(right) / len(left) >= 0.65:
        return True
    return False


def _is_institution_qualifier(line: str) -> bool:
    return (
        bool(re.match(r"^.+\([^)]+\)\s*$", line.strip()))
        and not _looks_like_address(line)
        and not FORMERLY_RE.search(line)
    )


def _is_university_line(line: str) -> bool:
    return bool(re.search(r"\b(?:University|College|Institute|Academy|Seminary)\b", line, re.I))


def _is_tower_line(line: str) -> bool:
    return bool(re.search(r"\b(?:Tower|toren|tour|Turm)\b", line, re.I))


def _looks_like_building_name(line: str) -> bool:
    if _looks_like_address(line):
        return False
    if _is_university_line(line):
        return False
    if FORMERLY_RE.search(line):
        return False
    if PAREN_ONLY_RE.match(line):
        return False
    return True


def _extract_building_parenthetical(
    line: str,
) -> tuple[str, str | None, str | None]:
    """Return primary line, English translation, or former-name fragment."""
    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", line.strip())
    if not match:
        return line.strip(), None, None
    primary, inner = match.group(1).strip(), match.group(2).strip()
    if _is_building_rename_text(inner):
        return primary, None, inner
    if _is_denomination_label(inner):
        return primary, None, None
    if _is_address_like_text(inner):
        return line.strip(), None, None
    if _is_english_text(inner):
        return primary, inner, None
    if primary and inner:
        return _join_bilingual_parts([primary, inner]), None, None
    return line.strip(), None, None


def _extract_building_translation(line: str) -> tuple[str, str | None]:
    primary, translation, _former = _extract_building_parenthetical(line)
    return primary, translation


def _format_city_region(
    city: str | None,
    city_alts: list[str],
    region_from_text: str | None,
    *,
    country_code: str,
    state_province: str,
) -> str | None:
    city_part = None
    if city or city_alts:
        city_part = _bilingual_line(city or "", city_alts)

    region = format_region(country_code, state_province or region_from_text or "")
    if not region and region_from_text:
        region = region_from_text.strip()

    if city_part and region and _normalize_key(region) not in _normalize_key(city_part):
        return f"{city_part}, {region}"
    return city_part or region or None


def _format_country_line(
    country_code: str,
    country_from_text: str | None = None,
) -> str | None:
    country = format_country(country_code)
    if country:
        return country
    return country_from_text or None


def _looks_like_address(line: str) -> bool:
    return bool(ADDRESS_HINT_RE.search(line))


def _looks_like_institution_context(line: str) -> bool:
    return bool(INSTITUTION_CONTEXT_RE.search(line))


def _stops_name_accumulation(line: str, *, after_name: bool) -> bool:
    if _looks_like_church_name(line):
        return False
    if after_name and _looks_like_institution_context(line):
        return True
    if ADDRESS_CORE_RE.search(line):
        return True
    if after_name and ADDRESS_CONTINUATION_RE.search(line):
        return True
    return False


def _is_city_preamble_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.endswith(",") and not _looks_like_address(stripped.rstrip(","))


def _format_badge(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", str(text).strip())
    if not cleaned:
        return None
    return format_display_text(cleaned)


def apply_location_display_case(result: dict[str, Any]) -> dict[str, Any]:
    """Apply display title case and saint spacing to rendered location fields."""
    display = dict(result)
    building = dict(display.get("building") or {})
    if building.get("line"):
        building["line"] = format_display_text(
            _clean_denomination_markers(str(building["line"]))
        )
    if building.get("translation"):
        building["translation"] = format_display_text(
            _clean_denomination_markers(str(building["translation"]))
        )
    display["building"] = building

    if display.get("badge"):
        display["badge"] = format_display_text(str(display["badge"]))
    if display.get("city_region"):
        display["city_region"] = format_display_text(str(display["city_region"]))
    if display.get("country"):
        display["country"] = format_display_text(str(display["country"]))
    display["address_lines"] = [
        format_display_text(_clean_denomination_markers(line))
        for line in display.get("address_lines") or []
        if _clean_denomination_markers(line)
    ]
    display["notes"] = [
        format_display_text(_clean_denomination_markers(note))
        for note in display.get("notes") or []
    ]
    return display


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


def _location_has_content(location: dict[str, Any]) -> bool:
    building = location.get("building") or {}
    return bool(
        building.get("line")
        or location.get("address_lines")
        or location.get("city_region")
        or location.get("country")
        or location.get("notes")
    )


def _empty_location_display(*, maps_url: str | None = None) -> dict[str, Any]:
    return {
        "badge": None,
        "building": {"line": None, "translation": None},
        "address_lines": [],
        "city_region": None,
        "country": None,
        "notes": [],
        "edge_case": None,
        "maps_url": maps_url,
        "has_content": False,
    }


def _migrate_legacy_override(override: dict[str, Any]) -> dict[str, Any]:
    migrated = dict(override)
    if "building" not in migrated and "name" in migrated:
        name = migrated.pop("name")
        hide = bool(migrated.pop("hide_name", False))
        aka = migrated.pop("also_known_as", None) or []
        translation = None
        if isinstance(aka, list):
            for item in aka:
                text = str(item).strip()
                if text and _is_english_text(text.strip("()")):
                    translation = text.strip("()")
                    break
        if hide:
            migrated["hide_building"] = True
        elif name:
            migrated["building"] = {
                "line": str(name).strip(),
                "translation": translation,
            }
    if "city_region" not in migrated and "locality" in migrated:
        locality = migrated.pop("locality")
        if locality:
            text = str(locality).strip()
            parts = _split_on_commas_outside_parens(text)
            if len(parts) >= 2:
                migrated["country"] = parts[-1]
                migrated["city_region"] = ", ".join(parts[:-1])
            else:
                migrated["city_region"] = text
    return migrated


def _override_value(override: dict[str, Any], key: str) -> Any | None:
    if key not in override:
        return None
    return override[key]


def _apply_override(
    result: dict[str, Any],
    override: dict[str, Any] | None,
    *,
    country_code: str = "",
    state_province: str = "",
) -> dict[str, Any]:
    if not override:
        return result

    override = _migrate_legacy_override(override)
    parsed_building = dict(result.get("building") or {"line": None, "translation": None})
    display: dict[str, Any] = {
        **result,
        "building": dict(parsed_building),
        "address_lines": list(result.get("address_lines") or []),
        "notes": list(result.get("notes") or []),
    }

    if override.get("hide_building"):
        display["building"] = {"line": None, "translation": None}
    elif "building" in override and isinstance(override["building"], dict):
        building = override["building"]
        if "line" in building:
            line = building.get("line")
            display["building"]["line"] = str(line).strip() if line else None
        if "translation" in building:
            translation = building.get("translation")
            display["building"]["translation"] = (
                str(translation).strip() if translation else None
            )

    if "badge" in override:
        badge = override["badge"]
        display["badge"] = _format_badge(str(badge).strip()) if badge else None

    for key in ("city_region", "country"):
        if key in override:
            value = override[key]
            display[key] = str(value).strip() if value else None

    for key in ("notes", "address_lines"):
        if key in override:
            value = override[key]
            if isinstance(value, list):
                display[key] = [str(item).strip() for item in value if str(item).strip()]
            else:
                display[key] = []

    if "hide_maps" in override:
        if override.get("hide_maps"):
            display["maps_url"] = None
        else:
            display["maps_url"] = result.get("maps_url")

    display["edge_case"] = result.get("edge_case")
    display["has_content"] = _location_has_content(display)
    return display


def _parse_building_block(
    content_lines: list[str],
    *,
    page_title: str,
) -> tuple[dict[str, str | None], list[str], list[str]]:
    """Return building, remaining lines, and notes."""
    lines = list(content_lines)
    notes: list[str] = []

    index = 0
    building_parts: list[str] = []
    building_translation: str | None = None

    while index < len(lines):
        line = lines[index]
        if FORMERLY_RE.search(line) or line.startswith("("):
            break
        if PAREN_ONLY_RE.match(line):
            break
        if _is_institution_qualifier(line) and _looks_like_church_name(line):
            parsed_name, parsed_translation = _parse_church_building_line(line)
            if parsed_name:
                building_parts.append(_normalize_building_part(parsed_name))
                if parsed_translation and not building_translation:
                    building_translation = parsed_translation
                index += 1
                continue
        if _is_institution_qualifier(line):
            break
        if building_parts and _stops_name_accumulation(line, after_name=True):
            break
        if not building_parts and _stops_name_accumulation(line, after_name=False):
            break

        if GENERIC_TOWER_RE.match(line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if _looks_like_building_name(next_line) and not _is_university_line(next_line):
                primary, translation, former = _extract_building_parenthetical(next_line)
                building_parts.append(
                    f"{_normalize_building_part(line)}, {_normalize_building_part(primary)}"
                )
                if translation and not building_translation:
                    building_translation = translation
                if former:
                    notes.append(_format_former_name_note(", ".join(building_parts), former))
                index += 2
                continue
            building_parts.append(_normalize_building_part(line))
            index += 1
            continue

        primary, translation, former = _extract_building_parenthetical(line)
        if former:
            building_parts.append(_normalize_building_part(primary))
            notes.append(_format_former_name_note(primary, former))
            index += 1
            continue
        if translation and not building_translation:
            building_translation = translation
            building_parts.append(_normalize_building_part(primary))
            index += 1
            continue

        if " / " in line and _looks_like_building_name(line):
            building_parts.append(_normalize_building_part(line))
            index += 1
            continue

        building_parts.append(_normalize_building_part(line))
        index += 1

    if (
        index < len(lines)
        and _is_university_line(lines[index])
        and building_parts
        and not any(_is_university_line(part) for part in building_parts)
    ):
        building_parts[-1] = f"{building_parts[-1]}, {lines[index].strip()}"
        index += 1
    elif (
        index < len(lines)
        and _is_institution_qualifier(lines[index])
        and building_parts
        and _is_university_line(lines[index])
    ):
        building_parts[-1] = f"{building_parts[-1]}, {lines[index].strip()}"
        index += 1

    remaining = lines[index:]
    building_line = ", ".join(building_parts) if building_parts else None

    if not building_line and not building_translation and not remaining:
        return {"line": None, "translation": None}, [], notes

    return (
        {"line": building_line, "translation": building_translation},
        remaining,
        notes,
    )


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
    city = None
    city_alts: list[str] = []
    region_from_text = None
    country_from_text = None
    if locality_index is not None:
        city, region_from_text, country_raw = _split_locality_line(lines[locality_index])
        country_code = _country_code_from_raw(country_raw, country_code)
        country_from_text = country_raw
        if city:
            city, city_alts = _parse_city_part(city)
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

    city_prefix: str | None = None
    while content_lines and _is_city_preamble_line(content_lines[-1]):
        prefix_line = content_lines.pop().rstrip().rstrip(",")
        city_prefix = f"{prefix_line}, {city_prefix}" if city_prefix else prefix_line
    if city_prefix:
        prefix_city, prefix_alts = _parse_city_part(city_prefix)
        if prefix_city:
            if not city:
                city = prefix_city
            elif _normalize_key(prefix_city) != _normalize_key(city):
                city_alts.append(prefix_city)
        for alt in prefix_alts:
            alt_key = _normalize_key(alt)
            if alt_key and alt_key not in {_normalize_key(city or ""), *(_normalize_key(a) for a in city_alts)}:
                city_alts.append(alt)

    building, remaining, notes = _parse_building_block(
        content_lines,
        page_title=page_title,
    )

    address_lines: list[str] = []
    index = 0
    while index < len(remaining):
        line = remaining[index]
        if PAREN_ONLY_RE.match(line):
            note = line.strip()
            if note.startswith("(") and note.endswith(")"):
                note = note[1:-1].strip()
            if note and _is_denomination_label(note):
                index += 1
                continue
            if note and _is_building_rename_text(note) and building.get("line"):
                notes.append(_format_former_name_note(building.get("line"), note))
            elif note and _is_address_like_text(note):
                address_lines.append(note.strip("()"))
            elif (
                note
                and _is_english_text(note)
                and not _is_address_footnote(note)
                and building.get("line")
                and not building.get("translation")
            ):
                building = dict(building)
                building["translation"] = note
            elif note and not _is_duplicate_of_title(note, page_title):
                notes.append(note)
            index += 1
            continue
        if FORMERLY_RE.search(line) or (line.startswith("(") and not PAREN_ONLY_RE.match(line)):
            note, index = _merge_note_lines(remaining, index)
            if note:
                if _is_building_rename_text(note) or re.search(r"\bpreviously known as\b", note, re.I):
                    notes.append(_format_former_name_note(building.get("line"), note))
                else:
                    notes.append(note)
            continue
        if _is_institution_qualifier(line) and _is_university_line(line):
            if building.get("line"):
                building = dict(building)
                building["line"] = f"{building['line']}, {line.strip()}"
            index += 1
            continue
        if _is_duplicate_of_title(line, page_title):
            index += 1
            continue
        address_lines.append(line)
        index += 1

    address_lines = [_format_address_display(line) for line in _merge_address_lines(address_lines)]

    building, notes = _normalize_former_name_notes(building, notes)

    building, address_lines = _promote_church_address_to_building(building, address_lines)

    latitude = site.get("latitude")
    longitude = site.get("longitude")
    if (
        latitude is not None
        and longitude is not None
        and not city
        and not state_province
        and not country_code
    ):
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

    city_region = _format_city_region(
        city,
        city_alts,
        region_from_text,
        country_code=country_code,
        state_province=state_province,
    )
    country = _format_country_line(country_code, country_from_text)

    result = {
        "badge": badge,
        "building": building,
        "address_lines": address_lines,
        "city_region": city_region,
        "country": country,
        "notes": notes,
        "edge_case": None,
        "maps_url": _maps_url(latitude, longitude),
        "has_content": False,
    }
    result["has_content"] = _location_has_content(result)

    return apply_location_display_case(
        _apply_override(
            result,
            override,
            country_code=country_code,
            state_province=state_province,
        )
    )
