"""Shared matching helpers for the event categorizers."""
from __future__ import annotations

import math

import pandas as pd


def present(v) -> str | None:
    """Return a cleaned string, or None if the value is missing / NaN / NA / blank.

    Handles pandas NA/NaT/NaN and None the way R's ``is.na()`` does. Surrounding whitespace is
    stripped: Neon exports carry incidental trailing spaces (e.g. ``"Visual Arts "``), and R's
    reference output has clean values, so stripping makes exact-match rules agree with R.
    """
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return s if s else None


def contains_any(haystack, needles, *, ignore_case: bool = False) -> bool:
    """True if any needle is a substring of ``haystack``.

    Case-sensitive by default, mirroring R's ``str_detect`` / ``fixed()``. Pass ``ignore_case=True``
    to mirror R's ``coll(..., ignore_case = TRUE)``.
    """
    if not haystack:
        return False
    h = str(haystack)
    if ignore_case:
        h = h.lower()
        return any(str(n).lower() in h for n in needles)
    return any(str(n) in h for n in needles)
