"""Two-stage event categorization (port of R logic).

major: performance / class / community / other  (uncategorized -> "ERROR" tripwire)
minor (splits performance): dance / music / theater / opera / other
"""
from __future__ import annotations

import pandas as pd

from .major import assign_major
from .minor import assign_minor

__all__ = ["assign_major", "assign_minor", "categorize_event", "add_major_minor"]


def categorize_event(category, event_name) -> tuple[str, str]:
    """Return ``(major, minor)`` for a single event."""
    major = assign_major(category, event_name)
    minor = assign_minor(category, event_name, major)
    return major, minor


def add_major_minor(
    df: pd.DataFrame,
    *,
    category_col: str = "category",
    name_col: str = "event_name",
    major_col: str = "event_majorcat",
    minor_col: str = "event_minorcat",
) -> pd.DataFrame:
    """Return a copy of ``df`` with ``event_majorcat`` and ``event_minorcat`` columns added."""
    out = df.copy()
    pairs = [
        categorize_event(c, n) for c, n in zip(out[category_col], out[name_col], strict=True)
    ]
    out[major_col] = [major for major, _ in pairs]
    out[minor_col] = [minor for _, minor in pairs]
    return out
