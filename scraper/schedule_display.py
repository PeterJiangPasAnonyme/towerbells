"""Structured schedule display for carillon detail pages."""

from __future__ import annotations

import json
import re
from typing import Any

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
DAY_ALIASES: dict[str, str] = {
    "mon": "mon",
    "monday": "mon",
    "tue": "tue",
    "tues": "tue",
    "tuesday": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "thu": "thu",
    "thur": "thu",
    "thurs": "thu",
    "thursday": "thu",
    "fri": "fri",
    "friday": "fri",
    "sat": "sat",
    "saturday": "sat",
    "sun": "sun",
    "sunday": "sun",
}

UNKNOWN_RE = re.compile(r"^\s*\(?unknown\)?\.?\s*$", re.I)
IRREGULAR_RE = re.compile(
    r"(?:"
    r"no regular schedule|"
    r"not played regularly|"
    r"not regularly played|"
    r"about \d+\s+concerts|"
    r"never been fully restored|"
    r"has never been fully restored|"
    r"quarter\s*&?\s*hour strike currently silent|"
    r"currently silent"
    r")",
    re.I,
)
HIDDEN_SCHEDULE_BADGES = frozenset({"Schedule unknown", "No regular schedule"})
CONDITION_PREFIX_RE = re.compile(
    r"^(?P<condition>"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"(?:\s*(?:-|to|–)\s*"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?))?"
    r"|Jun-Aug|Jun\s*-\s*Aug|May|Sep|Summer|Winter|Spring|Autumn|Fall|Advent|year-round|Year-round"
    r"|\([^)]+\)"
    r"|\d{1,2}\s+(?:Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?)"
    r"(?:\s+to\s+\d{1,2}\s+(?:Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?))?"
    r")\s*:\s*(?P<body>.+)$",
    re.I,
)
DAY_TOKEN_RE = re.compile(
    r"\b(Mon|Tue(?:s)?|Wed|Thu(?:r)?|Fri|Sat(?:urday)?|Sun(?:day)?)s?\b",
    re.I,
)
DAY_RANGE_RE = re.compile(
    r"\b(Mon|Tue(?:s)?|Wed|Thu(?:r)?|Fri|Sat(?:urday)?|Sun(?:day)?)s?\s*-\s*"
    r"(Mon|Tue(?:s)?|Wed|Thu(?:r)?|Fri|Sat(?:urday)?|Sun(?:day)?)s?\b",
    re.I,
)
DAY_LIST_RE = re.compile(
    r"\b(Mon|Tue(?:s)?|Wed|Thu(?:r)?|Fri|Sat(?:urday)?|Sun(?:day)?)s?"
    r"(?:\s*,\s*(Mon|Tue(?:s)?|Wed|Thu(?:r)?|Fri|Sat(?:urday)?|Sun(?:day)?)s?)+",
    re.I,
)
TIME_TOKEN_RE = re.compile(
    r"\b("
    r"noon|midnight|"
    r"\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?|"
    r"\d{3,4}(?:\s*-\s*\d{3,4})?|"
    r"\d{1,2}(?:\s*-\s*\d{1,2})?\s*(?:am|pm)"
    r")\b",
    re.I,
)
SUFFIX_CONDITION_RE = re.compile(
    r"(?:\bwhen school is in session\b|"
    r"\bdaily during Advent\b|"
    r"\bfrom mid-June thru August\b|"
    r"\byear-round\b|"
    r"\bsummer(?:\s+\([^)]+\))?\b|"
    r"\bsummer \(15 Jun to 15 Sep\)"
    r")",
    re.I,
)
TRAILING_CONDITION_RE = re.compile(
    r",\s*(when school is in session|year-round|daily during Advent|from mid-June thru August)\s*\.?$",
    re.I,
)
EXTRA_PROSE_MARKERS = re.compile(
    r"(?:also |special events|tours of|admission|open to visitors|hour strike|quarter|"
    r"fireworks|festival|holiday|Independence Day|New Year|marriages|recorded|"
    r"Gardens open|visitor|museum open|silenced|restored|programmed to play)",
    re.I,
)


