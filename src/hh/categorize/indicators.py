"""Cross-cutting event indicators (fundraiser / youth program / film).

``event_majorcat`` is the single *primary* grouping — attendance tables need every event
in exactly one bucket so rows sum. But one bucket cannot say "a performance that is also
a fundraiser" (Brews & Blues) or "a class that is also a youth program" (the camps).
These indicator columns are additive dimensions: each is independent, any combination
can be true, and none changes the primary category. Analyses that need exclusive rows
keep using ``event_majorcat``; analyses that ask a cross-cutting question filter on the
``is_*`` flags.

Rules are name/category evidence, case-insensitive, on normalized strings (see
:mod:`.major`). Extend the tables as new cross-cutting questions arrive.
"""
from __future__ import annotations

import re

from ._match import present
from .major import _norm

# category (normalized) that implies the indicator
INDICATOR_CATS: dict[str, set[str]] = {
    "is_fundraiser": {"fundraising events"},
    "is_youth_program": {"children's theater", "children's art classes"},
    "is_film": {"film screenings"},
}

# name pattern that implies the indicator
INDICATOR_NAME_PATTERNS: dict[str, re.Pattern] = {
    "is_fundraiser": re.compile(r"fundraiser|\bbenefit\b|\bgala\b", re.I),
    # an explicit age floor of 15 or below reads as programming for minors; "and up"
    # classes aimed at adults (16+, 20 and up) do not flag
    "is_youth_program": re.compile(
        r"\bteens?\b|\byouth\b|\byoung\b|\bchild(?:ren|'s)?\b|\bkids?\b|\bcamps?\b"
        r"|ages?\s*[-–]?\s*\d{1,2}\b",
        re.I,
    ),
    "is_film": re.compile(r"\bfilm|\bmovie|\bscreening|\bcinema\b", re.I),
}

_ADULT_AGE = re.compile(r"ages?\s*(\d{1,2})", re.I)
_GALA = re.compile(r"\bgala\b", re.I)
_FUNDRAISER_WORD = re.compile(r"fundraiser|\bbenefit\b", re.I)


def _age_floor(name: str) -> int | None:
    """The first age mentioned ("Ages 9 - 12" -> 9); None when no age appears."""
    m = _ADULT_AGE.search(name)
    return int(m.group(1)) if m else None


def assign_indicators(category, event_name) -> dict[str, bool]:
    """The ``is_*`` indicator flags for one event."""
    cat = _norm(present(category) or "")
    name = present(event_name) or ""
    youth = bool(INDICATOR_NAME_PATTERNS["is_youth_program"].search(name))
    floor = _age_floor(name)
    if floor is not None and floor > 15:
        youth = False
    youth = youth or cat in INDICATOR_CATS["is_youth_program"]
    # "gala" alone is not fundraiser evidence when the event is youth programming
    # (recitals are often billed as "Gala Dance Performance")
    gala_only = bool(_GALA.search(name)) and not bool(_FUNDRAISER_WORD.search(name))
    fundraiser = cat in INDICATOR_CATS["is_fundraiser"] or (
        bool(INDICATOR_NAME_PATTERNS["is_fundraiser"].search(name)) and not (gala_only and youth)
    )
    film = cat in INDICATOR_CATS["is_film"] or bool(
        INDICATOR_NAME_PATTERNS["is_film"].search(name)
    )
    return {"is_fundraiser": fundraiser, "is_youth_program": youth, "is_film": film}


def add_indicators(df, *, category_col: str = "category", name_col: str = "event_name"):
    """Return a copy of ``df`` with one boolean ``is_*`` column per indicator."""
    out = df.copy()
    flags = [
        assign_indicators(c, n)
        for c, n in zip(out[category_col], out[name_col], strict=True)
    ]
    for flag in INDICATOR_CATS:
        out[flag] = [f[flag] for f in flags]
    return out
