"""Structured carillon keyboard display from towerbells technical data."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from scraper.bourdon_pitch import BOURDON_PITCH_ORDER, canonical_bourdon_pitch
from scraper.technical_display import NA_DISPLAY, is_unknown_like_value

NOTE_PATTERN = re.compile(
    r"(A#|Bb|B|C#|Db|C|D#|Eb|D|E|F#|Gb|F|G#|Ab|G|A)",
    re.I,
)

PITCH_CLASS = {name: index for index, name in enumerate(BOURDON_PITCH_ORDER)}

MIDDLE_C = 60  # C4

# Missing bass semitones in the order they are dropped (absolute octave labels).
MISSING_CANDIDATE_SPECS: list[tuple[str, int]] = [
    ("F#", 2),
    ("G#", 2),
    ("B", 2),
    ("C#", 3),
    ("D#", 3),
]


def parse_keyboard_override(raw: str | None) -> dict[str, Any] | None:
    if not raw or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def parse_transposition_semitones(transposition: str | None) -> int | None:
    if not transposition:
        return None
    text = transposition.strip()
    if re.search(r"\bnil\b|\bconcert pitch\b|\bnone\b", text, re.I):
        return 0
    if re.search(r"\bunknown\b", text, re.I):
        return None

    octave_match = re.search(r"(up|down)\s+(one|two|three|\d+)\s+octaves?", text, re.I)
    if octave_match:
        amount = octave_match.group(2).lower()
        word_octaves = {"one": 1, "two": 2, "three": 3}
        octaves = word_octaves[amount] if amount in word_octaves else int(amount)
        semitones = octaves * 12
        return semitones if octave_match.group(1).lower() == "up" else -semitones

    match = re.search(r"(up|down)\s+(\d+)\s+semitone", text, re.I)
    if match:
        semitones = int(match.group(2))
        return semitones if match.group(1).lower() == "up" else -semitones
    return None


def parse_missing_bass_count(text: str | None) -> int:
    if not text:
        return 0
    lowered = text.lower()
    if "two missing" in lowered:
        return 2
    if "one missing" in lowered:
        return 1
    return 0


def resolve_missing_bass_count(site: dict) -> int:
    """Read missing-bass count from structured field or technical prose."""
    for source in (site.get("missing_bass_semitone"), site.get("technical_data")):
        count = parse_missing_bass_count(source)
        if count:
            return count
    return 0


def _pitch_class(name: str) -> int:
    canonical = canonical_bourdon_pitch(name)
    if canonical not in PITCH_CLASS:
        raise ValueError(f"Unknown pitch: {name}")
    return PITCH_CLASS[canonical]


def _pitch_name(pc: int) -> str:
    return BOURDON_PITCH_ORDER[pc % 12]


def _is_sharp(pc: int) -> bool:
    return _pitch_name(pc) in {"C#", "D#", "F#", "G#", "A#"}


def _concert_pitch(keyboard_pc: int, transposition_semitones: int | None) -> str:
    if transposition_semitones is None:
        return _pitch_name(keyboard_pc)
    concert_pc = (keyboard_pc + transposition_semitones) % 12
    return _pitch_name(concert_pc)


def _parse_note_tokens(text: str) -> list[str]:
    return [canonical_bourdon_pitch(match.group(0)) for match in NOTE_PATTERN.finditer(text)]


def _parse_keyboard_part(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None

    text = raw.strip()
    if not text or text.upper() in {"----", "NONE", "--"}:
        return None

    extra_bass: list[str] = []
    while True:
        match = re.match(r"^\(([^)]+)\)", text)
        if not match:
            break
        notes = _parse_note_tokens(match.group(1))
        extra_bass.extend(notes)
        text = text[match.end() :].strip()

    text = re.sub(r"-+", " ", text).strip()
    count: int | None = None
    count_match = re.search(r"(\d{1,2})\s*$", text)
    if count_match:
        count = int(count_match.group(1))
        text = text[: count_match.start()].strip()

    notes = _parse_note_tokens(text)
    if len(notes) < 2:
        return None

    return {
        "low": notes[0],
        "high": notes[1],
        "count": count,
        "extra_bass": extra_bass,
    }


def _parse_keyboard_range(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    text = raw.strip()
    if not text or text.startswith("----"):
        return None

    if "/" in text:
        hands_raw, pedals_raw = text.split("/", 1)
    else:
        hands_raw, pedals_raw = text, ""

    hands = _parse_keyboard_part(hands_raw)
    pedals = _parse_keyboard_part(pedals_raw)
    if hands and not pedals:
        pedals = _default_pedals_part(hands, pedals_raw)
    if not hands and not pedals:
        return None
    return {"hands": hands, "pedals": pedals}


def _default_pedals_part(hands_part: dict[str, Any], pedals_raw: str) -> dict[str, Any] | None:
    """Infer a standard pedal board when the range marks pedals as NONE or unknown."""
    text = re.sub(r"-+", " ", (pedals_raw or "").strip()).strip().upper()
    if text not in {"NONE", "", "--"} and not text.startswith("----"):
        return None
    pedal_low = (
        "C"
        if _pitch_class(hands_part["low"]) == _pitch_class("C")
        else hands_part["low"]
    )
    return {
        "low": pedal_low,
        "high": "G",
        "count": None,
        "extra_bass": [],
    }


def _anchor_lowest_midi(pedal_low: str) -> int:
    """Place the pedal low key about one to one-and-a-half octaves below C4."""
    pc = _pitch_class(pedal_low)
    candidates = [octave * 12 + pc for octave in range(1, 6)]
    in_window = [midi for midi in candidates if MIDDLE_C - 19 <= midi <= MIDDLE_C - 5]
    if in_window:
        return min(in_window)
    return 3 * 12 + pc


def _extra_bass_midi(note: str, anchor_midi: int) -> int | None:
    if "?" in note:
        return None
    pc = _pitch_class(note)
    extra = anchor_midi - 1
    while extra >= 24 and extra % 12 != pc:
        extra -= 1
    if extra >= 24 and extra < anchor_midi:
        return extra
    return None


def _extra_bass_extension(
    part: dict[str, Any],
    *,
    anchor_midi: int | None = None,
) -> tuple[int | None, set[int]]:
    """Parenthetical extra bass: the note exists; semitones up to the low pitch are gaps."""
    extra_notes = part.get("extra_bass") or []
    if not extra_notes:
        return None, set()
    anchor = anchor_midi if anchor_midi is not None else _anchor_lowest_midi(part["low"])
    start: int | None = None
    gaps: set[int] = set()
    for note in extra_notes:
        extra = _extra_bass_midi(note, anchor)
        if extra is None:
            continue
        start = extra if start is None else min(start, extra)
        gaps.update(range(extra + 1, anchor))
    return start, gaps


def _highest_midi(
    lowest_midi: int,
    bell_count: int,
    baton_high: str,
    *,
    missing_count: int = 0,
) -> int | None:
    if bell_count is None or bell_count <= 0:
        return None
    # Missing bass semitones are gaps in the chromatic compass, not playable bells.
    chromatic_span = bell_count + max(missing_count, 0)
    compass_top = lowest_midi + chromatic_span - 1
    high_pc = _pitch_class(baton_high)
    options = [midi for midi in range(lowest_midi, compass_top + 1) if midi % 12 == high_pc]
    if not options:
        return None
    return options[-1]


def _compass_chromatic_span(lowest_midi: int, highest_midi: int) -> int:
    return highest_midi - lowest_midi + 1


def _compass_validates_bell_count(
    lowest_midi: int,
    highest_midi: int,
    bell_count: int,
    missing_count: int,
) -> bool:
    return _compass_chromatic_span(lowest_midi, highest_midi) == bell_count + max(missing_count, 0)


def _named_midi(name: str, octave: int) -> int:
    """Scientific pitch label such as C#3 (C4 middle C is MIDI 60)."""
    return 12 * (octave + 1) + _pitch_class(name)


