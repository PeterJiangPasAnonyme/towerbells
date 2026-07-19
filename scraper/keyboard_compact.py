"""Compact keyboard override format for admin editing."""

from __future__ import annotations

import json
import re
from typing import Any

from scraper.bourdon_pitch import canonical_bourdon_pitch
from scraper.keyboard_display import (
    _parse_keyboard_range,
    _resolve_layout,
    _transposition_badge,
    build_keyboard_display,
    parse_keyboard_override,
)

NOTE_LABEL_RE = re.compile(r"^(.+?)(\d+)$")


def _pitch_name_from_label(label: str) -> str:
    match = NOTE_LABEL_RE.fullmatch(label.strip())
    if not match:
        raise ValueError(f"Invalid note label: {label!r}")
    return canonical_bourdon_pitch(match.group(1))


def _midi_from_label(label: str) -> int:
    from scraper.keyboard_display import _pitch_class

    match = NOTE_LABEL_RE.fullmatch(label.strip())
    if not match:
        raise ValueError(f"Invalid note label: {label!r}")
    name = canonical_bourdon_pitch(match.group(1))
    octave = int(match.group(2))
    return 12 * (octave + 1) + _pitch_class(name)


def _label_from_midi(midi: int) -> str:
    from scraper.keyboard_display import _pitch_name

    return f"{_pitch_name(midi % 12)}{midi // 12 - 1}"


def is_compact_keyboard_override(data: dict[str, Any] | None) -> bool:
    if not isinstance(data, dict):
        return False
    if data.get("format") == "compact":
        return True
    return "hands_low" in data and "hands" not in data and "pedals" not in data


def _compact_layout_signature(compact: dict[str, Any]) -> tuple[Any, ...]:
    missing = compact.get("missing_notes") or []
    return (
        compact.get("hands_low"),
        compact.get("hands_high"),
        compact.get("bass_low"),
        compact.get("bass_high"),
        compact.get("count"),
        tuple(missing) if isinstance(missing, list) else tuple(),
    )


def keyboard_display_to_compact(
    keyboard: dict[str, Any] | None,
    *,
    bell_count: int | None = None,
) -> dict[str, Any]:
    """Summarize a built keyboard display for admin editing."""
    keyboard = keyboard or {}
    compact: dict[str, Any] = {
        "format": "compact",
        "transposition_semitones": keyboard.get("transposition_semitones"),
        "hide_diagram": bool(keyboard.get("hide_diagram")),
        "force_prose": bool(keyboard.get("force_prose")),
        "prose": keyboard.get("prose"),
    }

    hands = keyboard.get("hands") or {}
    pedals = keyboard.get("pedals") or {}
    hands_keys = [key for key in hands.get("keys") or [] if not key.get("empty")]
    pedal_keys = [key for key in pedals.get("keys") or [] if not key.get("empty")]

    if hands_keys:
        compact["hands_low"] = _label_from_midi(min(key["midi"] for key in hands_keys))
        compact["hands_high"] = _label_from_midi(max(key["midi"] for key in hands_keys))

    if pedal_keys:
        compact["bass_low"] = _label_from_midi(min(key["midi"] for key in pedal_keys))
        compact["bass_high"] = _label_from_midi(max(key["midi"] for key in pedal_keys))

    if bell_count is not None:
        compact["count"] = bell_count

    missing = keyboard.get("missing_bass_notes")
    if missing:
        compact["missing_notes"] = list(missing)

    return compact


