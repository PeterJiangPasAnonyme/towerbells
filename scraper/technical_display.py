"""Structured technical data display for site detail pages."""

from __future__ import annotations

import json
import re
from typing import Any

from scraper.config import RAW_HTML_DIR
from scraper.extra_bells_display import parse_extra_bell_items
from scraper.instrument_types import normalize_instrument_type
from scraper.parse_site import SECTION_RE
from scraper.technical_sections import split_technical_sections
from scraper.text import decode_html_text, normalize_remarks_reference, reflow_wrapped_prose

_LINE = r"(?m)^\s*"

RECENT_WORK_START = re.compile(
    _LINE
    + r"(The instrument was enlarged|The bells were re-tuned|The instrument was re-tuned|"
    r"The whole instrument was installed|The complete instrument was)",
    re.I,
)

PRACTICE_CONSOLE_LABELS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"identical practice console", re.I), "Identical practice console"),
    (re.compile(r"non-identical practice console", re.I), "Non-identical practice console"),
    (re.compile(_LINE + r"There is a practice console\s*$", re.I), "Practice console"),
    (re.compile(_LINE + r"There is no practice console\s*$", re.I), "No practice console"),
    (re.compile(r"presence or absence of a practice console is unknown", re.I), None),
    (re.compile(_LINE + r"The practice console is (\w+)", re.I), None),
]

ARRANGEMENT_UNKNOWN = re.compile(r"arrangement of tones and semitones is unknown", re.I)
ARRANGEMENT_NONSTANDARD = re.compile(r"arrangement of tones and/or semitones", re.I)

AUXILIARY_LINE = re.compile(_LINE + r"Auxiliary mechanisms:\s*(.+?)\s*$", re.I)
NO_AUXILIARY = re.compile(_LINE + r"No auxiliary mechanisms known\s*$", re.I)

TECH_YEAR = re.compile(
    _LINE + r"Year of latest technical information source is (.+?)\s*$",
    re.I,
)

TOWER_METRICS = {
    "console_height": re.compile(_LINE + r"Height of console:\s*(.+?)\s*$", re.I),
    "lowest_bells": re.compile(_LINE + r"Height of lowest level of bells:\s*(.+?)\s*$", re.I),
    "highest_bells": re.compile(_LINE + r"Height of highest level of bells:\s*(.+?)\s*$", re.I),
    "belfry_openness": re.compile(_LINE + r"Belfry openness:\s*(.+?)\s*$", re.I),
}

TOWER_NOT_AVAILABLE = re.compile(_LINE + r"Tower details not available\s*$", re.I)

NA_DISPLAY = "N/A"
_UNKNOWN_LIKE_VALUES = frozenset(
    {
        "unknown",
        "not applicable",
        "not available",
        "n/a",
        "na",
    }
)


