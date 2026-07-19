"""Display helpers for carillon page titles and subtitles."""

from __future__ import annotations

import re
from typing import Any

from scraper.location_display import (
    FORMERLY_RE,
    build_location_display,
    parse_location_override,
    _is_building_rename_text,
    _is_english_text,
)
from scraper.text import format_display_text, normalize_saint_spacing
from scraper.carillonist_display import build_carillonist_display, parse_carillonist_override
from scraper.contact_display import build_contact_display, parse_contact_override
from scraper.keyboard_display import build_keyboard_display, parse_keyboard_override
from scraper.links_display import build_links_display
from scraper.former_location_display import build_former_location_display
from scraper.prior_history_display import build_prior_history_display
from scraper.remarks_display import build_remarks_display
from scraper.technical_display import build_technical_display
from scraper.past_carillonist_display import (
    build_past_carillonist_display,
    parse_past_carillonist_override,
)
from scraper.schedule_display import build_schedule_display, parse_schedule_override
from server.geo_labels import format_country, format_region

_LL_SUFFIX_RE = re.compile(
    r"\s*LL:\s*(?:[NS]\s*[\d.+-]+(?:,\s*[EW]\s*[\d.+-]+)?|[NS]\s*[\d.]+\s*[EW]\s*[\d.]+).*$",
    re.I | re.S,
)
_GEO_SUFFIX_RE = re.compile(
    r",\s*(?:"
    r"USA|United States|Canada|Mexico|Belgium|France|Germany|Netherlands|"
    r"Austria|Australia|Argentina|England|Scotland|Ireland|Italy|Spain|Portugal|"
    r"Switzerland|Denmark|Sweden|Norway|Finland|Poland|Brazil|Japan|China|"
    r"New Zealand|South Africa|Bosnia and Herzegovina|Bosnia"
    r")(?:,\s*(?:USA|United States|Canada|Belgium|France|Germany|Austria|Australia))?.*$",
    re.I,
)
_STREET_START_RE = re.compile(
    r"\s+(?="
    r"\d{1,5}(?:st|nd|rd|th)?\s+(?:Street|St\.?|Avenue|Ave\.?|Drive|Dr\.?|Road|Rd\.?|"
    r"Boulevard|Blvd\.?|Lane|Ln\.?|Way|Place|Parade|Parkway|Pkwy\.?|Circle|Crescent|"
    r"Close|Terrace|Highway|Hwy\.?)\b"
    r"|"
    r"\d{1,5}[A-Za-z]?\s+(?:North|South|East|West|[NSEW]\.?)\b"
    r"|"
    r"[A-Z][A-Za-z'.-]*\s+(?:Street|St\.?|Avenue|Ave\.?|Drive|Dr\.?|Road|Rd\.?|"
    r"Boulevard|Blvd\.?|Lane|Ln\.?|Way|Circle|Crescent|Close|Terrace|Highway|Hwy\.?)\b"
    r"|"
    r"(?:Grote Markt|Kerkplein|Domplatz|Sint-|Rue |Straat|steenweg|Markt |Parade |"
    r"Governors Drive|Woodlawn Avenue|Stanford Drive|King's Parade|"
    r"Place du |Place |Plaza |Square |Henry Square|St\.Marnock Street|bt Dundona)"
    r")",
    re.I,
)
_GENERIC_TOWER_LINE_RE = re.compile(r"^(North|South|East|West)\s+tower$", re.I)


def _strip_coordinate_suffix(text: str) -> str:
    text = _LL_SUFFIX_RE.sub("", text).strip()
    text = re.sub(r"\s*LL:\s*.*$", "", text, flags=re.I).strip()
    return text


def _strip_trailing_location(text: str) -> str:
    previous = None
    while text and text != previous:
        previous = text
        text = _GEO_SUFFIX_RE.sub("", text).strip()
        text = re.sub(
            r",\s*[A-Za-zÀ-ÿ .'-]+,\s*[A-Za-zÀ-ÿ .'-]+$",
            "",
            text,
        ).strip()
    return text


def _strip_trailing_address(text: str) -> str:
    match = _STREET_START_RE.search(text)
    if match:
        return text[: match.start()].strip()
    return text


