"""Decode HTML entities and fix common encoding issues in towerbells text."""

from __future__ import annotations

import html
import json
import re
from typing import Any

_EXTRA_MOJIBAKE = {
    "BollÃ©e": "Bollée",
    "BollÃ©": "Bollé",
}


def fix_mojibake(text: str) -> str:
    """Recover UTF-8 text that was misread as Latin-1."""
    if not text or ("Ã" not in text and "Â" not in text):
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass

    out: list[str] = []
    index = 0
    while index < len(text):
        if index + 1 < len(text):
            first, second = ord(text[index]), ord(text[index + 1])
            if 0xC0 <= first <= 0xFF and 0x80 <= second <= 0xFF:
                try:
                    out.append(bytes([first, second]).decode("utf-8"))
                    index += 2
                    continue
                except UnicodeDecodeError:
                    pass
        out.append(text[index])
        index += 1
    return "".join(out)


def decode_html_text(value: str | None) -> str:
    """Turn '&Eacute;glise' into 'Église' and fix common mojibake."""
    if not value:
        return ""
    text = html.unescape(value)
    text = text.replace("\xa0", " ")
    text = fix_mojibake(text)
    for bad, good in _EXTRA_MOJIBAKE.items():
        text = text.replace(bad, good)
    return text


def clean_html_fragment(text: str) -> str:
    """Strip HTML markup and decode entities from a towerbells.org fragment."""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = decode_html_text(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def decode_deep(value: Any) -> Any:
    if isinstance(value, str):
        return decode_html_text(value)
    if isinstance(value, dict):
        return {key: decode_deep(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode_deep(item) for item in value]
    return value


def decode_json_text_values(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return decode_html_text(raw)
    return json.dumps(decode_deep(data), ensure_ascii=False)


def needs_text_decode(value: str | None) -> bool:
    if not value:
        return False
    decoded = decode_html_text(value)
    return decoded != value


def decode_if_changed(value: str | None) -> tuple[str, bool]:
    if value is None:
        return "", False
    decoded = decode_html_text(value)
    if value == decoded:
        return value, False
    return decoded, True


def reflow_wrapped_prose(text: str | None) -> str:
    """Join HTML line wraps and break paragraphs where a source line ended with a period."""
    if not text or not str(text).strip():
        return ""

    paragraphs: list[str] = []
    buffer = ""
    for line in str(text).splitlines():
        piece = line.strip()
        if not piece:
            continue
        buffer = f"{buffer} {piece}".strip() if buffer else piece
        if piece.endswith("."):
            paragraphs.append(buffer)
            buffer = ""
    if buffer:
        paragraphs.append(buffer)
    return "\n\n".join(paragraphs)


def normalize_remarks_reference(text: str | None) -> str:
    """Towerbells.org cites Remarks above Technical data; our UI shows Remarks below."""
    if not text:
        return ""
    return re.sub(r"Remarks above", "Remarks below", str(text), flags=re.I)


_SAINT_PREFIXES = ("St", "Ste", "Sv", "Sct", "SS", "S")

_SMALL_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "as",
        "at",
        "au",
        "aux",
        "bij",
        "but",
        "by",
        "de",
        "des",
        "du",
        "en",
        "et",
        "for",
        "from",
        "in",
        "into",
        "near",
        "nor",
        "of",
        "on",
        "onto",
        "op",
        "or",
        "over",
        "part",
        "der",
        "den",
        "the",
        "to",
        "und",
        "van",
        "via",
        "vs",
        "was",
        "with",
        "between",
        "formerly",
        "opposite",
        "beside",
        "known",
    }
)

_ROMAN_NUMERALS = frozenset({"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"})
_ACRONYM_RE = re.compile(r"^[A-Z0-9]{2,}(?:\.[A-Z0-9]+)*\.?$")
_INITIAL_RE = re.compile(r"^[A-Z]\.$")
_SINGLE_LETTER_INITIAL_RE = re.compile(r"^[A-Za-z]\.$")


def normalize_saint_spacing(text: str | None) -> str:
    """Insert a space after saint abbreviations glued to a name (St.James -> St. James)."""
    if not text:
        return ""
    updated = str(text)
    for prefix in _SAINT_PREFIXES:
        updated = re.sub(rf"\b{prefix}\.(?=[A-Za-zÀ-ÿ])", f"{prefix}. ", updated)
    return re.sub(r"  +", " ", updated)


def _format_single_letter_initial(word: str) -> str | None:
    if _SINGLE_LETTER_INITIAL_RE.match(word):
        return word[0].upper() + "."
    return None


def _capitalize_word_core(word: str) -> str:
    if not word:
        return word
    if re.match(r"^\d", word):
        return word
    initial = _format_single_letter_initial(word)
    if initial:
        return initial
    if _INITIAL_RE.match(word):
        return word
    lower = word.lower()
    if lower in _ROMAN_NUMERALS:
        return word.upper()
    if word.isupper() and len(word) <= 5:
        return word
    if _ACRONYM_RE.match(word):
        return word
    if len(word) > 2 and word[0].isupper() and word[1].islower():
        return word
    if "-" in word:
        return "-".join(_capitalize_word_core(part) for part in word.split("-"))
    if "'" in word or "\u2019" in word:
        separator = "'" if "'" in word else "\u2019"
        parts = word.split(separator)
        formatted: list[str] = []
        for index, part in enumerate(parts):
            if not part:
                formatted.append(part)
                continue
            if index and part.lower() in _SMALL_WORDS:
                formatted.append(part.lower())
            else:
                formatted.append(_capitalize_word_core(part))
        return separator.join(formatted)
    if len(word) == 1:
        return word.upper()
    return word[0].upper() + word[1:].lower()


def _title_case_clause(text: str, *, word_index: int = 0) -> tuple[str, int]:
    words = re.split(r"(\s+)", text.strip())
    output: list[str] = []
    for token in words:
        if not token.strip():
            output.append(token)
            continue
        leading = ""
        trailing = ""
        core = token
        while core and not core[0].isalnum():
            leading += core[0]
            core = core[1:]
        while core and not core[-1].isalnum():
            trailing = core[-1] + trailing
            core = core[:-1]
        if not core:
            output.append(token)
            continue
        candidate = f"{core}{trailing}"
        initial = _format_single_letter_initial(candidate)
        if initial:
            output.append(f"{leading}{initial}")
        else:
            lower = core.lower()
            if word_index and lower in _SMALL_WORDS:
                output.append(f"{leading}{lower}{trailing}")
            else:
                output.append(f"{leading}{_capitalize_word_core(core)}{trailing}")
        word_index += 1
    return "".join(output), word_index


def format_display_case(text: str | None, *, word_index: int = 0) -> str:
    """Apply English title case while preserving acronyms and mixed-case proper nouns."""
    formatted, _word_index = format_display_case_with_index(text, word_index=word_index)
    return formatted


def format_display_case_with_index(text: str | None, *, word_index: int = 0) -> tuple[str, int]:
    if text is None:
        return "", word_index
    cleaned = re.sub(r"\s+", " ", str(text)).strip()
    if not cleaned:
        return "", word_index

    if " · " in cleaned:
        parts = [part.strip() for part in cleaned.split(" · ") if part.strip()]
        formatted: list[str] = []
        idx = word_index
        for part in parts:
            part_fmt, idx = format_display_case_with_index(part, word_index=idx)
            formatted.append(part_fmt)
        return " · ".join(formatted), idx

    if " / " in cleaned:
        parts = [part.strip() for part in cleaned.split(" / ") if part.strip()]
        formatted = []
        idx = word_index
        for part in parts:
            part_fmt, idx = format_display_case_with_index(part, word_index=idx)
            formatted.append(part_fmt)
        return " / ".join(formatted), idx

    def repl_paren(match: re.Match[str]) -> str:
        inner, _idx = format_display_case_with_index(match.group(1), word_index=word_index)
        return f"({inner})"

    cleaned = re.sub(r"\(([^()]+)\)", repl_paren, cleaned)

    if ", " in cleaned:
        parts = [part.strip() for part in cleaned.split(", ") if part.strip()]
        formatted = []
        idx = word_index
        for part_index, part in enumerate(parts):
            if part_index > 0:
                idx = max(idx, 1)
            part_fmt, idx = format_display_case_with_index(part, word_index=idx)
            formatted.append(part_fmt)
        return ", ".join(formatted), idx

    return _title_case_clause(cleaned, word_index=word_index)


def format_display_text(text: str | None) -> str:
    """Normalize saint abbreviations and apply display title case."""
    return format_display_case(normalize_saint_spacing(text))