def parse_schedule_override(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _empty_days() -> dict[str, list[str] | None]:
    return {day: None for day in DAY_KEYS}


def _normalize_day(token: str) -> str | None:
    return DAY_ALIASES.get(token.lower().strip())


def _day_index(day: str) -> int:
    return DAY_KEYS.index(day)


def _expand_day_range(start: str, end: str) -> list[str]:
    start_day = _normalize_day(start)
    end_day = _normalize_day(end)
    if not start_day or not end_day:
        return []
    start_idx = _day_index(start_day)
    end_idx = _day_index(end_day)
    if start_idx <= end_idx:
        return list(DAY_KEYS[start_idx : end_idx + 1])
    return list(DAY_KEYS[start_idx:]) + list(DAY_KEYS[: end_idx + 1])


def _extract_days(text: str) -> tuple[list[str], str]:
    remaining = text
    found: list[str] = []

    for match in DAY_RANGE_RE.finditer(text):
        found.extend(_expand_day_range(match.group(1), match.group(2)))

    for match in DAY_LIST_RE.finditer(text):
        for token in re.findall(
            r"(Mon|Tue(?:s)?|Wed|Thu(?:r)?|Fri|Sat(?:urday)?|Sun(?:day)?)s?",
            match.group(0),
            re.I,
        ):
            day = _normalize_day(token)
            if day:
                found.append(day)

    if not found:
        for match in DAY_TOKEN_RE.finditer(text):
            day = _normalize_day(match.group(1))
            if day:
                found.append(day)

    if found:
        seen: set[str] = set()
        ordered: list[str] = []
        for day in found:
            if day not in seen:
                seen.add(day)
                ordered.append(day)
        found = ordered
        remaining = DAY_RANGE_RE.sub(" ", remaining)
        remaining = DAY_LIST_RE.sub(" ", remaining)
        remaining = DAY_TOKEN_RE.sub(" ", remaining)

    return found, re.sub(r"\s+", " ", remaining).strip(" ,;")


def _format_hour_12(hour: int, minute: int = 0) -> str:
    suffix = "am" if hour < 12 else "pm"
    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12
    if minute:
        return f"{display_hour}:{minute:02d}{suffix}"
    return f"{display_hour}{suffix}"


def _normalize_time_token(token: str) -> str | None:
    text = token.strip().lower()
    if text == "noon":
        return "12:00pm"
    if text == "midnight":
        return "12:00am"

    match = re.fullmatch(r"(\d{3,4})(?:\s*-\s*(\d{3,4}))?", text.replace(" ", ""))
    if match:
        start = match.group(1)
        sh, sm = int(start[:-2]), int(start[-2:])
        if match.group(2):
            end = match.group(2)
            eh, em = int(end[:-2]), int(end[-2:])
            return f"{sh:02d}:{sm:02d}–{eh:02d}:{em:02d}"
        return f"{sh:02d}:{sm:02d}"

    match = re.fullmatch(
        r"(\d{1,2})(?::(\d{2}))?(?:\s*-\s*(\d{1,2})(?::(\d{2}))?)?\s*(am|pm)?",
        text,
    )
    if match:
        sh = int(match.group(1))
        sm = int(match.group(2) or 0)
        meridiem = match.group(5)
        if meridiem == "pm" and sh < 12:
            sh += 12
        if meridiem == "am" and sh == 12:
            sh = 0
        if match.group(3):
            eh = int(match.group(3))
            em = int(match.group(4) or 0)
            if meridiem == "pm" and eh < 12:
                eh += 12
            if meridiem == "am" and eh == 12:
                eh = 0
            return f"{_format_hour_12(sh, sm)}–{_format_hour_12(eh, em)}"
        return _format_hour_12(sh, sm)

    match = re.fullmatch(r"(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s*(am|pm)", text)
    if match:
        sh = int(match.group(1))
        meridiem = match.group(3)
        if match.group(2):
            eh = int(match.group(2))
            return f"{sh}{meridiem}–{eh}{meridiem}"
        if meridiem == "pm" and sh < 12:
            return _format_hour_12(sh + 12, 0)
        return f"{sh}{meridiem}"

    return token.strip()


def _extract_times(text: str) -> tuple[list[str], str]:
    times: list[str] = []
    remaining = text
    for match in TIME_TOKEN_RE.finditer(text):
        normalized = _normalize_time_token(match.group(1))
        if normalized:
            times.append(normalized)
    if times:
        remaining = TIME_TOKEN_RE.sub(" ", text)
        remaining = re.sub(r"\band\b", " ", remaining, flags=re.I)
        remaining = re.sub(r"\s+", " ", remaining).strip(" ,;")
    return times, remaining


def _split_clauses(text: str) -> list[str]:
    lines = [re.sub(r"\s+", " ", line.strip()) for line in text.splitlines() if line.strip()]
    grouped: list[str] = []
    for line in lines:
        if re.match(
            r"^(?:"
            r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?(?:\s*-\s*Aug(?:ust)?)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|"
            r"Summer|Winter|Spring|Autumn|Fall"
            r")\s*:",
            line,
            re.I,
        ):
            grouped.append(line)
        elif grouped:
            grouped[-1] = f"{grouped[-1]} {line}"
        else:
            grouped.append(line)

    clauses: list[str] = []
    for chunk in grouped:
        parts = re.split(r"\s*;\s*", chunk)
        clauses.extend(part.strip() for part in parts if part.strip())
    return clauses


def _parse_segment(segment: str) -> tuple[str | None, dict[str, list[str] | None]] | None:
    segment = segment.strip(" .")
    if not segment:
        return None

    condition = None
    body = segment
    prefix = CONDITION_PREFIX_RE.match(segment)
    if prefix:
        condition = prefix.group("condition").strip()
        body = prefix.group("body").strip()

    trailing = TRAILING_CONDITION_RE.search(body)
    if trailing:
        condition = condition or trailing.group(1).strip()
        body = body[: trailing.start()].strip(" ,;")

    suffix_match = SUFFIX_CONDITION_RE.search(body)
    if suffix_match and not condition:
        condition = suffix_match.group(0).strip(" ,")
        body = (body[: suffix_match.start()] + body[suffix_match.end() :]).strip(" ,;")

    times, after_times = _extract_times(body)
    days, leftover = _extract_days(after_times if times else body)

    if not days or not times:
        return None

    if leftover and not condition and len(leftover.split()) <= 8:
        if not re.search(r"\b(at|also|special|tour|open|admission|strike|quarter)\b", leftover, re.I):
            condition = leftover.strip(" ,;")

    day_map = _empty_days()
    for day in days:
        day_map[day] = list(times)
    return condition, day_map


def _parse_text(raw: str) -> tuple[list[dict[str, Any]], list[str]]:
    calendars: list[dict[str, Any]] = []
    prose_parts: list[str] = []
    consumed: set[str] = set()

    for clause in _split_clauses(raw):
        parsed_segments = _parse_clause(clause)
        if parsed_segments:
            consumed.add(clause)
            for condition, days in parsed_segments:
                calendars.append(_calendar_dict(condition, days))
        elif clause and (_looks_like_extra_prose(clause) or len(clause) > 40):
            prose_parts.append(clause)

    if not prose_parts:
        for clause in _split_clauses(raw):
            if clause not in consumed and clause.strip():
                if not _parse_clause(clause):
                    prose_parts.append(clause)

    return calendars, prose_parts


def _parse_clause(clause: str) -> list[tuple[str | None, dict[str, list[str] | None]]]:
    clause = clause.strip()
    if not clause:
        return []

    condition = None
    body = clause
    trailing = TRAILING_CONDITION_RE.search(clause)
    if trailing:
        condition = trailing.group(1).strip()
        body = clause[: trailing.start()].strip(" ,;")

    prefix = CONDITION_PREFIX_RE.match(body)
    if prefix:
        condition = prefix.group("condition").strip()
        body = prefix.group("body").strip()

    suffix_match = SUFFIX_CONDITION_RE.search(body)
    if suffix_match and not condition:
        condition = suffix_match.group(0).strip(" ,")
        body = (body[: suffix_match.start()] + body[suffix_match.end() :]).strip(" ,;")

    segments: list[tuple[list[str], list[str]]] = []
    parts = re.split(
        r"\s+and\s+(?=(?:noon|midnight|\d{1,2}(?::\d{2})?\s*(?:am|pm)?|\d{3,4})\s+"
        r"(?:Sun(?:day)?|Sat(?:urday)?|Wed|Tue(?:s)?|Thu(?:r)?|Fri|Mon(?!-)))",
        body,
        flags=re.I,
    )
    for part in parts:
        times, after_times = _extract_times(part.strip())
        if not times:
            continue
        days, _leftover = _extract_days(after_times)
        if not days:
            continue
        segments.append((days, times))

    if segments:
        merged = _empty_days()
        for days, times in segments:
            for day in days:
                existing = list(merged[day] or [])
                for token in times:
                    if token not in existing:
                        existing.append(token)
                merged[day] = existing
        return [(condition, merged)]

    parsed = _parse_segment(clause)
    return [parsed] if parsed else []


def _calendar_dict(condition: str | None, days: dict[str, list[str] | None]) -> dict[str, Any]:
    return {
        "condition": condition,
        "days": days,
    }


def _is_unknown(text: str) -> bool:
    return not text.strip() or bool(UNKNOWN_RE.match(text.strip()))


def _is_irregular(text: str) -> bool:
    return bool(IRREGULAR_RE.search(text))


def _looks_like_extra_prose(clause: str) -> bool:
    if _parse_clause(clause):
        return False
    return bool(EXTRA_PROSE_MARKERS.search(clause))


def _schedule_has_content(result: dict[str, Any]) -> bool:
    badge = result.get("badge")
    if badge in HIDDEN_SCHEDULE_BADGES and not result.get("calendars"):
        return False
    return bool(
        (badge and badge not in HIDDEN_SCHEDULE_BADGES)
        or result.get("calendars")
        or result.get("prose")
    )


def build_schedule_display(
    site: dict,
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = (site.get("schedule") or "").strip()
    result: dict[str, Any]

    if _is_unknown(raw):
        result = {
            "mode": "badge",
            "badge": "Schedule unknown",
            "calendars": [],
            "prose": None,
            "has_content": False,
        }
    else:
        calendars, prose_parts = _parse_text(raw)
        prose = "\n".join(prose_parts).strip() or None

        if calendars:
            result = {
                "mode": "structured",
                "badge": None,
                "calendars": calendars,
                "prose": prose,
                "has_content": True,
            }
        elif _is_irregular(raw):
            result = {
                "mode": "badge",
                "badge": "No regular schedule",
                "calendars": [],
                "prose": _clean_irregular_prose(raw),
                "has_content": False,
            }
        else:
            result = {
                "mode": "prose",
                "badge": None,
                "calendars": [],
                "prose": raw,
                "has_content": bool(raw),
            }

    result = _apply_override(result, override)
    result["has_content"] = _schedule_has_content(result)
    return result


def _clean_irregular_prose(text: str) -> str | None:
    cleaned = IRREGULAR_RE.sub("", text)
    cleaned = re.sub(r"^\s*[;,\s]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ;.")
    return cleaned or None


def _apply_override(result: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not override:
        return result

    if "mode" in override:
        result["mode"] = override["mode"]
    if "badge" in override:
        badge = override["badge"]
        result["badge"] = str(badge).strip() if badge else None
    if "calendars" in override and isinstance(override["calendars"], list):
        result["calendars"] = override["calendars"]
        if override["calendars"]:
            result["mode"] = "structured"
            result["badge"] = None
    if "prose" in override:
        prose = override["prose"]
        result["prose"] = str(prose).strip() if prose else None
    if override.get("hide_badge"):
        result["badge"] = None
    if override.get("force_prose") and result.get("prose"):
        result["mode"] = "prose"
        result["calendars"] = []

    result["has_content"] = _schedule_has_content(result)
    return result


def schedule_for_editor(display: dict[str, Any]) -> dict[str, Any]:
    """Return editable schedule JSON with all keys present."""
    if not display:
        return {
            "mode": "prose",
            "badge": None,
            "calendars": [],
            "prose": None,
            "hide_badge": False,
            "force_prose": False,
        }
    return {
        "mode": display.get("mode") or "prose",
        "badge": display.get("badge"),
        "calendars": display.get("calendars") or [],
        "prose": display.get("prose"),
        "hide_badge": bool(display.get("hide_badge")),
        "force_prose": bool(display.get("force_prose")),
    }
