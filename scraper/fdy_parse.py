"""Parse towerbells.org bellfounder/year (fdy) index pages."""

from __future__ import annotations

import re

from scraper.text import decode_html_text

SITE_LINK_RE = re.compile(
    r'<A\s+NAME=(\w+)\s+HREF=(\w+\.HTM)[^>]*>(.*?)</A>\s*(.*?)(?=<A\s+NAME=|\Z)',
    re.I | re.S,
)
SECTION_HEADER_RE = re.compile(
    r'<h3>\s*<A\s+NAME=[^>]+>(.*?)</A>(?:\s*,\s*(.*?))?\s*</h3>',
    re.I | re.S,
)
ITALIC_BLOCK_RE = re.compile(r"<[iI]>(.*?)</[iI]>", re.S)
CAST_PREFIX_RE = re.compile(
    r"^(?:cast\s+(?:mainly|here)\s+by|cast\s+for,?\s+and\s+inscribed\s+as\s+by,?\s*|"
    r"made\s+by|cast\s+by)\s+(.+)$",
    re.I | re.S,
)
MADE_BY_AT_RE = re.compile(r"^(.+?),\s*at\s+the\b", re.I | re.S)

_SKIP_SECTIONS = {"misc", "blank", "miscellaneous"}
_LOCATION_TAIL_WORDS = {
    "usa",
    "canada",
    "france",
    "belgium",
    "netherlands",
    "germany",
    "england",
    "inc",
    "inc.",
}


def _page_stem(page_filename: str) -> str:
    return page_filename.rsplit(".", 1)[0].upper()


def _section_founder(header_link_text: str, header_suffix: str | None) -> str | None:
    name = decode_html_text(header_link_text)
    name = re.sub(r"<br\s*/?>", " ", name, flags=re.I)
    name = re.sub(r"\s+", " ", name).strip()
    lowered = name.lower()
    if not name or "miscellaneous" in lowered or lowered.startswith("bellfoundry unknown"):
        return None
    if lowered.startswith("miscellaneous"):
        return None
    if header_suffix:
        return name.split(",", 1)[0].strip()
    if "," in name:
        return name.split(",", 1)[0].strip()
    return name


def strip_founder_location(name: str) -> str:
    """Remove trailing place names from a miscellaneous founder label."""
    text = decode_html_text(name)
    text = re.sub(r"\s+", " ", text).strip().rstrip("?")
    text = re.sub(r"\([^)]*\)$", "", text).strip()

    made_by_at = MADE_BY_AT_RE.match(text)
    if made_by_at:
        text = made_by_at.group(1).strip()

    of_parts = re.split(r"\s+of\s+", text, maxsplit=1, flags=re.I)
    if len(of_parts) == 2 and not re.search(r"\d", of_parts[1]):
        text = of_parts[0].strip()

    parts = [part.strip() for part in text.split(",") if part.strip()]
    while len(parts) > 1:
        last = parts[-1]
        last_lower = last.lower()
        if re.match(r"^\d{4}", last):
            parts.pop()
            continue
        if last_lower in _LOCATION_TAIL_WORDS:
            parts.pop()
            continue
        if re.search(r"\b(?:USA|Ohio|Texas|California|Pennsylvania|Karlsruhe)\b", last, re.I):
            parts.pop()
            continue
        if " de " in last_lower or " sur " in last_lower or " du " in last_lower:
            parts.pop()
            continue
        if len(last.split()) <= 2 and len(parts) >= 2:
            # Trailing place after founder name: "Heudebert, Bergues", "Bernard, Lorraine".
            if last_lower not in {"ainé", "aine", "françois", "francois", "jr.", "jr"}:
                parts.pop()
                continue
        break

    return ", ".join(parts).strip()


def _extract_cast_by_names(block_html: str) -> list[str]:
    names: list[str] = []
    for match in ITALIC_BLOCK_RE.finditer(block_html):
        raw = decode_html_text(match.group(1))
        raw = re.sub(r"\s+", " ", raw).strip()
        if not raw:
            continue
        cast_match = CAST_PREFIX_RE.match(raw)
        if not cast_match:
            continue
        founder = strip_founder_location(cast_match.group(1))
        if founder:
            names.append(founder)
    return names


def parse_fdy_page(html: str) -> list[dict[str, object]]:
    """
    Return one record per site link on a foundry index page.

    Each record includes the page stem, list site_id, section founder (if any),
    and any miscellaneous cast-by names in the entry block.
    """
    records: list[dict[str, object]] = []
    current_section: str | None = None

    for section_match in SECTION_HEADER_RE.finditer(html):
        header_text = section_match.group(1)
        header_suffix = section_match.group(2)
        section_name = section_match.group(0)
        anchor = re.search(r'NAME="?([^">]+)"?', section_match.group(0), re.I)
        anchor_id = (anchor.group(1) if anchor else header_text).lower()
        if anchor_id in _SKIP_SECTIONS or "misc" in anchor_id:
            current_section = None
        else:
            current_section = _section_founder(header_text, header_suffix)

        section_start = section_match.end()
        next_section = SECTION_HEADER_RE.search(html, section_start)
        section_end = next_section.start() if next_section else len(html)
        section_html = html[section_start:section_end]

        for site_match in SITE_LINK_RE.finditer(section_html):
            site_id = site_match.group(1).upper()
            page_stem = _page_stem(site_match.group(2))
            block_html = site_match.group(4)
            cast_names = _extract_cast_by_names(block_html)
            founders: list[str] = []
            if cast_names:
                founders.extend(cast_names)
            elif current_section:
                founders.append(current_section)

            records.append(
                {
                    "site_id": site_id,
                    "page_stem": page_stem,
                    "founders": founders,
                    "section": current_section,
                }
            )

    return records


def aggregate_founders_by_page(records: list[dict[str, object]]) -> dict[str, list[str]]:
    """Merge founders for the same underlying site page (.HTM)."""
    grouped: dict[str, list[str]] = {}
    seen: dict[str, set[str]] = {}

    for record in records:
        page_stem = str(record["page_stem"])
        founders = [str(name) for name in record.get("founders") or [] if name]
        if not founders:
            continue
        seen.setdefault(page_stem, set())
        bucket = grouped.setdefault(page_stem, [])
        for founder in founders:
            if founder not in seen[page_stem]:
                seen[page_stem].add(founder)
                bucket.append(founder)

    return grouped


def normalize_fdy_founder(name: str) -> str:
    from scraper.bellfounders import canonical_founder_name

    return canonical_founder_name(name) or name


def load_founders_by_page_from_html_pages(pages: dict[str, str]) -> dict[str, list[str]]:
    """Parse multiple regional fdy pages and merge founders by underlying .HTM page."""
    all_records: list[dict[str, object]] = []
    for html in pages.values():
        all_records.extend(parse_fdy_page(html))
    grouped = aggregate_founders_by_page(all_records)
    return {
        page: [normalize_fdy_founder(name) for name in founders]
        for page, founders in grouped.items()
    }