def _missing_candidate_midis(lowest_midi: int) -> list[int]:
    candidates: list[int] = []
    for name, octave in MISSING_CANDIDATE_SPECS:
        midi = _named_midi(name, octave)
        if midi > lowest_midi:
            candidates.append(midi)
    return candidates


def _missing_midi_set(lowest_midi: int, missing_count: int) -> set[int]:
    if missing_count <= 0:
        return set()
    return set(_missing_candidate_midis(lowest_midi)[:missing_count])


def _missing_note_labels(missing_midis: set[int]) -> list[str]:
    labels: list[str] = []
    for name, octave in MISSING_CANDIDATE_SPECS:
        midi = _named_midi(name, octave)
        if midi in missing_midis:
            labels.append(f"{name}{octave}")
    return labels


def _midi_for_pitch_between(name: str, low_midi: int, high_midi: int, *, prefer: Literal["low", "high"]) -> int | None:
    pc = _pitch_class(name)
    matches = [midi for midi in range(low_midi, high_midi + 1) if midi % 12 == pc]
    if not matches:
        return None
    return matches[0] if prefer == "low" else matches[-1]


def _pitch_immediately_above(lowest_midi: int, name: str) -> int | None:
    target_pc = _pitch_class(name)
    lowest_pc = lowest_midi % 12
    step = (target_pc - lowest_pc) % 12
    if step == 0:
        step = 12
    return lowest_midi + step


