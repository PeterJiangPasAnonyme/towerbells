"""Parse and classify carillon history events from towerbells.org list suffixes."""

from __future__ import annotations

import json
import re
from typing import Any

EVENT_TYPE_OPTIONS: list[dict[str, str]] = [
    {"value": "installed", "label": "Installed"},
    {"value": "founded", "label": "Founded"},
    {"value": "recast", "label": "Recast"},
]

_CODE_TO_TYPE: dict[str, str] = {
    "F": "founded",
    "I": "installed",
    "E": "installed",
    "C": "installed",
    "R": "recast",
    "T": "installed",
    "K": "installed",
}

_DEFAULT_YEAR_EVENT_TYPES = ("installed",)


def canonical_site_id(site_ids: list[str]) -> str:
    """Pick the primary site id for a group sharing one detail page."""

    def sort_key(site_id: str) -> tuple[int, int, str]:
        trailing_digits = bool(re.search(r"\d$", site_id))
        return (trailing_digits, len(site_id), site_id)

    return min(site_ids, key=sort_key)


def parse_event_suffix(line_suffix: str | None) -> tuple[int, str] | None:
    if not line_suffix:
        return None
    match = re.match(r"(\d{4})\s+([A-Z*])", line_suffix.strip())
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def event_code_to_type(code: str) -> str | None:
    return _CODE_TO_TYPE.get(code.upper())


def build_event(year: int, code: str) -> dict[str, Any] | None:
    event_type = event_code_to_type(code)
    if not event_type:
        return None
    return {"year": year, "code": code.upper(), "type": event_type}


def merge_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[int, str, str]] = set()
    merged: list[dict[str, Any]] = []
    for event in events:
        key = (event["year"], event["code"], event["type"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(event)
    merged.sort(key=lambda item: (-item["year"], item["type"], item["code"]))
    return merged


def events_from_line_suffix(line_suffix: str | None) -> list[dict[str, Any]]:
    parsed = parse_event_suffix(line_suffix)
    if not parsed:
        return []
    year, code = parsed
    event = build_event(year, code)
    return [event] if event else []


def primary_installation_year(events: list[dict[str, Any]]) -> int | None:
    installed = [event["year"] for event in events if event.get("type") == "installed"]
    if installed:
        return max(installed)
    return None


def events_to_json(events: list[dict[str, Any]]) -> str:
    return json.dumps(events, separators=(",", ":"))


def events_from_json(raw: str | None) -> list[dict[str, Any]]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return merge_events([event for event in data if isinstance(event, dict) and "year" in event])


def normalize_year_event_types(values: list[str] | None) -> list[str]:
    allowed = {option["value"] for option in EVENT_TYPE_OPTIONS}
    if not values:
        return list(_DEFAULT_YEAR_EVENT_TYPES)
    normalized = []
    for value in values:
        key = value.strip().lower()
        if key in allowed and key not in normalized:
            normalized.append(key)
    return normalized or list(_DEFAULT_YEAR_EVENT_TYPES)
