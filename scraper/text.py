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
