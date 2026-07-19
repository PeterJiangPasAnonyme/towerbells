"""Structured prior-history timeline for site detail pages."""

from __future__ import annotations

import re
from typing import Any

from scraper.carillon_events import events_from_json, merge_events
from scraper.keyboard_display import (
    build_keyboard_display,
    parse_missing_bass_count,
    parse_transposition_semitones,
)
from scraper.technical_display import extract_recent_work
from scraper.technical_sections import split_technical_sections
from scraper.bellfounders import canonical_founder_name
from scraper.text import normalize_remarks_reference

IN_YEAR_SPLIT_RE = re.compile(r"(?=^\s*In\s+\d{4}\b)", re.M)
IN_YEAR_HEAD_RE = re.compile(r"^\s*In\s+(\d{4}),?\s*(.+)$", re.S | re.I)

RECENT_YEAR_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"The instrument was enlarged in\s+(\d{4})\b", re.I), "enlarged"),
    (re.compile(r"The bells were re-tuned in\s+(\d{4})\b", re.I), "retuned"),
    (re.compile(r"The instrument was re-tuned in\s+(\d{4})\b", re.I), "retuned"),
    (re.compile(r"The whole instrument was installed in\s+(\d{4})\b", re.I), "installed"),
    (
        re.compile(r"The complete instrument of\s+(\d+)\s+bells was installed in\s+(\d{4})\b", re.I),
        "installed_complete",
    ),
]

FOOTER_LINE_RE = re.compile(
    r"^(?:No auxiliary mechanisms known|Auxiliary mechanisms:|Tower details|Year of latest technical information)",
    re.I,
)

FOUNDER_LINE_RE = re.compile(
    r"^(?:by|made by|with bells made by|apparently by)\s+(.+)$",
    re.I,
)
WITH_BELLS_MADE_RE = re.compile(r"^with\s+(\d+)\s+bells made by\s+(.+)$", re.I)
KEYBOARD_WAS_RE = re.compile(r"^Keyboard range was:\s*(.+)$", re.I)
HEAVIEST_WAS_RE = re.compile(r"^Pitch of heaviest bell(?: \(excluding sub-bourdon\))? was\s+(.+)$", re.I)
TRANSPOSE_WAS_RE = re.compile(r"^Transposition was\s+(.+)$", re.I)
BELLS_REMAIN_RE = re.compile(
    r"^\((\d+)\s+bells\s+(were added in and/or remain from that work|remain from that work)\.?\)$",
    re.I,
)

BELL_COUNT_RE = re.compile(r"\b(\d+)\s+bells?\b", re.I)

CARILLON_EVENT_HEADLINES = {
    "founded": "Dedicated",
    "installed": "Installed",
    "recast": "Recast",
}


def transposition_text_from_semitones(semitones: int | None) -> str:
    if semitones is None:
        return ""
    if semitones == 0:
        return "nil (concert pitch)"
    direction = "up" if semitones > 0 else "down"
    return f"{direction} {abs(semitones)} semitone(s)"


