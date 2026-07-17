"""Keyboard range classification labels used on towerbells.org kr index pages."""

from __future__ import annotations

RANGE_CLASS_ORDER: list[str] = [
    "Group 1a",
    "Group 1b",
    "Group 1c",
    "Group 1c-",
    "Group 2a+",
    "Group 2a",
    "Group 2b+",
    "Group 2b",
    "Group 2c",
    "Group 2c+",
    "Group 3a",
    "Group 3b",
    "Group 3c",
    "Group 4a",
    "Group 4b",
    "Group 4c",
    "Unknown",
]

RANGE_CLASSIFICATION_LEGEND: dict[str, object] = {
    "title": "Keyboard range classifications",
    "intro": (
        "Traditional carillons are grouped by total playing range and by which "
        "bass notes are missing from the keyboard. Subgroup numbers come from "
        "towerbells.org regional keyboard-range index pages."
    ),
    "groups": [
        {
            "label": "Group 1",
            "description": "Grand carillon — at least 4½ octaves (keyboard G to C).",
            "subgroups": [
                {
                    "code": "1a",
                    "description": "Fully chromatic within grand carillon range.",
                },
                {
                    "code": "1b",
                    "description": "Missing bass G♯ within grand carillon range.",
                },
                {
                    "code": "1c",
                    "description": "Missing bass G♯ and A♯ within grand carillon range.",
                },
                {
                    "code": "1c-",
                    "description": "Missing bass G♯, B, and C♯ within grand carillon range.",
                },
            ],
        },
        {
            "label": "Group 2",
            "description": "Concert carillon — at least 4 octaves (keyboard C to C).",
            "subgroups": [
                {
                    "code": "2a+",
                    "description": "Fully chromatic within concert carillon range, plus bass B♭.",
                },
                {
                    "code": "2a",
                    "description": "Fully chromatic within concert carillon range.",
                },
                {
                    "code": "2b+",
                    "description": "Missing bass C♯ from concert range, plus bass B♭.",
                },
                {
                    "code": "2b",
                    "description": "Missing bass C♯ from concert carillon range.",
                },
                {
                    "code": "2c",
                    "description": "Missing bass C♯ and D♯ from concert carillon range.",
                },
                {
                    "code": "2c+",
                    "description": "Missing bass C♯ and D♯ from concert range, plus bass B♭.",
                },
            ],
        },
        {
            "label": "Group 3",
            "description": "Medium carillon — at least 3 octaves (keyboard C to C).",
            "subgroups": [
                {
                    "code": "3a",
                    "description": "Medium carillon with fully chromatic bass.",
                },
                {
                    "code": "3b",
                    "description": "Medium carillon missing one bass semitone.",
                },
                {
                    "code": "3c",
                    "description": "Medium carillon missing two bass semitones.",
                },
            ],
        },
        {
            "label": "Group 4",
            "description": "Small carillon — less than 3 octaves.",
            "subgroups": [
                {
                    "code": "4a",
                    "description": "Small carillon with fully chromatic bass.",
                },
                {
                    "code": "4b",
                    "description": "Small carillon missing one bass semitone.",
                },
                {
                    "code": "4c",
                    "description": "Small carillon missing two bass semitones.",
                },
            ],
        },
    ],
    "note": (
        "Music that fits a subgroup can usually be played on every carillon in "
        "that subgroup, and also on carillons in higher subgroups in the table."
    ),
}


def sort_range_classification_facets(
    items: list[dict[str, object]],
) -> list[dict[str, object]]:
    order = {value: index for index, value in enumerate(RANGE_CLASS_ORDER)}
    return sorted(
        items,
        key=lambda item: (
            order.get(str(item["value"]), len(RANGE_CLASS_ORDER)),
            str(item["value"]).lower(),
        ),
    )
