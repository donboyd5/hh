"""Shared matching helpers for the event categorizers."""
from __future__ import annotations

import math


def present(v) -> str | None:
    """Return a cleaned string, or None if the value is missing / NaN / blank.

    Surrounding whitespace is stripped: Neon report exports carry incidental trailing spaces (e.g.
    ``"Visual Arts "``), and R's reference output has clean values, so stripping makes exact-match
    rules agree with R. NaN (a float) and None are treated as missing, like R's ``is.na()``.
    """
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
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
