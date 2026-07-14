"""Canonical instrument type labels from towerbells.org technical data."""

from __future__ import annotations

INSTRUMENT_TYPE_CANONICAL: dict[str, str] = {
    "traditional carillon": "Traditional carillon",
    "concert class carillon": "Concert class carillon",
    "non-traditional carillon": "Non-traditional carillon",
    "hybrid carillon": "Hybrid carillon",
    "travelling carillon": "Travelling carillon",
    "chime": "Chime",
    "ring": "Ring",
    "peal": "Peal",
    "bell tower": "Bell tower",
}


def normalize_instrument_type(value: str | None) -> str:
    if not value:
        return ""
    key = value.strip().lower()
    return INSTRUMENT_TYPE_CANONICAL.get(key, value.strip())
