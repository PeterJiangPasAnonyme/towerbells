"""Split towerbells Technical data prose into preamble, prior history, and footer."""

from __future__ import annotations

import re

PRIOR_HISTORY_MARKER_RE = re.compile(r"\bPrior history\s*:", re.I)
FOOTER_START_RE = re.compile(
    r"\b(?:Auxiliary mechanisms\s*:|Tower details|Year of latest technical information source)",
    re.I,
)


def find_footer_start(text: str, from_index: int = 0) -> int | None:
    match = FOOTER_START_RE.search(text, from_index)
    return match.start() if match else None


def split_technical_sections(text: str | None) -> tuple[str, str, str]:
    """Return (preamble, prior_history, footer) from raw Technical data text."""
    if not text or not str(text).strip():
        return "", "", ""

    body = str(text)
    history_match = PRIOR_HISTORY_MARKER_RE.search(body)
    if not history_match:
        footer_start = find_footer_start(body, 0)
        if footer_start is None:
            return body.strip(), "", ""
        return body[:footer_start].strip(), "", body[footer_start:].strip()

    preamble = body[: history_match.start()].strip()
    content_start = history_match.end()
    footer_start = find_footer_start(body, content_start)
    if footer_start is None:
        return preamble, body[content_start:].strip(), ""

    prior_history = body[content_start:footer_start].strip()
    footer = body[footer_start:].strip()
    return preamble, prior_history, footer


def technical_display_text(text: str | None) -> str:
    """Preamble plus footer — excludes the prior-history block."""
    preamble, _, footer = split_technical_sections(text)
    if preamble and footer:
        return f"{preamble}\n\n{footer}"
    return preamble or footer
