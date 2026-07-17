"""Canonical instrument type labels from towerbells.org technical data."""

from __future__ import annotations

INSTRUMENT_TYPE_CANONICAL: dict[str, str] = {
    "traditional carillon": "Traditional Carillon",
    "concert class carillon": "Concert Class Carillon",
    "non-traditional carillon": "Non-Traditional Carillon",
    "hybrid carillon": "Hybrid Carillon",
    "travelling carillon": "Travelling Carillon",
    "chime": "Chime",
    "ring": "Ring",
    "peal": "Peal",
    "bell tower": "Bell Tower",
}


def normalize_instrument_type(value: str | None) -> str:
    if not value:
        return ""
    key = value.strip().lower()
    return INSTRUMENT_TYPE_CANONICAL.get(key, value.strip())
