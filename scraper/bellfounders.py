"""Bellfounder string helpers."""

from __future__ import annotations

import re

from scraper.text import decode_html_text

MIN_FOUNDER_FACET_COUNT = 5

_FOUNDER_ALIASES = {
    "meeks": "Meeks, Watson & Co",
    "watson": "Meeks, Watson & Co",
    "meeks,watson": "Meeks, Watson & Co",
    "meeks & watson": "Meeks, Watson & Co",
    "meeks, watson": "Meeks, Watson & Co",
    "meeks, watson & co": "Meeks, Watson & Co",
    "vanbergen": "VanBergen",
    "vanaerschodt": "Van Aerschodt",
    "vandengheyn": "Vanden Gheyn",
    "van den gheyn": "Vanden Gheyn",
    "vanbergen bellfoundries": "VanBergen",
    "vanbergen bellfoundries, inc": "VanBergen",
    "vanbergen bellfoundries, inc.": "VanBergen",
    "de haze": "De Haze",
    "noorden & degrave": "Noorden & DeGrave",
}

# Initials abbreviations used on towerbells.org (e.g. P&F, G&J).
_FOUNDER_ABBREVIATIONS = {
    "a&f": "Alexis & François Jolly",
    "b&e": "Borchard & Eckhof",
    "g&j": "Gillett & Johnston",
    "m&c": "Meeks, Watson & Co",
    "m&w": "Meeks, Watson & Co",
    "n&d": "Noorden & DeGrave",
    "p&f": "Petit & Fritsen",
    "w&j": "Willem & Jaspar Moer",
}


def _founder_alias_key(name: str) -> str:
    return re.sub(r"\s*,\s*", ",", name.strip().lower())


def _apply_founder_alias(name: str) -> str:
    return _FOUNDER_ALIASES.get(_founder_alias_key(name), name)


def _normalize_founder_abbrev_key(name: str) -> str:
    text = name.strip().lower()
    text = re.sub(r"\s*&\s*", "&", text)
    return text.rstrip(".")


def _expand_founder_abbreviation(name: str) -> str:
    """Expand towerbells-style initials abbreviations such as P&F or G&J."""
    key = _normalize_founder_abbrev_key(name)
    if key in _FOUNDER_ABBREVIATIONS:
        return _FOUNDER_ABBREVIATIONS[key]
    return name


def _strip_founder_years(name: str) -> str:
    name = re.sub(r",?\s*cast\s+in\s+\d{4}.*$", "", name, flags=re.I)
    name = re.sub(r"\s*\(\d+\s+in\s+\d{4}\)", "", name, flags=re.I)
    name = re.sub(r"\s*\(except for \d+\)", "", name, flags=re.I)
    name = re.sub(r",?\s*in\s+\d{4}(?:\s*&\s*\d{4})?", "", name, flags=re.I)
    name = re.sub(r"\s*\(\d+\)$", "", name)
    return re.sub(r"\s+", " ", name).strip(" ,;")


def _merge_founder_family(name: str) -> str:
    """Merge known founder-family variants to a single canonical label."""
    key = _founder_alias_key(name)

    if re.fullmatch(r"(?:[a-z]\.|jacob\s+)?waghevens", key):
        return "Waghevens"

    if re.fullmatch(r"(?:guillelmus\s+|willem\s+)?witlockx", key):
        return "Witlockx"

    if re.fullmatch(
        r"claes\s+noorden\s*&\s*j\.a\.\s*degrave|n\.?\s*noorden\s*&\s*j\.a\.\s*degrave|noorden\s*&\s*degrave|j\.a\.\s*degrave|n\.?\s*noorden",
        key,
    ):
        return "Noorden & DeGrave"

    if re.fullmatch(r"a\.-f\.\s*vanden\s+gheyn", key) or key == "vanden gheyn":
        return "Vanden Gheyn"

    if " and " not in name.lower() and re.search(r"vanden\s+gheyn|van\s+den\s+gheyn", name, re.I):
        return "Vanden Gheyn"

    if re.fullmatch(r"(?:a\.-l\.-j\.\s+)?van\s+aerschodt", key):
        return "Van Aerschodt"

    return name


def normalize_founder_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", decode_html_text(value)).strip()


def canonical_founder_name(value: str | None) -> str:
    """Strip year annotations and merge known founder-family variants."""
    name = normalize_founder_text(value)
    if not name:
        return ""

    name = _expand_founder_abbreviation(name)
    name = _strip_founder_years(name)
    name = _merge_founder_family(name)
    return _apply_founder_alias(name)


def _expand_founder_part(part: str) -> list[str]:
    text = normalize_founder_text(part)
    if not text:
        return []

    if re.search(r"\s+and\s+", text, re.I):
        subparts = re.split(r"\s+and\s+", text, flags=re.I)
        if len(subparts) >= 2:
            names: list[str] = []
            for subpart in subparts:
                name = canonical_founder_name(subpart)
                if name:
                    names.append(name)
            if names:
                return names

    name = canonical_founder_name(text)
    return [name] if name else []


def split_founder_parts(value: str | None, *, canonical: bool = True) -> list[str]:
    text = normalize_founder_text(value)
    if not text:
        return []

    parts: list[str] = []
    seen: set[str] = set()
    for part in text.split(";"):
        chunk = part.strip()
        if not chunk:
            continue
        expanded = _expand_founder_part(chunk) if canonical else [normalize_founder_text(chunk)]
        for name in expanded:
            if not name:
                continue
            if canonical:
                name = canonical_founder_name(name)
            if name and name not in seen:
                seen.add(name)
                parts.append(name)
    return parts


def join_founder_parts(parts: list[str]) -> str:
    return "; ".join(canonical_founder_name(part) for part in parts if part)


def canonicalize_founder_field(value: str | None) -> str:
    return join_founder_parts(split_founder_parts(value))