MIN_PEDAL_SEMITONE_SPAN = 6


def _small_carillon_pedal_search_high(
    *,
    pedal_start: int,
    pedals_high: str,
    highest_midi: int | None,
) -> int:
    """Search ceiling for small-instrument pedals through the high pitch above C4."""
    high_pc = _pitch_class(pedals_high)
    offset = (high_pc - _pitch_class("C")) % 12
    top = MIDDLE_C + offset
    if highest_midi is not None:
        top = min(top, highest_midi)
    return max(top, pedal_start)


def _ensure_min_pedal_span(
    *,
    pedal_start: int,
    pedal_end: int | None,
    pedals_high: str,
    highest_midi: int | None,
) -> int | None:
    if pedal_end is None:
        return None
    if pedal_end - pedal_start + 1 >= MIN_PEDAL_SEMITONE_SPAN:
        return pedal_end
    if highest_midi is None:
        return pedal_end
    extended = _midi_for_pitch_between(
        pedals_high,
        pedal_start,
        highest_midi,
        prefer="high",
    )
    if extended is not None and extended - pedal_start + 1 >= MIN_PEDAL_SEMITONE_SPAN:
        return extended
    floor_end = pedal_start + MIN_PEDAL_SEMITONE_SPAN - 1
    return floor_end if floor_end <= highest_midi else pedal_end


def _infer_pedal_end_midi(
    *,
    pedals_high: str,
    lowest_midi: int,
    highest_midi: int,
    bell_count: int | None,
) -> int | None:
    """Highest pedal key when pedal count is not stated explicitly."""
    span = highest_midi - lowest_midi + 1
    small_carillon = span <= 25 or (bell_count is not None and bell_count <= 28)

    above_c4 = MIDDLE_C + 1
    usual_top = MIDDLE_C + 12  # C5

    high_pc = _pitch_class(pedals_high)
    if high_pc == _pitch_class("G"):
        preferred = _midi_for_pitch_between("G", above_c4, usual_top, prefer="high")
    elif high_pc == _pitch_class("C"):
        search_low = above_c4 if not small_carillon else lowest_midi
        search_high = (
            usual_top
            if not small_carillon
            else _small_carillon_pedal_search_high(
                pedal_start=lowest_midi,
                pedals_high=pedals_high,
                highest_midi=highest_midi,
            )
        )
        preferred = _midi_for_pitch_between("C", search_low, search_high, prefer="high")
        if (
            preferred is not None
            and high_pc == lowest_midi % 12
            and preferred <= lowest_midi
        ):
            next_c = lowest_midi + 12
            if next_c <= search_high:
                preferred = next_c
    else:
        search_low = above_c4 if not small_carillon else lowest_midi
        search_high = (
            usual_top
            if not small_carillon
            else _small_carillon_pedal_search_high(
                pedal_start=lowest_midi,
                pedals_high=pedals_high,
                highest_midi=highest_midi,
            )
        )
        preferred = _midi_for_pitch_between(pedals_high, search_low, search_high, prefer="high")

    if preferred is not None and lowest_midi <= preferred <= highest_midi:
        return preferred

    return _midi_for_pitch_between(pedals_high, lowest_midi, highest_midi, prefer="high")


