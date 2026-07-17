"""Display labels for towerbells.org institution type groupings."""

from __future__ import annotations

INSTITUTION_TYPE_LABELS: dict[str, str] = {
    "Churches, cathedrals, convents and seminaries": "Religious Institutions",
    "University/College/School": "Educational Institutions",
    "Public": "Public Institutions",
    "Business": "Businesses",
    "Estate or foundation": "Estates & Foundations",
    "Monument or memorial structure": "Monuments & Memorials",
}

INSTITUTION_TYPES_WITH_DENOMINATION: set[str] = {
    "Religious Institutions",
    "Educational Institutions",
}


def normalize_institution_type(value: str | None) -> str | None:
    if not value:
        return None
    return INSTITUTION_TYPE_LABELS.get(value.strip(), value.strip())
