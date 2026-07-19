"""Structured carillonist display for carillon detail pages."""

from __future__ import annotations

import json
import re
from typing import Any

from scraper.contact_display import _entry_has_content, _parse_block
from scraper.person_sections import person_section_display_title, resolve_person_sections_for_site

CERT_A_RE = re.compile(r"\(A\)|\(Associate Carillonneur\)", re.I)
CERT_C_RE = re.compile(r"\(C\)|\(Carillonneur\)|\(Certified Carillonneur\)", re.I)
CERT_STRIP_RE = re.compile(
    r"\s*\(A\)|\(C\)|\(Carillonneur\)|\(Certified Carillonneur\)|\(Associate Carillonneur\)\s*",
    re.I,
)

HIDDEN_RE = re.compile(
    r"(?:"
    r"^\s*\(?unknown\)?\.?\s*$|"
    r"^\s*\(none\)\s*$|"
    r"position vacant|"
    r"vacant from|"
    r"\(vacant\)|"
    r"applications wanted|"
    r"none appointed"
    r")",
    re.I,
)


def parse_carillonist_override(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def _should_hide(raw: str) -> bool:
    text = raw.strip()
    if not text:
        return True
    return bool(HIDDEN_RE.search(text))


def _extract_cert_from_text(text: str | None) -> tuple[str | None, str | None]:
    if not text:
        return None, None

    cert = None
    if CERT_A_RE.search(text):
        cert = "Associate Carillonneur"
    elif CERT_C_RE.search(text):
        cert = "Certified Carillonneur"

    cleaned = CERT_STRIP_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;")
    return cleaned or None, cert


def _format_entry(entry: dict[str, Any]) -> dict[str, Any]:
    cert: str | None = None

    name, name_cert = _extract_cert_from_text(entry.get("person_name"))
    if name_cert:
        cert = name_cert

    title, title_cert = _extract_cert_from_text(entry.get("person_title"))
    if title_cert and not cert:
        cert = title_cert

    organization = entry.get("organization")
    if organization:
        organization = organization.replace("\n", " ")
        organization, org_cert = _extract_cert_from_text(organization)
        if org_cert and not cert:
            cert = org_cert

    return {
        "person_name": name,
        "cert_label": cert,
        "person_title": title,
        "organization": organization,
        "address_lines": entry.get("address_lines") or [],
        "phones": entry.get("phones") or [],
        "emails": entry.get("emails") or [],
        "websites": entry.get("websites") or [],
    }


def _apply_override(result: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not override:
        return result

    if "mode" in override:
        result["mode"] = override["mode"]
    if "entries" in override:
        if isinstance(override["entries"], list):
            result["entries"] = override["entries"]
            if override["entries"]:
                result["mode"] = "structured"
        else:
            result["entries"] = []
    if "prose" in override:
        prose = override["prose"]
        result["prose"] = str(prose).strip() if prose else None
    if override.get("force_prose") and result.get("prose"):
        result["mode"] = "prose"
        result["entries"] = []

    result["has_content"] = bool(result.get("entries") or result.get("prose"))
    return result


def build_carillonist_display(
    site: dict,
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved = resolve_person_sections_for_site(site)
    raw = resolved.current_text.strip()
    title = person_section_display_title(
        resolved.current_label,
        role="current",
        instrument_type=site.get("instrument_type"),
        technical_data=site.get("technical_data"),
    )
    result: dict[str, Any]

    if _should_hide(raw):
        result = {
            "mode": "hidden",
            "entries": [],
            "prose": None,
            "has_content": False,
            "title": title,
        }
    else:
        entries: list[dict[str, Any]] = []
        for block in re.split(r"\s*-\s*and\s*-", raw):
            block = block.strip()
            if not block:
                continue
            entry = _format_entry(_parse_block(block))
            if _entry_has_content(entry):
                entries.append(entry)

        if entries:
            result = {
                "mode": "structured",
                "entries": entries,
                "prose": None,
                "has_content": True,
                "title": title,
            }
        elif raw:
            prose, _ = _extract_cert_from_text(raw)
            result = {
                "mode": "prose",
                "entries": [],
                "prose": prose or raw,
                "has_content": True,
                "title": title,
            }
        else:
            result = {
                "mode": "hidden",
                "entries": [],
                "prose": None,
                "has_content": False,
                "title": title,
            }

    return _apply_override(result, override)


def carillonist_for_editor(display: dict[str, Any]) -> dict[str, Any]:
    if not display or not display.get("has_content"):
        return {}
    payload: dict[str, Any] = {"mode": display.get("mode") or "structured"}
    if display.get("entries"):
        payload["entries"] = display["entries"]
    if display.get("prose"):
        payload["prose"] = display["prose"]
    return payload