def _strip_footer_lines(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if FOOTER_LINE_RE.match(stripped):
            break
        lines.append(stripped)
    return "\n".join(lines)


def _normalize_founder(raw: str) -> str:
    founder = normalize_remarks_reference(raw.strip())
    founder = re.sub(r"\s+", " ", founder)
    founder = founder.rstrip(" .")
    return canonical_founder_name(founder) or founder


def _extract_founder_from_action(action: str) -> str | None:
    for pattern in (
        r"\bwith bells made by\s+(.+)$",
        r"\bmade by\s+(.+)$",
        r"\bby\s+(.+)$",
    ):
        match = re.search(pattern, action, re.I)
        if match:
            return _normalize_founder(match.group(1))
    return None


def _extract_bell_count(action: str) -> int | None:
    match = BELL_COUNT_RE.search(action)
    if not match:
        return None
    return int(match.group(1))


def _headline_from_action(action: str, *, founder: str | None, bell_count: int | None) -> str:
    text = re.sub(r"\s+", " ", action.strip())
    lowered = text.lower()
    founder_part = f" by {founder}" if founder else ""

    if "begun with" in lowered:
        if bell_count is not None:
            return f"Dedicated with {bell_count} bells{founder_part}"
        return f"Dedicated{founder_part}"
    if "enlarged to" in lowered or re.search(r"enlarged in \d{4}", lowered):
        if bell_count is not None:
            return f"Enlarged to {bell_count} bells{founder_part}"
        return f"Enlarged{founder_part}"
    if "complete instrument" in lowered and "installed" in lowered:
        if bell_count is not None:
            return f"Installed with {bell_count} bells{founder_part}"
        return f"Installed{founder_part}"
    if "recast or replaced" in lowered:
        return f"Recast or replaced bells{founder_part}"
    if "keyboard was replaced" in lowered:
        return f"Keyboard replaced{founder_part}"
    if "re-tuned" in lowered or "retuned" in lowered:
        return f"Re-tuned{founder_part}"
    if "whole instrument was installed" in lowered or "instrument was installed" in lowered:
        if bell_count is not None:
            return f"Installed with {bell_count} bells{founder_part}"
        return f"Installed{founder_part}"
    if "some bells were recast" in lowered:
        return f"Recast or replaced bells{founder_part}"

    cleaned = text[0].upper() + text[1:] if text else text
    return normalize_remarks_reference(cleaned)


def _parse_sub_lines(event: dict[str, Any], lines: list[str]) -> None:
    for line in lines:
        match = WITH_BELLS_MADE_RE.match(line)
        if match:
            event["bell_count"] = int(match.group(1))
            event["founder"] = _normalize_founder(match.group(2))
            continue

        match = FOUNDER_LINE_RE.match(line)
        if match and not event.get("founder"):
            event["founder"] = _normalize_founder(match.group(1))
            continue

        match = BELLS_REMAIN_RE.match(line)
        if match:
            count = match.group(1)
            phrase = match.group(2).lower()
            if "added" in phrase:
                event["bullets"].append(f"{count} bells were added in and/or remain from that work")
            else:
                event["bullets"].append(f"{count} bells remain from that work")
            continue

        match = KEYBOARD_WAS_RE.match(line)
        if match:
            event["keyboard_range"] = match.group(1).strip()
            continue

        match = HEAVIEST_WAS_RE.match(line)
        if match:
            event["heaviest_pitch"] = match.group(1).strip()
            continue

        match = TRANSPOSE_WAS_RE.match(line)
        if match:
            event["transposition_raw"] = match.group(1).strip()
            event["transposition_semitones"] = parse_transposition_semitones(event["transposition_raw"])
            continue

        if "missing bass semitone" in line.lower():
            event["missing_bass_text"] = line.strip()
            continue


def _parse_event_body(*, year: int, source: str, body: str) -> dict[str, Any]:
    body = normalize_remarks_reference(body.strip())
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    action = lines[0] if lines else ""

    event: dict[str, Any] = {
        "year": year,
        "source": source,
        "action_raw": action,
        "founder": _extract_founder_from_action(action),
        "bell_count": _extract_bell_count(action),
        "keyboard_range": None,
        "heaviest_pitch": None,
        "transposition_raw": None,
        "transposition_semitones": None,
        "missing_bass_text": None,
        "bullets": [],
        "headline": "",
        "keyboard": None,
        "keyboard_bullets": [],
    }

    _parse_sub_lines(event, lines[1:])
    if not event["founder"]:
        for line in lines[1:]:
            match = FOUNDER_LINE_RE.match(line)
            if match:
                event["founder"] = _normalize_founder(match.group(1))
                break

    event["headline"] = _headline_from_action(
        action,
        founder=event.get("founder"),
        bell_count=event.get("bell_count"),
    )
    return event


def _parse_in_year_blocks(text: str) -> list[dict[str, Any]]:
    if not text or not text.strip():
        return []

    events: list[dict[str, Any]] = []
    for chunk in IN_YEAR_SPLIT_RE.split(text.strip()):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = IN_YEAR_HEAD_RE.match(chunk)
        if not match:
            continue
        year = int(match.group(1))
        body = match.group(2).strip()
        events.append(_parse_event_body(year=year, source="prior_history", body=body))
    return events


def _parse_recent_work(text: str) -> dict[str, Any] | None:
    cleaned = _strip_footer_lines(text)
    if not cleaned:
        return None

    for pattern, kind in RECENT_YEAR_PATTERNS:
        match = pattern.search(cleaned)
        if not match:
            continue
        if kind == "installed_complete":
            bell_count = int(match.group(1))
            year = int(match.group(2))
            action = f"The complete instrument of {bell_count} bells was installed"
        else:
            year = int(match.group(1))
            action = match.group(0).strip()
            bell_count = _extract_bell_count(cleaned)

        tail = cleaned[match.end() :].strip()
        lines = [line.strip() for line in tail.splitlines() if line.strip()]
        event = _parse_event_body(
            year=year,
            source="recent_work",
            body="\n".join([action, *lines]),
        )
        if kind == "installed_complete":
            event["bell_count"] = bell_count
            event["headline"] = _headline_from_action(
                action,
                founder=event.get("founder"),
                bell_count=bell_count,
            )
        return event
    return None


def _event_richness(event: dict[str, Any]) -> int:
    score = 0
    for key in ("founder", "keyboard_range", "heaviest_pitch", "transposition_raw"):
        if event.get(key):
            score += 2
    score += len(event.get("bullets") or [])
    if event.get("source") == "prior_history":
        score += 1
    return score


def _dedupe_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_year: dict[int, dict[str, Any]] = {}
    for event in events:
        year = event["year"]
        existing = by_year.get(year)
        if existing is None or _event_richness(event) > _event_richness(existing):
            by_year[year] = event
    return list(by_year.values())


def _infer_transpositions(events: list[dict[str, Any]], current_semitones: int | None) -> None:
    explicit = {
        event["year"]: event["transposition_semitones"]
        for event in events
        if event.get("transposition_semitones") is not None
    }

    for event in sorted(events, key=lambda item: item["year"]):
        if event.get("transposition_semitones") is not None:
            continue
        newer_years = [year for year in explicit if year > event["year"]]
        if newer_years:
            event["transposition_semitones"] = explicit[max(newer_years)]
        else:
            event["transposition_semitones"] = current_semitones


def _keyboard_bullets_for_event(event: dict[str, Any]) -> list[str]:
    bullets: list[str] = []
    if event.get("keyboard_range"):
        bullets.append(f"Keyboard range: {event['keyboard_range'].strip()}")
    if event.get("heaviest_pitch"):
        bullets.append(f"Heaviest bell: {event['heaviest_pitch']}")
    missing_text = event.get("missing_bass_text")
    if missing_text:
        bullets.append(missing_text)
    else:
        missing_count = parse_missing_bass_count(event.get("missing_bass_text"))
        if missing_count:
            label = "semitone" if missing_count == 1 else "semitones"
            bullets.append(f"Missing bass {label}: {missing_count}")
    return bullets


def _attach_keyboard(event: dict[str, Any], site: dict[str, Any]) -> None:
    keyboard_range = (event.get("keyboard_range") or "").strip()
    if not keyboard_range:
        event["keyboard"] = None
        event["keyboard_bullets"] = _keyboard_bullets_for_event(event)
        return

    transposition_raw = event.get("transposition_raw")
    if not transposition_raw and event.get("transposition_semitones") is not None:
        transposition_raw = transposition_text_from_semitones(event["transposition_semitones"])
    if not transposition_raw:
        transposition_raw = site.get("transposition") or ""

    pseudo_site = {
        "keyboard_range": keyboard_range,
        "bell_count": event.get("bell_count"),
        "transposition": transposition_raw,
        "missing_bass_semitone": event.get("missing_bass_text") or "",
        "heaviest_pitch": event.get("heaviest_pitch") or "",
        "technical_data": event.get("missing_bass_text") or "",
    }
    keyboard = build_keyboard_display(pseudo_site)
    show_diagram = bool(keyboard.get("has_content") and not keyboard.get("hide_diagram"))
    if show_diagram and keyboard.get("mode") == "structured":
        event["keyboard"] = keyboard
        event["keyboard_bullets"] = []
    else:
        event["keyboard"] = None
        event["keyboard_bullets"] = _keyboard_bullets_for_event(event)


def _event_from_carillon_record(record: dict[str, Any]) -> dict[str, Any]:
    year = int(record["year"])
    event_type = str(record.get("type") or "installed")
    headline = CARILLON_EVENT_HEADLINES.get(event_type, "Installed")
    return {
        "year": year,
        "source": "carillon_events",
        "action_raw": headline,
        "founder": None,
        "bell_count": None,
        "keyboard_range": None,
        "heaviest_pitch": None,
        "transposition_raw": None,
        "transposition_semitones": None,
        "missing_bass_text": None,
        "bullets": [],
        "headline": headline,
        "keyboard": None,
        "keyboard_bullets": [],
    }


def _carillon_events_from_index(index: dict[str, Any]) -> list[dict[str, Any]]:
    raw = index.get("carillon_events")
    if isinstance(raw, list):
        return merge_events(raw)
    return events_from_json(raw)


def build_prior_history_display(
    site: dict[str, Any],
    *,
    index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index = index or {}
    raw = site.get("technical_data") or ""
    preamble, prior_block, _ = split_technical_sections(raw)
    stored_prior = normalize_remarks_reference((site.get("prior_history") or "").strip())

    events: list[dict[str, Any]] = []
    recent = extract_recent_work(preamble)
    if recent:
        recent_event = _parse_recent_work(recent)
        if recent_event:
            events.append(recent_event)

    prior_text = prior_block.strip() or stored_prior
    events.extend(_parse_in_year_blocks(prior_text))

    covered_years = {event["year"] for event in events}
    for record in _carillon_events_from_index(index):
        year = int(record["year"])
        if year not in covered_years:
            events.append(_event_from_carillon_record(record))

    events = _dedupe_events(events)
    current_semitones = parse_transposition_semitones(site.get("transposition"))
    _infer_transpositions(events, current_semitones)

    for event in events:
        _attach_keyboard(event, site)

    events.sort(key=lambda item: item["year"], reverse=True)

    public_events: list[dict[str, Any]] = []
    for event in events:
        public_events.append(
            {
                "year": event["year"],
                "headline": event["headline"],
                "bullets": event.get("bullets") or [],
                "keyboard": event.get("keyboard"),
                "keyboard_bullets": event.get("keyboard_bullets") or [],
            }
        )

    return {
        "has_content": bool(public_events),
        "events": public_events,
    }
