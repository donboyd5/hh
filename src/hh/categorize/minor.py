"""Minor category for performance events: dance / music / theater / opera / other.

Faithful port of ``R_hhfrc/erin_donor_events_breakdown.qmd`` lines 59-161. Only meaningful when the
major category is ``"performance"``; returns ``"other"`` otherwise (matching R's ``.default``).

Case sensitivity is preserved exactly as in R:
- ``coll(..., ignore_case = TRUE)`` -> case-insensitive substring (most name matches).
- bare regex / ``fixed()`` -> case-sensitive substring
  (Cabaret, Concert, Blues, Crucible, Winter Carnival of New Work, Shakespeare, Travels With a
  Masked Man, Theater, Opera).
"""
from __future__ import annotations

from ._match import contains_any, present

# (field, needle, ignore_case) evaluated in order within each block; first match wins.
_MUSIC_NAME_RULES = [
    ("Music from Salem", True),
    ("Bob Warren", True),
    ("Music", True),
    ("Cabaret", False),
    ("Concert", False),
    ("Blues", False),
    ("Red Guitar", True),
    ("Florian Kitt", True),
    ("Jean Redpath", True),
    ("Village Harmony", True),
]
_THEATER_NAME_RULES = [
    ("Putnam County Spelling Bee", False),
    ("Year of Magical Thinking", True),
    ("Really Rosie", True),
    ("Sabina Spielrein", True),
    ("Crucible", False),
    ("Winter Carnival of New Work", False),
    ("Shakespeare", False),
    ("Travels With a Masked Man", False),
    ("Theater", False),
]


def assign_minor(category, event_name, major: str) -> str:
    """Return the minor category. Requires the already-computed ``major``."""
    if major != "performance":
        return "other"
    cat = present(category)
    name = present(event_name) or ""

    # ---- DANCE ----
    if contains_any(cat, ["Dance"], ignore_case=True):
        return "dance"
    if contains_any(name, ["Dance"], ignore_case=True):
        return "dance"

    # ---- MUSIC ----
    if contains_any(cat, ["Music"], ignore_case=True):
        return "music"
    for needle, ignore_case in _MUSIC_NAME_RULES:
        if contains_any(name, [needle], ignore_case=ignore_case):
            return "music"

    # ---- THEATER ----
    if cat in ("Shakespeare", "Theater Performances"):
        return "theater"
    for needle, ignore_case in _THEATER_NAME_RULES:
        if contains_any(name, [needle], ignore_case=ignore_case):
            return "theater"

    # ---- OPERA ----
    if cat == "Opera Performances":
        return "opera"
    if contains_any(name, ["Opera"], ignore_case=False):
        return "opera"

    return "other"
