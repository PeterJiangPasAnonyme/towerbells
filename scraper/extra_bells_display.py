"""Parse Bourdon / bass / swinging bell sections for technical display."""

from __future__ import annotations

import re
from typing import Any

from scraper.bellfounders import canonical_founder_name
from scraper.config import RAW_HTML_DIR
from scraper.parse_site import SECTION_RE
from scraper.text import clean_html_fragment, decode_html_text

EXTRA_BELL_SECTIONS: list[tuple[str, str]] = [
    ("Bourdon", "Bourdon"),
    ("Bass bell", "Bass bell"),
    ("Bass bells", "Bass bells"),
    ("Basses", "Basses"),
    ("Bells that swing", "Swinging bells"),
]

UNKNOWN_VALUES = frozenset({"?", "??", "???"})
YEAR_RE = re.compile(r"^(\d{4})\??$")
DIAMETER_RE = re.compile(r"^(\d+)\s*cm$", re.I)
WEIGHT_KG_RE = re.compile(r"^(\d+)\s*kg$", re.I)
WEIGHT_LB_HASH_RE = re.compile(r"^(\d+)#$")
WEIGHT_CWT_RE = re.compile(r"^(\d+)-(\d+)-(\d+)$")
PITCH_RE = re.compile(r"^(?:was\s+)?~?(?:[A-Ga-g](?:#|b)?\d*)$", re.I)
QUOTED_NAME_RE = re.compile(r'^"([^"]+)"')


def _load_page_html(site: dict[str, Any]) -> str:
    filename = (site.get("page_filename") or f"{site.get('site_id', '')}.HTM").strip()
    if not filename:
        return ""
    path = RAW_HTML_DIR / filename.lower()
    if not path.is_file():
        alt = RAW_HTML_DIR / f"{site.get('site_id', '').lower()}.htm"
        path = alt if alt.is_file() else path
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _extract_section_html(page_html: str, section_name: str) -> str:
    target = section_name.strip().lower()
    for match in SECTION_RE.finditer(page_html):
        if match.group(1).strip().lower() == target:
            return match.group(2)
    return ""