def _primary_title_line(full_title: str) -> str:
    lines = [line.strip() for line in full_title.splitlines() if line.strip()]
    if not lines:
        return full_title.strip()

    if len(lines) == 1:
        return _strip_coordinate_suffix(lines[0])

    candidates: list[str] = []
    for line in lines:
        cleaned = _strip_coordinate_suffix(line)
        if not cleaned or _GENERIC_TOWER_LINE_RE.match(cleaned):
            continue
        if re.search(r"(Platz|Straat|Parade|Markt|Domplatz|Kerkplein| / )", cleaned, re.I):
            continue
        candidates.append(cleaned)

    if candidates:
        return candidates[0]
    return _strip_coordinate_suffix(lines[0])


def _prepare_title_base(
    full_title: str | None,
    *,
    short_name: str | None = None,
) -> str:
    """Return a cleaned title string before translation split and display casing."""
    title = re.sub(r"\s+", " ", (full_title or "")).strip()
    if not title:
        return short_name or ""

    title = _primary_title_line(title)
    title = _strip_coordinate_suffix(title)
    title = _strip_trailing_address(title)
    title = _strip_trailing_location(title)
    title = re.sub(r"\s+", " ", title).strip(" ,;-")

    if not title:
        return short_name or full_title or ""

    if len(title) > 120:
        title = _strip_trailing_address(title) or title[:120].rsplit(" ", 1)[0]

    return title


def _title_paren_is_translation(inner: str) -> bool:
    cleaned = inner.strip()
    if not cleaned:
        return False
    if _is_building_rename_text(cleaned) or FORMERLY_RE.search(cleaned):
        return False
    if re.fullmatch(r"#\d+", cleaned):
        return False
    return _is_english_text(cleaned)


def _split_display_title(title: str) -> tuple[str, str | None]:
    """Split a title into primary line and optional English translation."""
    cleaned = re.sub(r"\s+", " ", (title or "")).strip()
    if not cleaned:
        return "", None

    match = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", cleaned)
    if not match:
        return cleaned, None

    primary, inner = match.group(1).strip(), match.group(2).strip()
    if _title_paren_is_translation(inner):
        return primary, inner
    return cleaned, None


def _format_title_override(text: str) -> str:
    """Preserve manual override casing; only normalize whitespace and saint spacing."""
    cleaned = re.sub(r"\s+", " ", (text or "")).strip()
    return normalize_saint_spacing(cleaned)


def clean_display_title(
    full_title: str | None,
    *,
    short_name: str | None = None,
    location_text: str | None = None,
) -> str:
    """Return an institution-focused title without embedded address or coordinates."""
    title, _translation = _split_display_title(
        _prepare_title_base(full_title, short_name=short_name)
    )
    return format_display_text(title)


def auto_display_title_translation_for_site(site: dict) -> str | None:
    _title, translation = _split_display_title(
        _prepare_title_base(site.get("full_title"), short_name=site.get("short_name"))
    )
    return format_display_text(translation) if translation else None


def display_title_translation_for_site(site: dict) -> str | None:
    translation_override = (site.get("display_title_translation_override") or "").strip()
    if translation_override:
        return _format_title_override(translation_override)

    title_override = (site.get("display_title_override") or "").strip()
    if title_override:
        _line, translation = _split_display_title(title_override)
        if translation:
            return _format_title_override(translation)

    return auto_display_title_translation_for_site(site)


def display_title_for_site(site: dict) -> str:
    """Clean title for lists, search, and detail pages."""
    override = (site.get("display_title_override") or "").strip()
    if override:
        line, _translation = _split_display_title(override)
        return _format_title_override(line or override)
    return auto_display_title_for_site(site)


