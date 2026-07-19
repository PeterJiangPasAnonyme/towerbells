"""Resolve carillonist / chimer / player sections from towerbells.org pages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from scraper.text import decode_html_text

CURRENT_SECTION_KEYS = (
    "Carillonist",
    "Player",
)

PAST_SECTION_KEYS = (
    "Past carillonists",
    "Past carillonist",
    "Previous carillonists",
    "Previous carillonist",
    "Past chimer",
    "Past chimers",
    "Past chimers & carillonists",
)

DEFAULT_CURRENT_TITLE = "Carillonist"
DEFAULT_PAST_TITLE = "Past carillonists"


@dataclass(frozen=True)
class ResolvedPersonSections:
    current_text: str = ""
    current_label: str | None = None
    past_text: str = ""
    past_label: str | None = None


def _normalize_section_key(key: str) -> str:
    text = decode_html_text(key or "")
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _sections_from_site(site: dict[str, Any]) -> dict[str, str]:
    raw = site.get("sections_json")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def uses_chime_person_titles(
    instrument_type: str | None,
    *,
    technical_data: str | None = None,
) -> bool:
    """True when the site should keep chime-style person section headings."""
    for source in (instrument_type, _technical_opening_line(technical_data)):
        if not source:
            continue
        lowered = source.strip().lower()
        if "carillon" in lowered:
            return False
        if re.search(r"\bchime\b", lowered):
            return True
    return False


def _technical_opening_line(technical_data: str | None) -> str | None:
    if not technical_data:
        return None
    for line in technical_data.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return None


def _find_section(
    sections: dict[str, str],
    candidates: tuple[str, ...],
) -> tuple[str, str] | None:
    if not sections:
        return None

    by_normalized = {_normalize_section_key(key): (key, value) for key, value in sections.items()}

    for candidate in candidates:
        match = by_normalized.get(_normalize_section_key(candidate))
        if match and match[1].strip():
            return match[0], match[1].strip()

    for normalized, (original, value) in by_normalized.items():
        if not value.strip():
            continue
        if "past chimers" in normalized and "carillonist" in normalized:
            return original, value.strip()

    return None


def resolve_person_sections(
    sections: dict[str, str],
    *,
    instrument_type: str | None = None,
    technical_data: str | None = None,
    stored_current: str | None = None,
    stored_past: str | None = None,
) -> ResolvedPersonSections:
    current_match = _find_section(sections, CURRENT_SECTION_KEYS)
    past_match = _find_section(sections, PAST_SECTION_KEYS)

    current_text = (stored_current or "").strip()
    if not current_text and current_match:
        current_text = current_match[1]

    past_text = (stored_past or "").strip()
    if not past_text and past_match:
        past_text = past_match[1]

    current_label = current_match[0] if current_match and current_text == current_match[1] else None
    if current_text and not current_label:
        if current_match and current_text == current_match[1]:
            current_label = current_match[0]
        elif _find_section(sections, ("Carillonist",)):
            current_label = "Carillonist"
        elif _find_section(sections, ("Player",)):
            current_label = "Player"

    past_label = past_match[0] if past_match and past_text == past_match[1] else None
    if past_text and not past_label:
        if past_match and past_text == past_match[1]:
            past_label = past_match[0]
        elif _find_section(sections, ("Past carillonists",)):
            past_label = "Past carillonists"

    return ResolvedPersonSections(
        current_text=current_text,
        current_label=current_label,
        past_text=past_text,
        past_label=past_label,
    )


def resolve_person_sections_for_site(site: dict[str, Any]) -> ResolvedPersonSections:
    sections = _sections_from_site(site)
    return resolve_person_sections(
        sections,
        instrument_type=site.get("instrument_type"),
        technical_data=site.get("technical_data"),
        stored_current=site.get("carillonist"),
        stored_past=site.get("past_carillonists"),
    )


def person_section_display_title(
    source_label: str | None,
    *,
    role: str,
    instrument_type: str | None = None,
    technical_data: str | None = None,
) -> str:
    if source_label and uses_chime_person_titles(instrument_type, technical_data=technical_data):
        return source_label
    return DEFAULT_CURRENT_TITLE if role == "current" else DEFAULT_PAST_TITLE
