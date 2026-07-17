"""Parse towerbells.org grouped list pages (denom, instype, kr)."""

from __future__ import annotations

import re

from scraper.text import decode_html_text

SITE_LINE_RE = re.compile(r"<A\s+NAME=(\w+)\s+HREF=(\w+\.HTM)", re.I)
GROUP_HEADER_RE = re.compile(r"Group\s+(\d+[a-z]?\+?-?)", re.I)
SECTION_TITLE_RE = re.compile(r"<A\s+NAME=[^>]+>([^<]+)</A>", re.I)


def parse_grouped_list_page(html: str, *, list_type: str | None = None) -> dict[str, str]:
    """Map site_id -> current section label from denom/instype/kr list pages."""
    mapping: dict[str, str] = {}
    current_group = "Unknown"

    for line in html.splitlines():
        site_match = SITE_LINE_RE.search(line)

        if list_type == "kr":
            if "Group " in line and not site_match:
                group_match = GROUP_HEADER_RE.search(line)
                if group_match:
                    current_group = f"Group {group_match.group(1)}"
                    continue
        elif list_type in {"denom", "instype"}:
            if re.search(r"<h2\b", line, re.I) and not site_match:
                title_match = SECTION_TITLE_RE.search(line)
                if title_match:
                    label = decode_html_text(title_match.group(1).strip())
                    if label:
                        current_group = label
                    continue

        if site_match:
            mapping[site_match.group(1).upper()] = current_group

    return mapping