def _expand_layout_from_compact(
    compact: dict[str, Any],
    site: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Best-effort layout rebuild when compact layout fields change."""
    required = ("hands_low", "hands_high", "bass_low", "bass_high", "count")
    if not all(compact.get(key) not in (None, "") for key in required):
        return None, None

    try:
        hands_part = {
            "low": _pitch_name_from_label(compact["hands_low"]),
            "high": _pitch_name_from_label(compact["hands_high"]),
            "count": None,
            "extra_bass": [],
        }
        pedals_part = {
            "low": _pitch_name_from_label(compact["bass_low"]),
            "high": _pitch_name_from_label(compact["bass_high"]),
            "count": None,
            "extra_bass": [],
        }
    except ValueError:
        return None, None

    # Preserve explicit counts from the site range when present.
    parsed_range = _parse_keyboard_range(site.get("keyboard_range") or "")
    if parsed_range:
        hands_range = parsed_range.get("hands") or {}
        pedals_range = parsed_range.get("pedals") or {}
        hands_part["count"] = hands_range.get("count")
        pedals_part["count"] = pedals_range.get("count")
        hands_part["extra_bass"] = list(hands_range.get("extra_bass") or [])
        pedals_part["extra_bass"] = list(pedals_range.get("extra_bass") or [])

    missing_count = len(compact.get("missing_notes") or [])
    hands, pedals, _, ok = _resolve_layout(
        {"hands": hands_part, "pedals": pedals_part},
        bell_count=compact.get("count"),
        missing_count=missing_count,
    )
    if not ok or not hands or not pedals:
        return None, None
    return hands, pedals


def merge_compact_keyboard_override(
    compact: dict[str, Any],
    site: dict[str, Any],
    *,
    stored_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert compact admin input into a full keyboard override payload."""
    effective = build_keyboard_display(site, override=stored_override)
    base_compact = keyboard_display_to_compact(
        effective,
        bell_count=site.get("bell_count"),
    )

    hands = effective.get("hands")
    pedals = effective.get("pedals")
    if _compact_layout_signature(compact) != _compact_layout_signature(base_compact):
        rebuilt_hands, rebuilt_pedals = _expand_layout_from_compact(compact, site)
        if rebuilt_hands and rebuilt_pedals:
            hands = rebuilt_hands
            pedals = rebuilt_pedals

    transposition = compact.get("transposition_semitones")
    if transposition in ("", None):
        transposition_semitones = None
    else:
        transposition_semitones = int(transposition)

    full: dict[str, Any] = {
        "transposition_semitones": transposition_semitones,
        "transposition_badge": _transposition_badge(
            transposition_semitones,
            site.get("transposition"),
        ),
        "hands": hands,
        "pedals": pedals,
        "missing_bass_notes": list(compact.get("missing_notes") or []),
        "hide_diagram": bool(compact.get("hide_diagram")),
        "force_prose": bool(compact.get("force_prose")),
        "prose": compact.get("prose"),
    }
    return full


def normalize_keyboard_override_text(raw: str | None, site: dict[str, Any]) -> str:
    """Validate admin keyboard override text and store the expanded full override."""
    trimmed = (raw or "").strip()
    if not trimmed:
        return ""

    try:
        parsed = json.loads(trimmed)
    except json.JSONDecodeError as exc:
        raise ValueError("Keyboard override must be valid JSON.") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Keyboard override must be a JSON object.")

    stored_override = parse_keyboard_override(site.get("keyboard_display_override"))

    if is_compact_keyboard_override(parsed):
        compact = parsed
    elif "hands" in parsed or "pedals" in parsed:
        effective = build_keyboard_display(site, override=parsed)
        compact = keyboard_display_to_compact(effective, bell_count=site.get("bell_count"))
        for key in ("transposition_semitones", "hide_diagram", "force_prose", "prose"):
            if key in parsed:
                compact[key] = parsed[key]
        if "missing_bass_notes" in parsed:
            compact["missing_notes"] = parsed["missing_bass_notes"]
    else:
        compact = parsed
        compact.setdefault("format", "compact")

    full = merge_compact_keyboard_override(compact, site, stored_override=stored_override)

    # Safety check: if layout signature unchanged, keys must match the effective display.
    effective = build_keyboard_display(site, override=stored_override)
    base_compact = keyboard_display_to_compact(effective, bell_count=site.get("bell_count"))
    if _compact_layout_signature(compact) == _compact_layout_signature(base_compact):
        if effective.get("hands") and full.get("hands"):
            full["hands"] = effective["hands"]
        if effective.get("pedals") and full.get("pedals"):
            full["pedals"] = effective["pedals"]

    return json.dumps(full, indent=2)


def keyboard_override_for_editor(site: dict[str, Any], keyboard: dict[str, Any] | None) -> str:
    """JSON text shown in admin for keyboard overrides."""
    stored = parse_keyboard_override(site.get("keyboard_display_override"))
    if stored and is_compact_keyboard_override(stored):
        return json.dumps(stored, indent=2)

    compact = keyboard_display_to_compact(keyboard, bell_count=site.get("bell_count"))
    return json.dumps(compact, indent=2)
