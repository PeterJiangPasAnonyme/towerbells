"""Structured past carillonist display with timeline parsing."""

from __future__ import annotations

import json
import re
from typing import Any

CERT_A_RE = re.compile(r"\(A\)|\(Associate Carillonneur\)", re.I)
CERT_C_RE = re.compile(r"\(C\)|\(Carillonneur\)|\(Certified Carillonneur\)", re.I)
CERT_CH_RE = re.compile(r"\(CH[^)]*\)", re.I)
CERT_STRIP_RE = re.compile(
    r"\s*\(A\)|\(C\)|\(Carillonneur\)|\(Certified Carillonneur\)|"
    r"\(Associate Carillonneur\)|\(CH[^)]*\)\s*",
    re.I,
)

DEDICATION_RE = re.compile(
    r"(?:"
    r"(?P<ded_compact>\d{1,2}[A-Za-z]{2,}\d{2,4}|\d{4}[A-Za-z]{2,}\d{2,4})"
    r"[\s.]*(?:ded\.?|dedicated|inaug\.?)"
    r"|"
    r"(?P<ded_year>\d{4})[\s.]*(?:ded\.?|dedicated|inaug\.?)"
    r"|"
    r"(?P<ded_long>\d{1,2}\s+[A-Za-z]{3,}\s+\d{4})[\s.]*(?:ded\.?|dedicated|inaug\.?)"
    r"|"
    r"(?P<ded_paren>\([^)]*\b(?:chime|carillon)\s+ded[^)]*\))"
    r"|"
    r"(?P<ded_word>ded\.?\s*\d{1,2}[A-Za-z]{2,}\d{2,4}|ded\.?\s*\d{4}[A-Za-z]{2,}\d{2,4})"
    r"|"
    r"dedication"
    r")",
    re.I,
)

YEAR_RANGE_RE = re.compile(
    r"^\s*(?:"
    r"(?P<circa>c\.?\s*)?"
    r"(?P<start>\d{4}|\d{2,4}[?xX_]+|\?\?|\d\?|\?\d|\d_\d|\d{3}\?)"
    r"(?:\s*[-–—:]\s*"
    r"(?P<end>\d{4}|\d{2,4}(?:[?xX_]+)?|\?\?|\d\?|\?\d|xx|19xx|20xx|\d_\d|\d{3}\?))?"
    r")\s*(?P<rest>.*)?$",
    re.I,
)

PLACEHOLDER_RE = re.compile(
    r"^\s*\((?P<label>unknown|none|students|various[^)]*)\)\s*$",
    re.I,
)
SILENT_RE = re.compile(r"\(carillon\s+silent\)", re.I)
SEE_REF_RE = re.compile(r"\(see\s+[^)]+\)", re.I)

LIFESPAN_BIRTH_DEATH_RE = re.compile(r"\((\d{4})\s*[-–—]\s*(\d{4})\)")
DEATH_ONLY_RE = re.compile(r"\(d\.?\s*(\d{4})\??\)", re.I)
DEATH_UNKNOWN_RE = re.compile(r"\(d\.?\)", re.I)

YEAR_UNCERTAIN_RE = re.compile(r"[?xX_]|19xx|20xx|\?\?", re.I)

AND_SPLIT_RE = re.compile(r"\s*-\s*and\s*-", re.I)