def is_unknown_like_value(value: str | None) -> bool:
    if not value or not str(value).strip():
        return False
    normalized = re.sub(r"^\(|\)$", "", str(value).strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized in _UNKNOWN_LIKE_VALUES


def format_exception_field_value(value: str) -> str:
    if is_unknown_like_value(value):
        return NA_DISPLAY
    return value


def omit_unknown_like_value(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    text = str(value).strip()
    if is_unknown_like_value(text):
        return None
    return text


def extract_recent_work(preamble: str) -> str:
    if not preamble:
        return ""
    match = RECENT_WORK_START.search(preamble)
    if not match:
        return ""
    return preamble[match.start() :].strip()


def preamble_without_recent_work(preamble: str) -> str:
    if not preamble:
        return ""
    match = RECENT_WORK_START.search(preamble)
    if not match:
        return preamble.strip()
    return preamble[: match.start()].strip()


def combine_prior_history_display(site: dict) -> str:
    raw = site.get("technical_data") or ""
    preamble, prior_history, _ = split_technical_sections(raw)
    recent = extract_recent_work(preamble)
    parts = [part for part in (recent, prior_history.strip()) if part]
    stored = (site.get("prior_history") or "").strip()
    if not parts and stored:
        return normalize_remarks_reference(stored)
    return normalize_remarks_reference("\n\n".join(parts))


def format_transposition_display(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    text = str(raw).strip()
    lowered = text.lower()
    if is_unknown_like_value(text):
        return NA_DISPLAY
    if "nil" in lowered or "concert pitch" in lowered:
        return "Concert pitch"
    if lowered.startswith("up ") or lowered.startswith("down "):
        direction, rest = text.split(" ", 1)
        return f"{direction.capitalize()} {rest}"
    return text[0].upper() + text[1:] if text else text


def format_missing_bass_display(raw: str | None) -> str | None:
    if not raw or not str(raw).strip():
        return None
    if is_unknown_like_value(raw):
        return NA_DISPLAY
    lowered = str(raw).lower()
    if "two missing" in lowered:
        return "2"
    if "one missing" in lowered:
        return "1"
    if "three missing" in lowered:
        return "3"
    if "no missing" in lowered:
        return "0"
    return str(raw).strip()


def parse_practice_console(preamble: str, stored: str | None) -> str | None:
    text = preamble or ""
    for pattern, label in PRACTICE_CONSOLE_LABELS:
        match = pattern.search(text)
        if match:
            if label is None and "unknown" in pattern.pattern.lower():
                return None
            if label:
                return omit_unknown_like_value(label)
            value = match.group(1).strip()
            return omit_unknown_like_value(value.capitalize() if value else "")
    if stored and str(stored).strip():
        return omit_unknown_like_value(str(stored).strip().capitalize())
    return None


def parse_arrangement_note(preamble: str) -> str | None:
    if not preamble:
        return None
    if ARRANGEMENT_UNKNOWN.search(preamble):
        return None
    if ARRANGEMENT_NONSTANDARD.search(preamble):
        if re.search(r"non-standard", preamble, re.I):
            return "Non-standard (see Remarks)"
        return "Non-standard"
    return None


def parse_auxiliary_mechanisms(
    footer: str | None,
    preamble: str | None,
    stored: str | None,
) -> str | None:
    for text in (footer, preamble):
        if text and NO_AUXILIARY.search(text):
            return "None known"

    if footer:
        match = AUXILIARY_LINE.search(footer)
        if match:
            value = match.group(1).strip()
            if value:
                return value

    if stored:
        value = str(stored).strip()
        if value and len(value) <= 24 and "\n" not in value:
            return value

    return None


def parse_tech_info_year(footer: str | None, site_year: int | str | None = None) -> str | None:
    if footer:
        match = TECH_YEAR.search(footer)
        if match:
            return match.group(1).strip()
    if site_year not in (None, ""):
        return str(site_year)
    return None


def parse_tower_details_block(text: str | None) -> dict[str, Any]:
    if not text or not str(text).strip():
        return {}

    body = str(text).strip()
    if TOWER_NOT_AVAILABLE.search(body):
        return {}

    metrics: dict[str, str] = {}
    labels = {
        "console_height": "Height of console",
        "lowest_bells": "Height of lowest level of bells",
        "highest_bells": "Height of highest level of bells",
        "belfry_openness": "Belfry openness",
    }
    for key, pattern in TOWER_METRICS.items():
        match = pattern.search(body)
        if match:
            value = match.group(1).strip()
            if not is_unknown_like_value(value):
                metrics[labels[key]] = value

    if metrics:
        return {"metrics": metrics}

    cleaned = re.sub(_LINE + r"Tower details:\s*", "", body, count=1, flags=re.I).strip()
    if cleaned and not TECH_YEAR.search(cleaned) and not AUXILIARY_LINE.search(cleaned):
        first_line = cleaned.splitlines()[0].strip()
        if is_unknown_like_value(first_line):
            return {}
        if first_line:
            return {"summary": first_line}

    return {}


def _instrument_type_label(site: dict, preamble: str) -> str | None:
    stored = site.get("instrument_type")
    if stored and str(stored).strip():
        normalized = normalize_instrument_type(stored)
        return normalized or str(stored).strip()
    first = preamble.splitlines()[0].strip() if preamble else ""
    match = re.match(
        r"^((?:Traditional|Concert class|Non-traditional|Hybrid|Travelling|Electric(?:-\w+)?)"
        r"(?: carillon| chime(?: \([^)]+\))?| chime)?|Chime(?:-sized instrument)?|Ring|Peal|Bell tower)"
        r"(?: of \d+ bells)?",
        first,
        re.I,
    )
    if match:
        return match.group(1).strip()
    match = re.match(r"^(.+?) of \d+ bells", first, re.I)
    return match.group(1).strip() if match else (first or None)


def _parse_heaviest(spec_preamble: str, stored: str | None) -> tuple[str, str] | None:
    heaviest = (stored or "").strip()
    heaviest_label = "Heaviest bell"
    match = re.search(
        _LINE + r"Pitch of heaviest bell(?: \(excluding sub-bourdon\))? is (.+?)\s*$",
        spec_preamble,
        re.I,
    )
    if match:
        parsed = match.group(1).strip()
        if not heaviest or "octave" in parsed.lower() or len(parsed) > len(heaviest):
            heaviest = parsed
        if re.search(r"excluding sub-bourdon", match.group(0), re.I):
            heaviest_label = "Heaviest bell (excluding sub-bourdon)"
    if heaviest:
        return heaviest_label, heaviest
    return None


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


def _extract_access_raw_html(page_html: str) -> str:
    for match in SECTION_RE.finditer(page_html):
        if match.group(1).strip().lower() == "access":
            return match.group(2)
    return ""


def parse_access_text(site: dict[str, Any]) -> str | None:
    raw = ""
    sections_json = site.get("sections_json")
    if sections_json:
        try:
            sections = json.loads(sections_json)
        except json.JSONDecodeError:
            sections = {}
        if isinstance(sections, dict):
            raw = str(sections.get("Access") or "").strip()

    if not raw:
        page_html = _load_page_html(site)
        if page_html:
            raw = decode_html_text(_extract_access_raw_html(page_html)).strip()

    if not raw:
        return None

    text = normalize_remarks_reference(reflow_wrapped_prose(raw))
    return omit_unknown_like_value(text)


def build_technical_display(
    site: dict,
    *,
    keyboard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = site.get("technical_data") or ""
    preamble, _, footer = split_technical_sections(raw)
    spec_preamble = preamble_without_recent_work(preamble)

    keyboard = keyboard or {}
    show_diagram = bool(
        keyboard.get("has_content") and not keyboard.get("hide_diagram")
    )
    show_keyboard_fields = not show_diagram

    items: list[dict[str, Any]] = []

    instrument = omit_unknown_like_value(_instrument_type_label(site, preamble))
    if instrument:
        items.append({"label": "Instrument type", "value": instrument})

    bell_count = site.get("bell_count")
    if bell_count is not None:
        items.append({"label": "Number of bells", "value": str(bell_count)})

    insert_at = len(items)
    for extra_item in parse_extra_bell_items(site):
        items.insert(insert_at, extra_item)
        insert_at += 1

    heaviest = _parse_heaviest(spec_preamble, site.get("heaviest_pitch"))
    if heaviest:
        label, value = heaviest
        if not show_diagram or "itty-bitty" in value.lower():
            items.append({"label": label, "value": format_exception_field_value(value)})

    if show_keyboard_fields:
        keyboard_range = (site.get("keyboard_range") or "").strip()
        if not keyboard_range:
            match = re.search(_LINE + r"Keyboard range:\s*(.+?)\s*$", spec_preamble, re.I)
            if match:
                keyboard_range = match.group(1).strip()
        if keyboard_range:
            items.append(
                {
                    "label": "Keyboard range",
                    "value": format_exception_field_value(keyboard_range),
                }
            )

        transposition = format_transposition_display(site.get("transposition"))
        if not transposition:
            match = re.search(_LINE + r"Transposition is (.+?)\s*$", spec_preamble, re.I)
            if match:
                transposition = format_transposition_display(match.group(1))
        if transposition:
            items.append({"label": "Transposition", "value": transposition})

        missing_bass = format_missing_bass_display(site.get("missing_bass_semitone"))
        if missing_bass is None:
            match = re.search(
                _LINE
                + r"(There are two missing bass semitones|There is one missing bass semitone|"
                r"No missing bass semitone|There are no missing bass semitones|"
                r"There are three missing bass semitones)\s*$",
                spec_preamble,
                re.I,
            )
            if match:
                missing_bass = format_missing_bass_display(match.group(1))
        if missing_bass is not None:
            items.append({"label": "Missing bass semitones", "value": missing_bass})

    practice = parse_practice_console(spec_preamble, site.get("practice_console"))
    if practice:
        items.append({"label": "Practice console", "value": practice})

    arrangement = omit_unknown_like_value(parse_arrangement_note(spec_preamble))
    if arrangement:
        items.append({"label": "Keyboard arrangement", "value": arrangement})

    auxiliary = omit_unknown_like_value(
        parse_auxiliary_mechanisms(footer, spec_preamble, site.get("auxiliary_mechanisms"))
    )
    if auxiliary:
        items.append({"label": "Auxiliary mechanisms", "value": auxiliary})

    tower = parse_tower_details_block(footer)
    if not tower:
        stored_tower = site.get("tower_details")
        if stored_tower and len(str(stored_tower)) <= 40:
            tower = parse_tower_details_block(str(stored_tower))
    if tower.get("metrics"):
        items.append(
            {
                "label": "Tower details",
                "subitems": [{"label": k, "value": v} for k, v in tower["metrics"].items()],
            }
        )
    elif tower.get("summary") and not is_unknown_like_value(tower["summary"]):
        items.append({"label": "Tower details", "value": tower["summary"]})

    access = parse_access_text(site)
    if access:
        items.append({"label": "Access", "value": access})

    tech_year = parse_tech_info_year(footer, site.get("tech_info_year"))

    has_content = bool(items) or show_diagram or bool(keyboard.get("prose"))

    return {
        "has_content": has_content,
        "show_diagram": show_diagram,
        "show_keyboard_fields": show_keyboard_fields,
        "items": items,
        "tech_info_year": tech_year,
    }
