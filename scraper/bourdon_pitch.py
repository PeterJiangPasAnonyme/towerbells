"""Parse and normalize bourdon (heaviest bell) pitch names."""

from __future__ import annotations

import re

from scraper.text import decode_html_text

BOURDON_PITCH_ORDER: list[str] = [
    "C",
    "C#",
    "D",
    "D#",
    "E",
    "F",
    "F#",
    "G",
    "G#",
    "A",
    "A#",
    "B",
]

_FLAT_TO_SHARP = {
    "DB": "C#",
    "EB": "D#",
    "GB": "F#",
    "AB": "G#",
    "BB": "A#",
    "CB": "B",
}

_PITCH_PATTERN = re.compile(
    r"(?:^|(?<=[^A-Za-z#b]))"
    r"(A#|Bb|B|C#|Db|C|D#|Eb|D|E|F#|Gb|F|G#|Ab|G|A)"
    r"(?![A-Za-z#b])",
    re.I,
)


def normalize_pitch_text(value: str | None) -> str:
    if not value:
        return ""
    text = decode_html_text(value)
    text = text.replace("♯", "#").replace("♭", "b")
    return re.sub(r"\s+", " ", text).strip()


def canonical_bourdon_pitch(value: str | None) -> str:
    """Normalize a pitch token to sharp spelling (Db -> C#)."""
    pitch = normalize_pitch_text(value).upper().replace(" ", "")
    if not pitch:
        return ""
    if pitch in {p.upper() for p in BOURDON_PITCH_ORDER}:
        return pitch if "#" in pitch else pitch[0]
    return _FLAT_TO_SHARP.get(pitch, pitch)


def parse_bourdon_pitch(heaviest_pitch: str | None) -> str:
    """Extract canonical bourdon pitch from heaviest-bell text."""
    text = normalize_pitch_text(heaviest_pitch)
    if not text:
        return ""
    if re.search(r"\bunknown\b", text, re.I):
        return ""

    match = _PITCH_PATTERN.search(text)
    if not match:
        return ""

    raw = match.group(1)
    if raw.upper() == "BB":
        return "A#"
    return canonical_bourdon_pitch(raw)


def sort_bourdon_pitch_facets(items: list[dict]) -> list[dict]:
    order = {pitch: index for index, pitch in enumerate(BOURDON_PITCH_ORDER)}

    def sort_key(item: dict) -> tuple[int, str]:
        value = item.get("value") or ""
        return (order.get(value, len(order)), value)

    return sorted(items, key=sort_key)