def parse_past_carillonist_override(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _expand_end_year(start: int, end_token: str) -> int | None:
    token = end_token.strip()
    if YEAR_UNCERTAIN_RE.search(token):
        return None
    if len(token) == 4 and token.isdigit():
        return int(token)
    if len(token) <= 2 and token.isdigit():
        century = (start // 100) * 100
        year = century + int(token)
        if year < start:
            year += 100
        return year
    return None


def _parse_year_token(token: str) -> int | None:
    token = token.strip()
    if YEAR_UNCERTAIN_RE.search(token):
        return None
    if len(token) == 4 and token.isdigit():
        return int(token)
    return None


def _extract_lifespan(text: str) -> tuple[str, str | None]:
    """Return cleaned text and standardized lifespan parenthetical."""
    lifespan: str | None = None

    match = LIFESPAN_BIRTH_DEATH_RE.search(text)
    if match:
        lifespan = f"({match.group(1)}–{match.group(2)})"
        text = text[: match.start()] + text[match.end() :]

    for match in DEATH_ONLY_RE.finditer(text):
        lifespan = f"(-{match.group(1)})"
        text = text[: match.start()] + text[match.end() :]
        break

    if not lifespan and DEATH_UNKNOWN_RE.search(text):
        lifespan = "(–)"
        text = DEATH_UNKNOWN_RE.sub("", text)

    text = re.sub(r"\s+", " ", text).strip(" ,;")
    return text, lifespan


def _extract_cert(text: str) -> tuple[str, str | None]:
    cert: str | None = None
    if CERT_A_RE.search(text):
        cert = "Associate Carillonneur"
    elif CERT_C_RE.search(text):
        cert = "Certified Carillonneur"
    elif CERT_CH_RE.search(text):
        cert = "Certified Carillonneur"

    cleaned = CERT_STRIP_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;")
    return cleaned, cert


def _format_date_label(start: int | None, end: int | None, *, raw_range: str | None = None) -> str | None:
    if start is None:
        return raw_range.strip() if raw_range else None
    if end is None:
        return raw_range.strip() if raw_range else str(start)
    if start == end:
        return str(start)
    if end // 100 == start // 100:
        return f"{start}–{end % 100:02d}"
    return f"{start}–{end}"


def _is_block_start(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("(") and (
        PLACEHOLDER_RE.match(stripped)
        or SEE_REF_RE.search(stripped)
        or SILENT_RE.search(stripped)
    ):
        return True
    if DEDICATION_RE.search(stripped):
        return True
    if YEAR_RANGE_RE.match(stripped):
        return True
    return False


def _split_blocks(raw: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []

    for line in raw.splitlines():
        if not line.strip():
            continue
        if _is_block_start(line) and current:
            blocks.append("\n".join(current))
            current = [line.strip()]
        else:
            current.append(line.strip())

    if current:
        blocks.append("\n".join(current))
    return blocks


def _parse_year_tokens(
    start_token: str,
    end_token: str | None,
    *,
    circa: str | None = None,
) -> tuple[int | None, int | None, str | None, list[str]]:
    flags: list[str] = []
    start_token = (start_token or "").strip()
    end_token = (end_token or "").strip() if end_token else None

    if YEAR_UNCERTAIN_RE.search(start_token):
        flags.append("partial_dates")
        start = None
    else:
        start = _parse_year_token(start_token)

    end: int | None = None
    if end_token:
        if YEAR_UNCERTAIN_RE.search(end_token):
            flags.append("partial_dates")
        elif start is not None:
            end = _expand_end_year(start, end_token)
        else:
            end = _parse_year_token(end_token)

    if circa:
        flags.append("circa_date")

    label_parts = [start_token]
    if end_token:
        label_parts.append(end_token)
    raw_range = "–".join(label_parts) if start is None else None
    date_label = _format_date_label(start, end, raw_range=raw_range)
    return start, end, date_label, flags


def _parse_dedication_year(text: str) -> tuple[int | None, str | None]:
    compact = re.search(r"(\d{4})", text)
    if compact:
        return int(compact.group(1)), None
    return None, text.strip()


def _entry_base(**kwargs: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": kwargs.get("kind", "tenure"),
        "person_name": kwargs.get("person_name"),
        "cert_label": kwargs.get("cert_label"),
        "person_title": kwargs.get("person_title"),
        "lifespan": kwargs.get("lifespan"),
        "date_label": kwargs.get("date_label"),
        "start_year": kwargs.get("start_year"),
        "end_year": kwargs.get("end_year"),
        "flags": kwargs.get("flags") or [],
        "raw": kwargs.get("raw", ""),
    }
    return entry


def _parse_block(block: str) -> dict[str, Any]:
    lines = [line.strip() for line in block.splitlines() if line.strip()]
    raw = "\n".join(lines)
    flags: list[str] = []
    first = lines[0]

    if SEE_REF_RE.search(first) and re.match(r"^\(see\b", first, re.I):
        flags.append("cross_reference")
        return _entry_base(
            kind="cross_ref",
            person_name=first.strip(),
            date_label=None,
            flags=flags,
            raw=raw,
        )

    silent_match = SILENT_RE.search(first)
    if silent_match:
        flags.append("carillon_silent")
        rest = SILENT_RE.sub("", first).strip()
        start, end, date_label, range_flags = (None, None, None, [])
        if rest:
            yr_match = YEAR_RANGE_RE.match(rest)
            if yr_match:
                start, end, date_label, range_flags = _parse_year_tokens(
                    yr_match.group("start") or "",
                    yr_match.group("end"),
                    circa=yr_match.group("circa"),
                )
        flags.extend(range_flags)
        return _entry_base(
            kind="silent",
            person_name="Carillon silent",
            start_year=start,
            end_year=end,
            date_label=date_label or rest or "Carillon silent",
            flags=flags,
            raw=raw,
        )

    placeholder = PLACEHOLDER_RE.match(first)
    if placeholder:
        label = placeholder.group("label").strip().lower()
        if label == "unknown":
            flags.append("placeholder_unknown")
        elif label == "none":
            flags.append("placeholder_none")
        else:
            flags.append("placeholder_other")
        start, end, date_label, range_flags = (None, None, None, [])
        yr_match = YEAR_RANGE_RE.match(first)
        if yr_match and yr_match.group("rest") and PLACEHOLDER_RE.match(yr_match.group("rest").strip()):
            start, end, date_label, range_flags = _parse_year_tokens(
                yr_match.group("start") or "",
                yr_match.group("end"),
                circa=yr_match.group("circa"),
            )
        flags.extend(range_flags)
        return _entry_base(
            kind="placeholder",
            person_name=f"({placeholder.group('label').strip()})",
            start_year=start,
            end_year=end,
            date_label=date_label,
            flags=flags,
            raw=raw,
        )

    if DEDICATION_RE.search(first):
        flags.append("dedication")
        ded_year, _ = _parse_dedication_year(first)
        body = DEDICATION_RE.sub("", first, count=1).strip(" .-")
        body, lifespan = _extract_lifespan(body)
        body, cert = _extract_cert(body)
        title: str | None = None
        if len(lines) > 1:
            extra = " ".join(lines[1:])
            extra, life2 = _extract_lifespan(extra)
            lifespan = lifespan or life2
            if extra and not title:
                if re.match(r"^\(\d{4}", extra):
                    _, lifespan2 = _extract_lifespan(extra)
                    lifespan = lifespan or lifespan2
                else:
                    title = extra
        return _entry_base(
            kind="dedication",
            person_name=body or None,
            cert_label=cert,
            person_title=title,
            lifespan=lifespan,
            start_year=ded_year,
            end_year=ded_year,
            date_label=str(ded_year) if ded_year else first.split()[0] if first else None,
            flags=flags,
            raw=raw,
        )

    range_match = YEAR_RANGE_RE.match(first)
    if range_match:
        start, end, date_label, range_flags = _parse_year_tokens(
            range_match.group("start") or "",
            range_match.group("end"),
            circa=range_match.group("circa"),
        )
        flags.extend(range_flags)
        rest = (range_match.group("rest") or "").strip()

        inline_placeholder = PLACEHOLDER_RE.match(rest) if rest else None
        if inline_placeholder:
            label = inline_placeholder.group("label").strip().lower()
            if label == "unknown":
                flags.append("placeholder_unknown")
            elif label == "none":
                flags.append("placeholder_none")
            else:
                flags.append("placeholder_other")
            return _entry_base(
                kind="placeholder",
                person_name=f"({inline_placeholder.group('label').strip()})",
                start_year=start,
                end_year=end,
                date_label=date_label or _format_date_label(start, end),
                flags=flags,
                raw=raw,
            )

        if rest and SEE_REF_RE.search(rest):
            flags.append("cross_reference")

        name_part = rest
        title: str | None = None
        lifespan: str | None = None
        cert: str | None = None
        if len(lines) > 1:
            titles: list[str] = []
            for cont in lines[1:]:
                cont_clean, life = _extract_lifespan(cont)
                if life:
                    lifespan = lifespan or life
                elif re.match(r"^\(\d{4}", cont_clean):
                    _, life2 = _extract_lifespan(cont_clean)
                    lifespan = lifespan or life2
                elif cont_clean:
                    titles.append(cont_clean)
            if titles:
                title = "\n".join(titles)

        name_part, life_from_name = _extract_lifespan(name_part or "")
        lifespan = lifespan or life_from_name
        name_part, cert = _extract_cert(name_part or "")

        if not name_part and title:
            name_part, title = title, None

        return _entry_base(
            kind="tenure",
            person_name=name_part or None,
            cert_label=cert,
            person_title=title,
            lifespan=lifespan,
            start_year=start,
            end_year=end,
            date_label=date_label or _format_date_label(start, end),
            flags=flags,
            raw=raw,
        )

    # Name-only or unusual block → unknown time
    flags.append("no_year")
    if "&" in first:
        flags.append("ampersand_names")
    if ":" in first and re.search(r"\d{4}\s*[-–—:]", first):
        flags.append("colon_separator")

    combined = "\n".join(lines)
    combined, lifespan = _extract_lifespan(combined)
    combined, cert = _extract_cert(combined)
    return _entry_base(
        kind="unknown_time",
        person_name=combined or None,
        cert_label=cert,
        lifespan=lifespan,
        flags=flags,
        raw=raw,
    )


def _timeline_bounds(entries: list[dict[str, Any]]) -> tuple[int | None, int | None]:
    years: list[int] = []
    for entry in entries:
        for key in ("start_year", "end_year"):
            val = entry.get(key)
            if isinstance(val, int):
                years.append(val)
    if not years:
        return None, None
    return min(years), max(years)


def _assign_timeline_positions(entries: list[dict[str, Any]], *, year_min: int, year_max: int) -> None:
    span = max(year_max - year_min, 1)
    for entry in entries:
        start = entry.get("start_year")
        end = entry.get("end_year") or start
        if not isinstance(start, int):
            continue
        if not isinstance(end, int):
            end = start
        entry["axis_start_pct"] = round((start - year_min) / span * 100, 2)
        entry["axis_end_pct"] = round((end - year_min) / span * 100, 2)


def _apply_override(result: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not override:
        return result
    if override.get("timelines") and isinstance(override["timelines"], list):
        result["timelines"] = override["timelines"]
        result["has_content"] = bool(override["timelines"] or result.get("unknown_time"))
    if "unknown_time" in override and isinstance(override["unknown_time"], list):
        result["unknown_time"] = override["unknown_time"]
    return result


def build_past_carillonist_display(
    site: dict,
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = (site.get("past_carillonists") or "").strip()
    if not raw:
        result = {
            "has_content": False,
            "timelines": [],
            "unknown_time": [],
            "flags": [],
        }
        return _apply_override(result, override)

    all_flags: list[dict[str, Any]] = []
    parsed_entries: list[dict[str, Any]] = []

    for segment in AND_SPLIT_RE.split(raw):
        segment = segment.strip()
        if not segment:
            continue
        if AND_SPLIT_RE.search(raw):
            pass  # flag below per block if needed
        for block in _split_blocks(segment):
            entry = _parse_block(block)
            entry["id"] = f"pc-{len(parsed_entries)}"
            parsed_entries.append(entry)
            for flag in entry.get("flags") or []:
                all_flags.append({"site_id": site.get("site_id"), "entry_id": entry["id"], "flag": flag, "raw": entry.get("raw")})

    silent_entries = [e for e in parsed_entries if e.get("kind") == "silent"]
    timed_entries: list[dict[str, Any]] = []
    unknown_time: list[dict[str, Any]] = []

    for entry in parsed_entries:
        kind = entry.get("kind")
        if kind == "silent":
            continue
        if kind == "unknown_time":
            unknown_time.append(entry)
            continue
        start = entry.get("start_year")
        has_uncertain = "partial_dates" in (entry.get("flags") or []) and (
            start is None or entry.get("end_year") is None and "?" in (entry.get("date_label") or "")
        )
        if kind in ("tenure", "placeholder", "dedication", "cross_ref"):
            if start is None:
                unknown_time.append(entry)
            elif has_uncertain and start is None:
                unknown_time.append(entry)
            else:
                timed_entries.append(entry)
        else:
            timed_entries.append(entry)

    # Entries with uncertain start (19??) but known end → unknown section
    still_timed: list[dict[str, Any]] = []
    for entry in timed_entries:
        raw_line = entry.get("raw") or ""
        if re.search(r"19\?\?|19xx|\?\?-|^\s*\?\?", raw_line, re.I) and entry.get("start_year") is None:
            entry.setdefault("flags", []).append("partial_dates")
            unknown_time.append(entry)
        elif re.match(r"^\s*(?:19\?\?|19xx|\?\?|\d\?|\?\d)", raw_line, re.I):
            entry.setdefault("flags", []).append("partial_dates")
            unknown_time.append(entry)
        else:
            still_timed.append(entry)
    timed_entries = still_timed

    timelines: list[dict[str, Any]] = []
    year_min, year_max = _timeline_bounds(timed_entries)
    if timed_entries and year_min is not None and year_max is not None:
        _assign_timeline_positions(timed_entries, year_min=year_min, year_max=year_max)
        timelines.append(
            {
                "id": "appointments",
                "label": None,
                "year_min": year_min,
                "year_max": year_max,
                "entries": timed_entries,
            }
        )

    if silent_entries:
        s_min, s_max = _timeline_bounds(silent_entries)
        if s_min is None:
            s_min = year_min or 1900
        if s_max is None:
            s_max = year_max or s_min
        _assign_timeline_positions(silent_entries, year_min=s_min, year_max=s_max)
        timelines.append(
            {
                "id": "silent",
                "label": "Carillon silent",
                "year_min": s_min,
                "year_max": s_max,
                "entries": silent_entries,
            }
        )

    result = {
        "has_content": bool(timelines or unknown_time),
        "timelines": timelines,
        "unknown_time": unknown_time,
        "flags": all_flags,
    }
    return _apply_override(result, override)


def collect_past_carillonist_flags(sites: list[dict]) -> list[dict[str, Any]]:
    """Return all flagged entries across sites for review."""
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for site in sites:
        display = build_past_carillonist_display(site)
        if not display.get("has_content"):
            continue
        site_id = site.get("site_id")
        for item in display.get("flags") or []:
            key = (site_id, item.get("entry_id"), item.get("flag"))
            if key in seen:
                continue
            seen.add(key)
            rows.append({**item, "site_id": site_id})
        for entry in display.get("unknown_time") or []:
            for flag in entry.get("flags") or []:
                key = (site_id, entry.get("id"), flag)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "site_id": site_id,
                        "entry_id": entry.get("id"),
                        "flag": flag,
                        "raw": entry.get("raw"),
                    }
                )
    return rows
