"""Display helpers for the Remarks section."""

from __future__ import annotations

from typing import Any

from scraper.text import normalize_remarks_reference, reflow_wrapped_prose


def build_remarks_display(site: dict[str, Any]) -> dict[str, Any]:
    raw = (site.get("remarks") or "").strip()
    if not raw:
        return {"has_content": False, "paragraphs": []}

    text = reflow_wrapped_prose(raw)
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    return {
        "has_content": bool(paragraphs),
        "paragraphs": paragraphs,
    }
