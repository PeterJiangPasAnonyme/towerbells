"""Extract and normalize regional subdivisions from site location text."""

from __future__ import annotations

import re
import unicodedata

NL_PROVINCE_ALIASES: dict[str, str] = {
    "N.Brabant": "Noord-Brabant",
    "N.Holland": "Noord-Holland",
    "Z.Holland": "Zuid-Holland",
}

BE_PROVINCE_ALIASES: dict[str, str] = {
    "LiÃ¨ge (Luik)": "Liège",
    "LiÃ¨ge": "Liège",
    "Liege (Luik)": "Liège",
    "Liege": "Liège",
    "Brabant": "Brabant (unspecified)",  # non-Brussels only; Brussels handled in extract_be_province
    "Antwerpen": "Antwerp",
    "Oost-Vlaanderen": "East Flanders",
    "West-Vlaanderen": "West Flanders",
    "Vlaams-Brabant": "Flemish Brabant",
    "Brabant wallon": "Walloon Brabant",
    "Hainaut": "Hainaut",
    "Namur": "Namur",
    "Luxembourg": "Luxembourg",
    "Limburg": "Limburg",
}

# Towerbells.org historic Danish regions (Jylland / Sjælland / Fyn)
DK_REGION_FROM_TEXT: list[tuple[str, str]] = [
    (r"fyn\s+amt|,\s*fyn\b", "F"),
    (r"sudjylland|sønderjylland|midjylland|nordjylland|ringkøbing|århus\s+amt|arhus\s+amt|jylland", "J"),
    (r"københavn|kobenhavn|frederiksberg|københavns|holbæk|hillerød|sjælland|sjaelland", "S"),
]


def _fix_mojibake(text: str) -> str:
    if not text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def normalize_province_name(name: str) -> str:
    name = _fix_mojibake(name.strip())
    name = unicodedata.normalize("NFC", name)
    return name


def extract_nl_province(location_text: str) -> str | None:
    if not location_text:
        return None
    m = re.search(r",\s*([^,\n]+),\s*Netherlands\b", location_text, re.I)
    if not m:
        return None
    raw = normalize_province_name(m.group(1))
    return NL_PROVINCE_ALIASES.get(raw, raw)


def extract_be_province(location_text: str) -> str | None:
    if not location_text:
        return None
    m = re.search(r",\s*([^,\n]+),\s*Belgium\b", location_text, re.I)
    if not m:
        return None
    raw = normalize_province_name(m.group(1))
    # Brussels: towerbells.org lists historic "Brabant" for Bruxelles/Brussel
    if raw.lower() == "brabant" and re.search(
        r"bruxelles|brussel", location_text, re.I
    ):
        return "Brussels-Capital Region"
    return BE_PROVINCE_ALIASES.get(raw, raw)


def infer_dk_region(location_text: str) -> str | None:
    if not location_text:
        return None
    text = _fix_mojibake(location_text).lower()
    for pattern, code in DK_REGION_FROM_TEXT:
        if re.search(pattern, text, re.I):
            return code
    return None


def extract_province(country_code: str, location_text: str, existing: str = "") -> str | None:
    cc = (country_code or "").upper()
    if existing and cc not in ("NETHERLANDS", "BELGIUM"):
        return existing or None

    if cc == "NETHERLANDS":
        return extract_nl_province(location_text)
    if cc == "BELGIUM":
        return extract_be_province(location_text)
    if cc == "DENMARK" and not existing:
        return infer_dk_region(location_text)
    return existing or None