def _key_dict(midi: int, *, gap: bool = False, empty: bool = False) -> dict[str, Any]:
    pc = midi % 12
    if empty:
        return {
            "midi": midi,
            "keyboard": None,
            "pc": pc,
            "is_sharp": False,
            "missing": False,
            "gap": False,
            "empty": True,
        }
    if gap:
        return {
            "midi": midi,
            "keyboard": _pitch_name(pc),
            "pc": pc,
            "is_sharp": _is_sharp(pc),
            "missing": True,
            "gap": True,
            "empty": False,
        }
    return {
        "midi": midi,
        "keyboard": _pitch_name(pc),
        "pc": pc,
        "is_sharp": _is_sharp(pc),
        "missing": False,
        "gap": False,
        "empty": False,
    }


def _is_missing_midi(midi: int, missing_midis: set[int]) -> bool:
    return midi in missing_midis


def _manual_bounds(keys: list[dict[str, Any]] | None) -> tuple[int | None, int | None]:
    if not keys:
        return None, None
    active = [key for key in keys if not key.get("empty")]
    if not active:
        return None, None
    midis = [key["midi"] for key in active if key.get("midi") is not None]
    if not midis:
        return None, None
    return min(midis), max(midis)


def _build_manual_grid(
    *,
    manual_start: int,
    manual_end: int,
    grid_start: int,
    grid_end: int,
    missing_midis: set[int],
) -> list[dict[str, Any]]:
    """One slot per semitone on the shared compass; inactive slots stay empty."""
    keys: list[dict[str, Any]] = []
    for midi in range(grid_start, grid_end + 1):
        if midi < manual_start or midi > manual_end:
            keys.append(_key_dict(midi, empty=True))
        elif _is_missing_midi(midi, missing_midis):
            keys.append(_key_dict(midi, gap=True))
        else:
            keys.append(_key_dict(midi))
    return keys


def _collect_keys_range(
    *,
    start_midi: int,
    end_midi: int,
    missing_midis: set[int],
) -> list[dict[str, Any]]:
    """Walk every semitone from start to end, inserting missing-note gaps inline."""
    keys: list[dict[str, Any]] = []
    for midi in range(start_midi, end_midi + 1):
        if _is_missing_midi(midi, missing_midis):
            keys.append(_key_dict(midi, gap=True))
        else:
            keys.append(_key_dict(midi))
    return keys


