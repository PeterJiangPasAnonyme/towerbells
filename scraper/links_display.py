"""Display helpers for the Links section."""

from __future__ import annotations

import html
import re
from typing import Any

from scraper.config import RAW_HTML_DIR
from scraper.parse_site import SECTION_RE
from scraper.text import clean_html_fragment, decode_html_text, reflow_wrapped_prose

ANCHOR_RE = re.compile(
    r'(?is)<a\s+[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>'
)
BLOCK_SPLIT_RE = re.compile(r"(?i)(?:<p\s*>|</p>|<br\s*/?>|\n\s*\n+)")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
WRAPPER_TAG_RE = re.compile(r"(?i)</?(?:dl|dd|p)\b[^>]*>")


def _is_internal_towerbells_href(href: str) -> bool:
    href = (href or "").strip()
    if not href or href == "#":
        return True

    lowered = href.lower()
    if lowered.startswith("mailto:"):
        return False
    if lowered.startswith(("http://", "https://")):
        return "towerbells.org" in lowered or "towerbells.com" in lowered

    # Relative towerbells.org navigation pages and site cross-links.
    if re.search(r"\.html?$", href, re.I):
        return True
    if re.match(r"^[A-Za-z0-9]{2}[A-Za-z0-9]{5,7}\.htm", href, re.I):
        return True
    if href.startswith(("../", "./", "/")):
        return True
    return True


def _extract_links_raw_html(page_html: str) -> str:
    for match in SECTION_RE.finditer(page_html):
        if match.group(1).strip().lower() == "links":
            return match.group(2)
    return ""


def _load_page_html(site: dict[str, Any]) -> str:
    filename = (site.get("page_filename") or f"{site.get('site_id', '')}.HTM").strip()
    if not filename:
        return ""
    path = RAW_HTML_DIR / filename.lower()
    if not path.is_file():
        alt = RAW_HTML_DIR / f"{site.get('site_id', '').lower()}.htm"
        path = alt if alt.is_file() else path
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _split_link_blocks(raw_html: str) -> list[str]:
    text = COMMENT_RE.sub("", raw_html)
    text = WRAPPER_TAG_RE.sub("\n", text)
    blocks: list[str] = []
    for chunk in BLOCK_SPLIT_RE.split(text):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk in {"-->", "--"}:
            continue
        blocks.append(chunk)
    return blocks


def _block_has_only_internal_links(block_html: str) -> bool:
    hrefs = [match.group(1) for match in ANCHOR_RE.finditer(block_html)]
    if not hrefs:
        return False
    return all(_is_internal_towerbells_href(href) for href in hrefs)


def _escape_text(text: str) -> str:
    return html.escape(text, quote=True)


def _block_to_display_html(block_html: str) -> str:
    parts: list[str] = []
    pos = 0
    for match in ANCHOR_RE.finditer(block_html):
        before = clean_html_fragment(block_html[pos : match.start()])
        if before:
            parts.append(_escape_text(before))

        href = decode_html_text(match.group(1).strip())
        label = clean_html_fragment(match.group(2))
        if not label:
            pos = match.end()
            continue

        if _is_internal_towerbells_href(href):
            parts.append(_escape_text(label))
        else:
            parts.append(
                f'<a href="{_escape_text(href)}" target="_blank" rel="noopener noreferrer">{_escape_text(label)}</a>'
            )
        pos = match.end()

    tail = clean_html_fragment(block_html[pos:])
    if tail:
        parts.append(_escape_text(tail))

    combined = "".join(parts)
    return _normalize_link_spacing(combined)


def _normalize_link_spacing(text: str) -> str:
    text = re.sub(r"(\w)(<a\b)", r"\1 \2", text)
    text = re.sub(r"(</a>)(\w)", r"\1 \2", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _reflow_display_paragraph(text: str) -> str:
    """Join source line wraps; break where a source line ended with a period."""
    if not text:
        return ""
    if "<a " in text:
        # Preserve anchor markup; only normalize whitespace.
        return _normalize_link_spacing(text)

    reflowed = reflow_wrapped_prose(text)
    if "\n\n" not in reflowed:
        return reflowed.strip()
    return reflowed.replace("\n\n", "<br><br>")


def build_links_display(site: dict[str, Any]) -> dict[str, Any]:
    page_html = _load_page_html(site)
    raw = _extract_links_raw_html(page_html) if page_html else ""

    paragraphs: list[dict[str, str]] = []
    for block in _split_link_blocks(raw):
        if _block_has_only_internal_links(block):
            continue
        display_html = _block_to_display_html(block)
        if not display_html:
            continue
        display_html = _reflow_display_paragraph(display_html)
        if display_html:
            paragraphs.append({"html": display_html})

    return {
        "has_content": bool(paragraphs),
        "paragraphs": paragraphs,
    }