def site_row_for_display(index_row: dict[str, Any], sites_row: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge site_index + sites rows so display titles use the sites table as source of truth."""
    merged = dict(index_row)
    if not sites_row:
        return merged
    for key in (
        "full_title",
        "short_name",
        "display_title_override",
        "display_title_translation_override",
        "location_text",
        "location_display_override",
    ):
        if key in sites_row:
            merged[key] = sites_row[key]
    return merged


def auto_display_title_for_site(site: dict) -> str:
    return clean_display_title(
        site.get("full_title"),
        short_name=site.get("short_name"),
        location_text=site.get("location_text"),
    )


def format_site_subtitle(
    *,
    country_code: str | None,
    state_province: str | None,
    bell_count: int | None = None,
    installation_year: int | None = None,
    bourdon_pitch: str | None = None,
) -> str:
    """Build 'State, Country · N bells · year · Bourdon X'."""
    parts: list[str] = []
    location = format_location_subtitle(
        country_code=country_code,
        state_province=state_province,
        bell_count=bell_count,
    )
    if location:
        parts.append(location)
    elif bell_count:
        bells = f"{bell_count} bell" if bell_count == 1 else f"{bell_count} bells"
        parts.append(bells)

    if installation_year:
        parts.append(str(installation_year))
    if bourdon_pitch:
        pitch = bourdon_pitch.upper() if len(bourdon_pitch.strip()) == 1 else format_display_text(bourdon_pitch)
        parts.append(f"Bourdon {pitch}")

    return " · ".join(parts)


def format_location_subtitle(
    *,
    country_code: str | None,
    state_province: str | None,
    bell_count: int | None = None,
) -> str:
    """Build 'State, Country · N bells' (or country-only when no subdivision)."""
    country = format_country(country_code or "")
    region = format_region(country_code or "", state_province or "")

    location_parts: list[str] = []
    if region:
        location_parts.append(region)
    if country and country not in location_parts:
        location_parts.append(country)

    subtitle = ", ".join(location_parts)
    if bell_count:
        bells = f"{bell_count} bell" if bell_count == 1 else f"{bell_count} bells"
        subtitle = f"{subtitle} · {bells}" if subtitle else bells
    return subtitle


def build_site_display(
    site: dict,
    *,
    index: dict | None = None,
    get_site: Any | None = None,
) -> dict[str, Any]:
    index = index or {}
    bell_count = site.get("bell_count") or index.get("bell_count")
    title = display_title_for_site(site)
    title_auto = auto_display_title_for_site(site)
    title_translation = display_title_translation_for_site(site)
    title_translation_auto = auto_display_title_translation_for_site(site)
    override = parse_location_override(site.get("location_display_override"))
    location = build_location_display(
        site,
        page_title=title,
        override=override,
    )
    schedule_override = parse_schedule_override(site.get("schedule_display_override"))
    schedule = build_schedule_display(site, override=schedule_override)
    contact_override = parse_contact_override(site.get("contact_display_override"))
    contact = build_contact_display(site, override=contact_override)
    carillonist_override = parse_carillonist_override(site.get("carillonist_display_override"))
    carillonist = build_carillonist_display(site, override=carillonist_override)
    past_override = parse_past_carillonist_override(site.get("past_carillonist_display_override"))
    past_carillonists = build_past_carillonist_display(site, override=past_override, get_site=get_site)
    keyboard_override = parse_keyboard_override(site.get("keyboard_display_override"))
    keyboard = build_keyboard_display(site, override=keyboard_override)
    technical = build_technical_display(site, keyboard=keyboard)
    prior_history = build_prior_history_display(site, index=index)
    former_locations = build_former_location_display(site)
    remarks = build_remarks_display(site)
    links = build_links_display(site)
    badge = location.get("badge")
    return {
        "title": title,
        "title_auto": title_auto,
        "title_translation": title_translation,
        "title_translation_auto": title_translation_auto,
        "badge": badge,
        "subtitle": format_site_subtitle(
            country_code=site.get("country_code"),
            state_province=site.get("state_province"),
            bell_count=bell_count,
            installation_year=index.get("installation_year"),
            bourdon_pitch=index.get("bourdon_pitch") or site.get("bourdon_pitch"),
        ),
        "location": location,
        "schedule": schedule,
        "contact": contact,
        "carillonist": carillonist,
        "past_carillonists": past_carillonists,
        "keyboard": keyboard,
        "technical": technical,
        "prior_history": prior_history,
        "former_locations": former_locations,
        "remarks": remarks,
        "links": links,
    }