def _align_keyboard_rows(
    *,
    baton_start: int,
    baton_end: int,
    pedal_start: int,
    pedal_end: int,
    missing_midis: set[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grid_start = min(baton_start, pedal_start)
    grid_end = max(baton_end, pedal_end)
    baton_keys = _build_manual_grid(
        manual_start=baton_start,
        manual_end=baton_end,
        grid_start=grid_start,
        grid_end=grid_end,
        missing_midis=missing_midis,
    )
    pedal_keys = _build_manual_grid(
        manual_start=pedal_start,
        manual_end=pedal_end,
        grid_start=grid_start,
        grid_end=grid_end,
        missing_midis=missing_midis,
    )
    return baton_keys, pedal_keys


def _pedals_prefer_inferred_range(pedals_part: dict[str, Any], pedals_count: int | None) -> bool:
    """Standard pedal-board letters (especially G) beat an explicit count that overshoots."""
    if pedals_count is None:
        return True
    return _pitch_class(pedals_part["high"]) == _pitch_class("G")


def _collect_keys(
    *,
    count: int,
    start_midi: int,
    direction: Literal["up", "down"],
    missing_midis: set[int],
) -> list[dict[str, Any]] | None:
    keys: list[dict[str, Any]] = []
    played = 0
    midi = start_midi
    step = 1 if direction == "up" else -1
    guard = 0

    while played < count and guard < 200:
        if _is_missing_midi(midi, missing_midis):
            keys.append(_key_dict(midi, gap=True))
        else:
            keys.append(_key_dict(midi))
            played += 1
        midi += step
        guard += 1

    if played != count:
        return None
    return keys


def _keys_low_to_high(keys: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ensure keys render left-to-right from low pitch to high pitch."""
    played = [key for key in keys if key.get("midi") is not None]
    if len(played) >= 2 and played[0]["midi"] > played[-1]["midi"]:
        return list(reversed(keys))
    return keys


def _build_baton_keys_full_compass(
    *,
    hands_part: dict[str, Any],
    lowest_midi: int,
    highest_midi: int,
    missing_midis: set[int],
) -> tuple[int | None, int | None, list[dict[str, Any]] | None]:
    """Batons share the pedal low note and span up to the top of the instrument."""
    baton_start = lowest_midi
    baton_end = _midi_for_pitch_between(
        hands_part["high"],
        lowest_midi,
        highest_midi,
        prefer="high",
    )
    if baton_end is None or baton_start > baton_end:
        return None, None, None
    baton_keys = _collect_keys_range(
        start_midi=baton_start,
        end_midi=baton_end,
        missing_midis=missing_midis,
    )
    if not baton_keys:
        return None, None, None
    return baton_start, baton_end, baton_keys


def _find_baton_keys_counting_up(
    *,
    hands_part: dict[str, Any],
    pedals_part: dict[str, Any],
    hands_count: int,
    missing_midis: set[int],
    lowest_midi: int,
    highest_midi: int | None,
) -> list[dict[str, Any]] | None:
    _, _, keys = _find_baton_keys_from_anchor(
        hands_part=hands_part,
        pedals_part=pedals_part,
        hands_count=hands_count,
        missing_midis=missing_midis,
        lowest_midi=lowest_midi,
        highest_midi=highest_midi,
    )
    return keys


def _baton_start_midi(
    *,
    hands_part: dict[str, Any],
    pedals_part: dict[str, Any],
    lowest_midi: int,
) -> int | None:
    """First baton key sits on the hands low pitch immediately above the pedal low."""
    low_pc = _pitch_class(hands_part["low"])
    pedal_pc = _pitch_class(pedals_part["low"])
    if low_pc == pedal_pc:
        return lowest_midi
    return _pitch_immediately_above(lowest_midi, hands_part["low"])


def _find_baton_keys_from_anchor(
    *,
    hands_part: dict[str, Any],
    pedals_part: dict[str, Any],
    hands_count: int,
    missing_midis: set[int],
    lowest_midi: int,
    highest_midi: int | None,
) -> tuple[int | None, int | None, list[dict[str, Any]] | None]:
    """Count baton keys upward from the pitch above the pedal low."""
    start = _baton_start_midi(
        hands_part=hands_part,
        pedals_part=pedals_part,
        lowest_midi=lowest_midi,
    )
    if start is None:
        return None, None, None

    keys = _collect_keys(
        count=hands_count,
        start_midi=start,
        direction="up",
        missing_midis=missing_midis,
    )
    if not keys:
        return None, None, None

    played = [key for key in keys if not key.get("gap")]
    if len(played) != hands_count:
        return None, None, None

    high_pc = _pitch_class(hands_part["high"])
    if played[-1]["pc"] != high_pc:
        return None, None, None

    return played[0]["midi"], played[-1]["midi"], _keys_low_to_high(keys)


def _layout_inputs_viable(
    hands_part: dict[str, Any],
    pedals_part: dict[str, Any],
    *,
    bell_count: int | None,
    hands_count: int | None,
    pedals_count: int | None,
) -> bool:
    if hands_count or pedals_count:
        return True
    return bool(bell_count)


def _resolve_layout(
    parsed: dict[str, Any],
    *,
    bell_count: int | None,
    missing_count: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str], bool]:
    hands_part = parsed.get("hands")
    pedals_part = parsed.get("pedals")
    if not hands_part or not pedals_part:
        return None, None, [], False

    if not _layout_inputs_viable(
        hands_part,
        pedals_part,
        bell_count=bell_count,
        hands_count=hands_part.get("count"),
        pedals_count=pedals_part.get("count"),
    ):
        return None, None, [], False

    hands_count = hands_part.get("count")
    pedals_count = pedals_part.get("count")
    same_pitch_span = _pitch_class(hands_part["low"]) == _pitch_class(hands_part["high"])
    explicit_hands = hands_part.get("count")

    if hands_count is None and pedals_count is not None and bell_count and not same_pitch_span:
        inferred = bell_count - pedals_count
        if inferred > 0:
            probe_start, probe_end, probe_keys = _find_baton_keys_from_anchor(
                hands_part=hands_part,
                pedals_part=pedals_part,
                hands_count=inferred,
                missing_midis=set(),
                lowest_midi=_anchor_lowest_midi(pedals_part["low"]),
                highest_midi=None,
            )
            if probe_keys:
                hands_count = inferred

    lowest_midi = _anchor_lowest_midi(pedals_part["low"])
    highest_midi = (
        _highest_midi(
            lowest_midi,
            bell_count,
            hands_part["high"],
            missing_count=missing_count,
        )
        if bell_count
        else None
    )

    missing_midis = _missing_midi_set(lowest_midi, missing_count)
    missing_labels = _missing_note_labels(missing_midis)

    # --- Pedals ---
    pedals_anchor = _anchor_lowest_midi(pedals_part["low"])
    pedal_start = pedals_anchor
    extra_pedal_start, structural_pedal_gaps = _extra_bass_extension(
        pedals_part,
        anchor_midi=pedals_anchor,
    )
    pedal_missing = set(missing_midis)
    if extra_pedal_start is not None:
        pedal_start = min(pedal_start, extra_pedal_start)
        pedal_missing |= structural_pedal_gaps

    pedal_end: int | None = None
    inferred_pedal_end = (
        _infer_pedal_end_midi(
            pedals_high=pedals_part["high"],
            lowest_midi=pedal_start,
            highest_midi=highest_midi,
            bell_count=bell_count,
        )
        if highest_midi is not None
        else None
    )

    if _pedals_prefer_inferred_range(pedals_part, pedals_count) and inferred_pedal_end is not None:
        pedal_end = inferred_pedal_end
    elif pedals_count:
        pedal_probe = _collect_keys(
            count=pedals_count,
            start_midi=pedal_start,
            direction="up",
            missing_midis=pedal_missing,
        )
        if pedal_probe:
            played = [key for key in pedal_probe if not key.get("gap")]
            pedal_end = played[-1]["midi"] if played else None
    elif inferred_pedal_end is not None:
        pedal_end = inferred_pedal_end

    pedal_end = _ensure_min_pedal_span(
        pedal_start=pedal_start,
        pedal_end=pedal_end,
        pedals_high=pedals_part["high"],
        highest_midi=highest_midi,
    )

    # --- Batons ---
    baton_end: int | None = None
    baton_start: int | None = None
    baton_keys: list[dict[str, Any]] | None = None

    if same_pitch_span and highest_midi is not None:
        baton_start, baton_end, baton_keys = _build_baton_keys_full_compass(
            hands_part=hands_part,
            lowest_midi=lowest_midi,
            highest_midi=highest_midi,
            missing_midis=missing_midis,
        )
    elif hands_count:
        baton_start, baton_end, baton_keys = _find_baton_keys_from_anchor(
            hands_part=hands_part,
            pedals_part=pedals_part,
            hands_count=hands_count,
            missing_midis=missing_midis,
            lowest_midi=lowest_midi,
            highest_midi=highest_midi,
        )

    if not baton_keys and highest_midi is not None and bell_count:
        baton_start, baton_end, baton_keys = _build_baton_keys_full_compass(
            hands_part=hands_part,
            lowest_midi=lowest_midi,
            highest_midi=highest_midi,
            missing_midis=missing_midis,
        )
        if baton_keys and _pitch_class(hands_part["low"]) != _pitch_class(pedals_part["low"]):
            alt_start = _baton_start_midi(
                hands_part=hands_part,
                pedals_part=pedals_part,
                lowest_midi=lowest_midi,
            )
            if alt_start is not None and baton_end is not None and alt_start <= baton_end:
                baton_start = alt_start
                baton_keys = _collect_keys_range(
                    start_midi=baton_start,
                    end_midi=baton_end,
                    missing_midis=missing_midis,
                )

    if baton_start is None or baton_end is None or pedal_end is None:
        return None, None, missing_labels, False

    hands_anchor = _anchor_lowest_midi(hands_part["low"])
    extra_baton_start, structural_baton_gaps = _extra_bass_extension(
        hands_part,
        anchor_midi=hands_anchor,
    )
    baton_missing = set(missing_midis)
    if extra_baton_start is not None:
        baton_start = min(baton_start, extra_baton_start)
        baton_missing |= structural_baton_gaps
        baton_keys = _collect_keys_range(
            start_midi=baton_start,
            end_midi=baton_end,
            missing_midis=baton_missing,
        )

    if _pedals_prefer_inferred_range(pedals_part, pedals_count):
        pedal_keys = _collect_keys_range(
            start_midi=pedal_start,
            end_midi=pedal_end,
            missing_midis=pedal_missing,
        )
    elif pedals_count:
        pedal_keys = _collect_keys(
            count=pedals_count,
            start_midi=pedal_start,
            direction="up",
            missing_midis=pedal_missing,
        )
    else:
        pedal_keys = _collect_keys_range(
            start_midi=pedal_start,
            end_midi=pedal_end,
            missing_midis=pedal_missing,
        )

    if not baton_keys:
        return None, None, missing_labels, False
    if not pedal_keys:
        return None, None, missing_labels, False

    pedal_keys = _keys_low_to_high(pedal_keys)
    baton_keys = _keys_low_to_high(baton_keys)

    confident = bool(baton_keys and pedal_keys)
    hands = None
    pedals = None
    if confident:
        played_batons = [key for key in baton_keys if not key.get("gap")]
        played_pedals = [key for key in pedal_keys if not key.get("gap")]
        hands_low = hands_part["low"]
        if extra_baton_start is not None and played_batons:
            hands_low = played_batons[0]["keyboard"] or hands_low
        hands = {
            "low": hands_low,
            "high": hands_part["high"],
            "count": len(played_batons),
            "extra_bass": hands_part.get("extra_bass") or [],
            "keys": baton_keys,
        }
        pedals_low = pedals_part["low"]
        if extra_pedal_start is not None and played_pedals:
            pedals_low = played_pedals[0]["keyboard"] or pedals_low
        pedals = {
            "low": pedals_low,
            "high": pedals_part["high"],
            "count": len(played_pedals),
            "extra_bass": pedals_part.get("extra_bass") or [],
            "keys": pedal_keys,
        }

    return hands, pedals, missing_labels, confident


def _transposition_badge(
    transposition_semitones: int | None,
    transposition_raw: str | None = None,
) -> str | None:
    if is_unknown_like_value(transposition_raw):
        return NA_DISPLAY
    if transposition_semitones is None:
        return None
    if transposition_semitones == 0:
        return "0"
    if transposition_semitones % 12 == 0:
        octaves = transposition_semitones // 12
        return f"+{octaves} oct" if octaves > 0 else f"{octaves} oct"
    return f"+{transposition_semitones}" if transposition_semitones > 0 else str(transposition_semitones)


def _apply_concert_labels(
    keyboard: dict[str, Any] | None,
    transposition_semitones: int | None,
) -> None:
    if not keyboard:
        return
    for key in keyboard.get("keys") or []:
        key["concert"] = _concert_pitch(key["pc"], transposition_semitones)


def _keyboard_has_content(result: dict[str, Any]) -> bool:
    if result.get("force_prose"):
        return bool((result.get("prose") or "").strip())
    if result.get("hide_diagram"):
        return False
    hands = result.get("hands")
    pedals = result.get("pedals")
    return bool((hands and hands.get("keys")) or (pedals and pedals.get("keys")))


def build_keyboard_display(
    site: dict,
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    keyboard_range = (site.get("keyboard_range") or "").strip()
    transposition_raw = site.get("transposition") or ""
    missing_text = site.get("missing_bass_semitone") or ""
    bell_count = site.get("bell_count")

    transposition_semitones = parse_transposition_semitones(transposition_raw)
    missing_count = resolve_missing_bass_count(site)
    parsed = _parse_keyboard_range(keyboard_range)

    result: dict[str, Any] = {
        "mode": "structured",
        "keyboard_range_raw": (
            NA_DISPLAY
            if is_unknown_like_value(keyboard_range)
            else (keyboard_range or None)
        ),
        "transposition_raw": transposition_raw or None,
        "transposition_semitones": transposition_semitones,
        "transposition_badge": _transposition_badge(transposition_semitones, transposition_raw),
        "missing_bass_count": missing_count,
        "missing_bass_text": (
            NA_DISPLAY if is_unknown_like_value(missing_text) else (missing_text or None)
        ),
        "parse_error": None,
        "hands": None,
        "pedals": None,
        "prose": None,
        "hide_diagram": False,
        "force_prose": False,
        "has_content": False,
    }

    if not parsed:
        result["parse_error"] = "Could not parse keyboard range"
        result["mode"] = "prose"
        result = _apply_override(result, override)
        result["has_content"] = _keyboard_has_content(result)
        return result

    hands, pedals, missing_labels, confident = _resolve_layout(
        parsed,
        bell_count=bell_count,
        missing_count=missing_count,
    )

    if confident:
        result["hands"] = hands
        result["pedals"] = pedals
        _apply_concert_labels(hands, transposition_semitones)
        _apply_concert_labels(pedals, transposition_semitones)
    else:
        result["mode"] = "prose"

    if missing_labels:
        result["missing_bass_notes"] = missing_labels

    result["has_content"] = confident

    result = _apply_override(result, override)
    result["has_content"] = _keyboard_has_content(result)
    return result


def _apply_override(result: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    if not override:
        return result

    if "transposition_semitones" in override:
        value = override["transposition_semitones"]
        result["transposition_semitones"] = int(value) if value not in (None, "") else None
        result["transposition_badge"] = _transposition_badge(
            result["transposition_semitones"],
            result.get("transposition_raw"),
        )
        _apply_concert_labels(result.get("hands"), result.get("transposition_semitones"))
        _apply_concert_labels(result.get("pedals"), result.get("transposition_semitones"))

    if "transposition_badge" in override:
        badge = override["transposition_badge"]
        result["transposition_badge"] = str(badge).strip() if badge else None

    if "hands" in override and isinstance(override["hands"], dict):
        result["hands"] = override["hands"]
        _apply_concert_labels(result["hands"], result.get("transposition_semitones"))

    if "pedals" in override and isinstance(override["pedals"], dict):
        result["pedals"] = override["pedals"]
        _apply_concert_labels(result["pedals"], result.get("transposition_semitones"))

    if "missing_bass_notes" in override and isinstance(override["missing_bass_notes"], list):
        result["missing_bass_notes"] = override["missing_bass_notes"]

    if "prose" in override:
        prose = override["prose"]
        result["prose"] = str(prose).strip() if prose else None

    if override.get("hide_diagram"):
        result["hide_diagram"] = True
    if override.get("force_prose"):
        result["force_prose"] = True
        result["mode"] = "prose"

    if override.get("mode"):
        result["mode"] = override["mode"]

    return result
