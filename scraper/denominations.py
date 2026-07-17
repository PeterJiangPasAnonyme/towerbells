"""Display labels for towerbells.org denomination groupings."""

from __future__ import annotations

EXCLUDED_DENOMINATIONS = {
    "Denomination unknown",
    "Denomination not applicable",
}


def normalize_denomination(value: str | None, country_code: str | None = None) -> str | None:
    if not value:
        return None
    label = value.strip()
    if label in EXCLUDED_DENOMINATIONS:
        return None
    if label == "Episcopal (USA) or Anglican (Canada)":
        return "Anglican" if country_code == "CANADA" else "Episcopal"
    return label
