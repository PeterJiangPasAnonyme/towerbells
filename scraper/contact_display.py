"""Structured contact display for carillon detail pages."""

from __future__ import annotations

import json
import re
from typing import Any

DOMAIN_RE = re.compile(
    r"\b(?:https?://|www\.)?[a-z0-9][\w.\-]*\.(?:com|org|net|edu|nl|de|uk|gov|be|fr|info)(?:/\S*)?\b",
    re.I,
)

UNKNOWN_RE = re.compile(r"^\s*\(?unknown\)?\.?\s*$", re.I)
HIDDEN_CONTACT_BADGES = frozenset({"Contact unknown"})

TITLE_HINTS = re.compile(
    r"\b(?:"
    r"Director|Mayor|President|Musician|Minister|Manager|Head of|Chair|Secretary|"
    r"Priest|Carillonist|Carillonneur|beiaardier|stadsbeiaardier|Sexton|co-chair|Music Director|Church Musician|Parish Priest|"
    r"Dean|Curator|Coordinator|Administrator|Officer|Marketing|Communications|"
    r"Music Performance|Parish|Music Ministries"
    r")\b",
    re.I,
)

ORG_HINTS = re.compile(
    r"\b(?:"
    r"Church|Foundation|Department|University|School|Center|Centre|Office|"
    r"Association|Bureau|Parochie|Stichting|Kerk|Congregation|Institute|Carillon|"
    r"Library|Hall|Presbytery|Secretariat|Committee|Corporation|Inc\.|Ltd\.|"
    r"Hotline|Bureau|Parish|Conservatory|Academy|Performing Arts|Visitors Bureau|"
    r"Alumni|Chancellor|Restoration|Campus|Convention"
    r")\b|"
    r"^St\.|^St\s|^First-|^Holy |^Our |^The |^Millennium |^Regional ",
    re.I,
)

ADDRESS_HINTS = re.compile(
    r"(?:"
    r"\bP\.?\s*O\.?\s*Box\b|"
    r"\bPostbus\b|"
    r"\b\d{1,5}[A-Za-z]?\s+(?:North|South|East|West|[NSEW]\.?)\s+\w+|"
    r"\b\d{1,5}(?:st|nd|rd|th)\s+(?:Street|St\.?|Avenue|Ave\.?|Drive|Dr\.?|Road|Rd\.?)\b|"
    r"\b\d{5}(?:-\d{4})?\b|"
    r"\b\d{4}\s+[A-Z]{2}\b|"
    r"\bD-\d{5}\b|"
    r"\b\d{3}/\d+\b|"
    r"(?:Street|St\.|Avenue|Ave\.|Drive|Dr\.|Road|Rd\.|Lane|Ln\.|Boulevard|Blvd\.|"
    r"Highway|Hwy\.|Route|Terrace|Straat|strasse|straße|weg|platz|Markt|Parade|"
    r"Parkway|Pkwy\.|Circle|Crescent|Close|Pennsylvania Avenue|Broad Street|"
    r"Locust Street|Clearfield Street|River Road|Magsaysay|Kelburn Road|"
    r"Indian Avenue|Washington Street|Corporation Street|Crab Street|"
    r"Woodlawn Avenue|Domplatz|Kerkplein|Grote Markt|Hauptstrasse|Broekhovensweg|"
    r"Stadhuisstraat|Groenmarktstraat|Dewey Hall|Ramón|Ramon Magsaysay"
    r")\b|"
    r"[A-Za-z\s\-']+,\s*[A-Z]{2}\s+\d{5}|"
    r"\bUnit\s+\d+\b|"
    r"\b\d+\s+[A-Z][a-z]+\s+(?:Avenue|Street|Road|Drive|Lane)\b"
    r")",
    re.I,
)

LOCALITY_HINTS = re.compile(
    r"(?:"
    r"[A-Za-z\s\-']+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?|"
    r"[A-Za-z\s\-']+,\s*[A-Z]{2}\b|"
    r"\b[A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2}\b|"
    r"\b\d{4}\s+[A-Z]{2}\b|"
    r"\bD-\d{5}\s+\w+|"
    r"\bDK-\d{4}\b|"
    r"\b\d{5}\s+\w+"
    r")",
    re.I,
)