def _section_plain_text(raw_html: str) -> str:
    text = re.sub(r"(?i)<br\s*/?>", "\n", raw_html)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = decode_html_text(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _is_unknown(value: str) -> bool:
    cleaned = value.strip().strip('"').rstrip("?")
    if not cleaned:
        return True
    if cleaned in UNKNOWN_VALUES:
        return True
    if re.fullmatch(r"\?+cm", cleaned, re.I):
        return True
    if re.fullmatch(r"\?+kg", cleaned, re.I):
        return True
    if cleaned.lower() == "unknown":
        return True
    return False


def _split_commas(text: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    for char in text:
        if char == '"':
            in_quote = not in_quote
            current.append(char)
        elif char == "," and not in_quote:
            piece = "".join(current).strip()
            if piece:
                parts.append(piece)
            current = []
        else:
            current.append(char)
    piece = "".join(current).strip()
    if piece:
        parts.append(piece)
    return parts


def _leading_token(line: str) -> str:
    if line.startswith('"'):
        match = QUOTED_NAME_RE.match(line)
        if match:
            return match.group(0)
    return line.split(",", 1)[0].strip()


def _starts_new_bell(line: str) -> bool:
    if line.startswith('"'):
        return True
    token = _leading_token(line)
    if token.lower().startswith("was "):
        token = token[4:].strip()
    return PITCH_RE.match(token) is not None


def _split_bell_records(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    records: list[str] = []
    buffer = ""
    for line in lines:
        if buffer and _starts_new_bell(line):
            records.append(buffer)
            buffer = line
        else:
            buffer = f"{buffer} {line}".strip() if buffer else line
    if buffer:
        records.append(buffer)
    return records


def _format_cwt_weight(value: str) -> str:
    match = WEIGHT_CWT_RE.match(value)
    if not match:
        return value
    hundred, quarters, pounds = match.groups()
    return f"{hundred} cwt {quarters} qr {pounds} lb"


def _format_weight(value: str) -> str | None:
    cleaned = value.strip()
    if _is_unknown(cleaned):
        return None
    match = WEIGHT_KG_RE.match(cleaned)
    if match:
        return f"{match.group(1)} kg"
    match = WEIGHT_LB_HASH_RE.match(cleaned)
    if match:
        return f"{match.group(1)} lb"
    if WEIGHT_CWT_RE.match(cleaned):
        return _format_cwt_weight(cleaned)
    return None


def _format_diameter(value: str) -> str | None:
    cleaned = value.strip()
    if _is_unknown(cleaned):
        return None
    match = DIAMETER_RE.match(cleaned.replace(" ", ""))
    if match:
        return f"{match.group(1)} cm"
    return None


def _format_pitch(value: str) -> str | None:
    cleaned = value.strip()
    if cleaned.lower().startswith("was "):
        cleaned = cleaned[4:].strip()
    if _is_unknown(cleaned):
        return None
    if PITCH_RE.match(cleaned):
        return cleaned
    return None


def _format_year(value: str) -> str | None:
    cleaned = value.strip()
    if _is_unknown(cleaned):
        return None
    match = YEAR_RE.match(cleaned)
    if match:
        return match.group(1)
    return None


def _format_founder(value: str) -> str | None:
    cleaned = value.strip()
    if _is_unknown(cleaned):
        return None
    if re.fullmatch(r"\?", cleaned):
        return None
    if re.search(r"[A-Za-z]", cleaned):
        return canonical_founder_name(cleaned) or None
    return None


def _classify_part(part: str) -> tuple[str, str] | None:
    cleaned = part.strip()
    if _is_unknown(cleaned):
        return None

    for formatter, label, pattern in (
        (_format_year, "Year cast", YEAR_RE),
        (_format_diameter, "Diameter", DIAMETER_RE),
        (_format_weight, "Weight", None),
        (_format_pitch, "Pitch", PITCH_RE),
        (_format_founder, "Bellfounder", None),
    ):
        if label == "Weight":
            value = formatter(cleaned)
            if value and (
                WEIGHT_KG_RE.match(cleaned)
                or WEIGHT_LB_HASH_RE.match(cleaned)
                or WEIGHT_CWT_RE.match(cleaned)
            ):
                return (label, value)
            continue
        if label == "Bellfounder":
            value = formatter(cleaned)
            if value:
                return (label, value)
            continue
        if label == "Diameter":
            value = formatter(cleaned)
            if value and pattern.match(cleaned.replace(" ", "")):
                return (label, value)
            continue
        if label == "Pitch":
            pitch_input = cleaned[4:].strip() if cleaned.lower().startswith("was ") else cleaned
            value = formatter(cleaned)
            if value and pattern.match(pitch_input):
                return (label, value)
            continue
        if pattern and pattern.match(cleaned):
            value = formatter(cleaned)
            if value:
                return (label, value)
    return None


def _parse_bell_record(record: str) -> dict[str, str]:
    record = clean_html_fragment(record)
    name_match = QUOTED_NAME_RE.match(record)
    name = ""
    remainder = record
    if name_match:
        name = name_match.group(1).strip()
        remainder = record[name_match.end() :].lstrip(" ,")

    fields: dict[str, str] = {}
    if name and not _is_unknown(name):
        fields["Name"] = name

    assigned: set[str] = set()
    for part in _split_commas(remainder):
        classified = _classify_part(part)
        if not classified:
            continue
        label, value = classified
        if label in assigned:
            continue
        fields[label] = value
        assigned.add(label)
    return fields


def _fields_to_subitems(fields: dict[str, str]) -> list[dict[str, str]]:
    order = ["Pitch", "Weight", "Diameter", "Year cast", "Bellfounder"]
    subitems: list[dict[str, str]] = []
    for label in order:
        value = fields.get(label)
        if value and not _is_unknown(value):
            subitems.append({"label": label, "value": value})
    return subitems


def _parse_section_item(section_name: str, display_label: str, raw_html: str) -> dict[str, Any] | None:
    text = _section_plain_text(raw_html)
    if not text:
        return None

    records = _split_bell_records(text)
    bell_groups: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        fields = _parse_bell_record(record)
        subitems = _fields_to_subitems(fields)
        if not subitems:
            continue
        name = fields.get("Name")
        if name and not _is_unknown(name):
            bell_groups.append({"label": name, "subitems": subitems})
        elif len(records) == 1:
            return {"label": display_label, "subitems": subitems}
        else:
            pitch = fields.get("Pitch")
            group_label = pitch if pitch and not _is_unknown(pitch) else f"Bell {index}"
            bell_groups.append({"label": group_label, "subitems": subitems})

    if not bell_groups:
        return None
    return {"label": display_label, "subitems": bell_groups}


def parse_extra_bell_items(site: dict[str, Any]) -> list[dict[str, Any]]:
    page_html = _load_page_html(site)
    if not page_html:
        return []

    items: list[dict[str, Any]] = []
    for section_name, display_label in EXTRA_BELL_SECTIONS:
        raw_html = _extract_section_html(page_html, section_name)
        if not raw_html:
            continue
        item = _parse_section_item(section_name, display_label, raw_html)
        if item:
            items.append(item)
    return items
