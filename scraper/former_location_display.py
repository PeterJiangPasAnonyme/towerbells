"""Former location sections rendered as a prior-history-style timeline."""

from __future__ import annotations

import json
import re
from typing import Any

from scraper.text import decode_html_text, normalize_remarks_reference

FORMER_LOCATION_SECTION_RE = re.compile(r"^former\s+locations?\b", re.I)
SECTION_PERIOD_RE = re.compile(r"\(([^)]+)\)\s*$")
ENTRY_PERIOD_LINE_RE = re.compile(r"^\s*(?:\(([^)]+)\)|(.+?))\s*:\s*$")
PERIOD_SORT_YEAR_RE = re.compile(r"(\d{4})")
PERIOD_SORT_SHORT_YEAR_RE = re.compile(r"^\s*(\d{2})\s*[-–—]")


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


def _former_location_sections(sections: dict[str, str]) -> list[tuple[str, str]]:
    matches: list[tuple[str, str]] = []
    for key, value in sections.items():
        label = decode_html_text(key).strip()
        if not FORMER_LOCATION_SECTION_RE.match(label):
            continue
        text = normalize_remarks_reference(decode_html_text(value)).strip()
        if text:
            matches.append((label, text))
    return matches


def _period_from_section_key(section_key: str) -> str | None:
    match = SECTION_PERIOD_RE.search(section_key.strip())
    if not match:
        return None
    period = match.group(1).strip()
    return period or None


def _is_entry_period_line(line: str) -> bool:
    match = ENTRY_PERIOD_LINE_RE.match(line)
    if not match:
        return False
    period = (match.group(1) or match.group(2) or "").strip()
    return bool(re.search(r"\d|\?", period))


def _period_from_entry_line(line: str) -> str:
    match = ENTRY_PERIOD_LINE_RE.match(line)
    if not match:
        return line.strip()
    return (match.group(1) or match.group(2) or "").strip()


def _period_sort_key(period: str | None) -> tuple[int, str]:
    text = (period or "").strip()
    if not text:
        return (0, "")

    match = PERIOD_SORT_YEAR_RE.search(text)
    if match:
        return (int(match.group(1)), text)

    match = PERIOD_SORT_SHORT_YEAR_RE.match(text)
    if match:
        short = int(match.group(1))
        return (1900 + short if short >= 30 else 2000 + short, text)

    return (0, text)


def _split_body_into_blocks(body: str, default_period: str | None) -> list[tuple[str | None, list[str]]]:
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if not lines:
        return []

    if not any(_is_entry_period_line(line) for line in lines):
        return [(default_period, lines)]

    blocks: list[tuple[str | None, list[str]]] = []
    current_period: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if _is_entry_period_line(line):
            if current_lines or current_period is not None:
                blocks.append((current_period or default_period, current_lines))
            current_period = _period_from_entry_line(line)
            current_lines = []
            continue
        current_lines.append(line)

    if current_lines or current_period is not None:
        blocks.append((current_period or default_period, current_lines))

    return blocks


def _block_to_event(period: str | None, lines: list[str]) -> dict[str, Any] | None:
    cleaned_lines = [normalize_remarks_reference(line).strip() for line in lines if line.strip()]
    cleaned_lines = [line for line in cleaned_lines if line]
    if not period and not cleaned_lines:
        return None

    headline = cleaned_lines[0] if cleaned_lines else (period or "")
    bullets = cleaned_lines[1:] if len(cleaned_lines) > 1 else []

    display_period = period or "—"
    return {
        "year": display_period,
        "headline": headline,
        "bullets": bullets,
        "_sort_key": _period_sort_key(period),
    }


def _events_from_section(section_key: str, body: str) -> list[dict[str, Any]]:
    default_period = _period_from_section_key(section_key)
    events: list[dict[str, Any]] = []
    for period, lines in _split_body_into_blocks(body, default_period):
        event = _block_to_event(period, lines)
        if event:
            events.append(event)
    return events


def build_former_location_display(site: dict[str, Any]) -> dict[str, Any]:
    sections = _sections_from_site(site)
    events: list[dict[str, Any]] = []

    for section_key, body in _former_location_sections(sections):
        events.extend(_events_from_section(section_key, body))

    events.sort(key=lambda item: item["_sort_key"], reverse=True)
    public_events = [
        {
            "year": event["year"],
            "headline": event["headline"],
            "bullets": event.get("bullets") or [],
        }
        for event in events
    ]

    return {
        "has_content": bool(public_events),
        "events": public_events,
    }