PERSON_NAME_RE = re.compile(
    r"^[A-Z][\w'\-\.]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][\w'\-\.]+){0,2}$"
)


def parse_contact_override(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def normalize_email(raw: str) -> str | None:
    text = raw.strip().strip(".,;")
    if not text or re.match(r"^Webform\b", text, re.I):
        return None

    text = re.sub(r"\s*/@\s*/?\s*", "@", text)
    text = re.sub(r"\s+DOT\s*", ".", text, flags=re.I)
    text = re.sub(r"@\s+", "@", text)
    text = text.replace(" ", "")

    match = re.search(r"[\w.\-+]+@[\w.\-]+\.[A-Za-z]{2,}", text)
    if match:
        return match.group(0).lower()
    return None


def _phone_href(display: str) -> str:
    digits = re.sub(r"[^\d+]", "", display.replace("/", ""))
    return f"tel:{digits}" if digits else f"tel:{display.strip()}"


def _phone_display(kind: str, raw: str) -> str:
    cleaned = raw.strip(" ,;")
    kind = kind.upper()
    if kind == "F":
        return f"Fax: {cleaned}"
    if kind in {"C", "M"}:
        return f"Cell: {cleaned}"
    if kind == "H":
        return f"Home: {cleaned}"
    if kind == "W":
        return f"Work: {cleaned}"
    return cleaned


def _website_entry(raw: str, display: str | None = None) -> dict[str, str]:
    href = raw.strip().rstrip(".,;")
    if not re.match(r"https?://", href, re.I):
        href = f"https://{href.lstrip('/')}"
    label = display or raw.strip()
    if label.lower().startswith("webform"):
        label = "Website"
    return {"display": label, "href": href}


def _split_email_tokens(raw: str) -> list[str]:
    parts = re.split(r"\s+(?=[\w.\-+]+(?:/@/|@))", raw.strip())
    return [part.strip(" ,;") for part in parts if part.strip(" ,;")]


def _looks_like_address(line: str) -> bool:
    if ORG_HINTS.search(line) and not re.search(r"\d", line):
        return False
    if re.search(r"\bSt\.\s*[A-Z]", line) and not re.search(
        r"\b\d+\s+St\.?\b|\bSt\.\s*(?:Street|Ave|Rd|Lane|Dr)\b",
        line,
        re.I,
    ):
        return False
    if re.search(r"(?:kirche|kerk|church|parish|foundation|department)\b", line, re.I) and not re.search(
        r"\d", line
    ):
        return False
    return bool(ADDRESS_HINTS.search(line) or LOCALITY_HINTS.search(line))


def _looks_like_title_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped[0].islower():
        return True
    if TITLE_HINTS.search(stripped):
        return True
    if re.search(r"carillon|instructor|emeritus|beiaardier|effective \d", stripped, re.I):
        return True
    return bool(re.match(r"^(?:and|or)\s+", stripped, re.I) or re.match(r"^\(effective\b", stripped, re.I))


def _looks_like_person(line: str) -> bool:
    stripped = line.strip()
    if not stripped or _looks_like_address(stripped):
        return False
    if re.search(
        r"(?:kirche|kerk|church|parish|stiftung|stichting|foundation|department|academy|conservatory)\b",
        stripped,
        re.I,
    ) and "," not in stripped:
        return False
    if ORG_HINTS.search(stripped) and "," not in stripped:
        return False
    if re.match(r"^(?:Msgr\.|Rev\.|Dr\.|Mr\.|Mrs\.|Ms\.|Prof\.)\s", stripped, re.I):
        return True
    if "," in stripped:
        name_part, title_part = (part.strip() for part in stripped.split(",", 1))
        if ORG_HINTS.search(name_part) and not re.match(r"^(?:Msgr\.|Rev\.|Dr\.)", name_part, re.I):
            return False
        if TITLE_HINTS.search(title_part) or (
            name_part and not _looks_like_address(title_part) and len(name_part.split()) <= 4
        ):
            return bool(re.match(r"^[A-Z]", name_part))
    if PERSON_NAME_RE.match(stripped) and not ORG_HINTS.search(stripped):
        return len(stripped.split()) <= 4
    return False


def _extract_phones_from_line(line: str) -> tuple[str, list[dict[str, str]]]:
    phones: list[dict[str, str]] = []
    remaining = line
    for match in re.finditer(
        r"(?:^|\s)([TFCWHM]):\s*((?:.(?!\s[TFCWHM]:|\sE:))*.)",
        line,
        flags=re.I,
    ):
        kind = match.group(1).upper()
        raw_value = match.group(2).strip(" ,;")
        for part in re.split(r"\s+or\s+", raw_value):
            display_raw = part.strip(" ,;")
            if not display_raw:
                continue
            phones.append(
                {
                    "type": kind,
                    "display": _phone_display(kind, display_raw),
                    "href": _phone_href(display_raw),
                }
            )
    if phones:
        remaining = re.sub(
            r"(?:^|\s)[TFCWHM]:\s*(?:.(?!\s[TFCWHM]:|\sE:))*.",
            "",
            line,
            flags=re.I,
        ).strip(" ,;")
    return remaining, phones


def _extract_emails_from_line(line: str) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    emails: list[dict[str, str]] = []
    websites: list[dict[str, str]] = []
    match = re.search(r"(?:^|\s)E:\s*(.+)$", line, re.I)
    if not match:
        return line, emails, websites

    remaining = line[: match.start()].strip(" ,;")
    raw = match.group(1).strip()
    if re.match(r"^Webform\b", raw, re.I):
        url = re.sub(r"^Webform\s*[@,]\s*", "", raw, flags=re.I).strip()
        if url:
            websites.append(_website_entry(url, "Website"))
    else:
        for token in _split_email_tokens(raw):
            email = normalize_email(token)
            if email:
                emails.append({"display": email, "href": f"mailto:{email}"})
    return remaining, emails, websites


def _parse_block(block: str) -> dict[str, Any]:
    lines = [re.sub(r"\s+", " ", line.strip()) for line in block.splitlines() if line.strip()]

    phones: list[dict[str, str]] = []
    emails: list[dict[str, str]] = []
    websites: list[dict[str, str]] = []
    content_lines: list[str] = []

    index = 0
    while index < len(lines):
        line = lines[index]

        if re.match(r"^E:\s*Webform\s*@?\s*$", line, re.I) and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if re.match(r"(?:https?://|www\.)", next_line, re.I):
                websites.append(_website_entry(next_line, "Website"))
                index += 2
                continue

        remaining, line_phones = _extract_phones_from_line(line)
        phones.extend(line_phones)

        remaining, line_emails, line_websites = _extract_emails_from_line(remaining)
        emails.extend(line_emails)
        websites.extend(line_websites)

        if remaining and re.match(r"^(?:https?://|www\.)\S+$", remaining, re.I):
            websites.append(_website_entry(remaining, remaining))
            remaining = ""

        if remaining:
            content_lines.append(remaining)
        index += 1

    person_name: str | None = None
    person_title: str | None = None
    organization_lines: list[str] = []
    address_lines: list[str] = []

    line_index = 0
    while line_index < len(content_lines):
        line = content_lines[line_index]

        if person_name is None and _looks_like_person(line):
            if "," in line:
                name_part, title_part = (part.strip() for part in line.split(",", 1))
                person_name = name_part
                title_parts = [title_part] if title_part else []
            else:
                person_name = line.strip()
                title_parts = []

            line_index += 1
            while line_index < len(content_lines) and _looks_like_title_line(content_lines[line_index]):
                title_parts.append(content_lines[line_index].strip())
                line_index += 1

            if title_parts:
                person_title = " ".join(title_parts)
            continue

        if _looks_like_address(line):
            address_lines.append(line)
            line_index += 1
            while line_index < len(content_lines) and (
                _looks_like_address(content_lines[line_index])
                or LOCALITY_HINTS.search(content_lines[line_index])
            ):
                address_lines.append(content_lines[line_index].strip())
                line_index += 1
            continue

        organization_lines.append(line)
        line_index += 1

    organization = "\n".join(organization_lines).strip() or None

    if not person_name and organization_lines and not address_lines:
        organization = "\n".join(organization_lines).strip() or None
    elif not person_name and organization_lines and address_lines:
        organization = "\n".join(organization_lines).strip() or None

    if not person_name and not organization and content_lines:
        organization = "\n".join(content_lines).strip() or None
        address_lines = []

    return _finalize_entry(
        {
            "person_name": person_name,
            "person_title": person_title,
            "organization": organization,
            "address_lines": address_lines,
            "phones": phones,
            "emails": emails,
            "websites": websites,
        }
    )


def _finalize_entry(entry: dict[str, Any]) -> dict[str, Any]:
    organization = entry.get("organization")
    if organization and "\n" in organization:
        org_lines: list[str] = []
        extra_address: list[str] = []
        for line in (part.strip() for part in organization.splitlines() if part.strip()):
            if _looks_like_address(line):
                extra_address.append(line)
            elif not extra_address:
                org_lines.append(line)
            else:
                extra_address.append(line)
        entry["organization"] = "\n".join(org_lines) if org_lines else None
        if extra_address:
            entry["address_lines"] = (entry.get("address_lines") or []) + extra_address

    organization = entry.get("organization")
    if organization:
        domains = DOMAIN_RE.findall(organization)
        if domains:
            websites = entry.setdefault("websites", [])
            for domain in domains:
                websites.append(_website_entry(domain, domain))
            organization = DOMAIN_RE.sub("", organization)
            organization = re.sub(r"\n\s*\n", "\n", organization).strip()
            entry["organization"] = organization or None

    return entry


def _entry_has_content(entry: dict[str, Any]) -> bool:
    return bool(
        entry.get("person_name")
        or entry.get("person_title")
        or entry.get("organization")
        or entry.get("address_lines")
        or entry.get("phones")
        or entry.get("emails")
        or entry.get("websites")
    )


def _contact_has_content(result: dict[str, Any]) -> bool:
    badge = result.get("badge")
    if badge in HIDDEN_CONTACT_BADGES and not result.get("entries"):
        return False
    return bool(
        (badge and badge not in HIDDEN_CONTACT_BADGES)
        or result.get("entries")
        or result.get("prose")
    )


def _apply_override(result: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not override:
        return result

    if "mode" in override:
        result["mode"] = override["mode"]
    if "badge" in override:
        badge = override["badge"]
        result["badge"] = str(badge).strip() if badge else None
    if "entries" in override and isinstance(override["entries"], list):
        result["entries"] = override["entries"]
        if override["entries"]:
            result["mode"] = "structured"
            result["badge"] = None
    if "prose" in override:
        prose = override["prose"]
        result["prose"] = str(prose).strip() if prose else None
    if override.get("force_prose") and result.get("prose"):
        result["mode"] = "prose"
        result["entries"] = []

    result["has_content"] = _contact_has_content(result)
    return result


def build_contact_display(
    site: dict,
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = (site.get("contact") or "").strip()
    result: dict[str, Any]

    if UNKNOWN_RE.match(raw):
        result = {
            "mode": "badge",
            "badge": "Contact unknown",
            "entries": [],
            "prose": None,
            "has_content": False,
        }
    else:
        entries: list[dict[str, Any]] = []
        for block in re.split(r"\s*-\s*or\s*-", raw):
            block = block.strip()
            if not block:
                continue
            entry = _parse_block(block)
            if _entry_has_content(entry):
                entries.append(entry)

        if entries:
            result = {
                "mode": "structured",
                "badge": None,
                "entries": entries,
                "prose": None,
                "has_content": True,
            }
        elif raw:
            result = {
                "mode": "prose",
                "badge": None,
                "entries": [],
                "prose": raw,
                "has_content": True,
            }
        else:
            result = {
                "mode": "prose",
                "badge": None,
                "entries": [],
                "prose": None,
                "has_content": False,
            }

    result = _apply_override(result, override)
    result["has_content"] = _contact_has_content(result)
    return result


def contact_for_editor(display: dict[str, Any]) -> dict[str, Any]:
    """Return editable contact JSON with all keys present."""
    if not display:
        return {
            "mode": "prose",
            "badge": None,
            "entries": [],
            "prose": None,
            "force_prose": False,
        }
    return {
        "mode": display.get("mode") or "prose",
        "badge": display.get("badge"),
        "entries": display.get("entries") or [],
        "prose": display.get("prose"),
        "force_prose": bool(display.get("force_prose")),
    }
