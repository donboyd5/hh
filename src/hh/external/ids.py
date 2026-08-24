"""ID coercion for external spreadsheets.

Neon ids are strings without decimals in every cleaned table (``"40486"``), but Excel exports
them as floats (``40486.0``) or left-padded text. :func:`coerce_id` normalizes all three to the
Neon form so external ids join cleanly against ``account_id`` / ``household_id``.
"""
from __future__ import annotations

import pandas as pd


def coerce_id(series: pd.Series) -> pd.Series:
    """Normalize a column of Neon ids (float / int / string / blank) to clean strings.

    ``40486.0``, ``40486``, and ``"40486"`` all become ``"40486"``; blanks and non-numeric
    values become ``pd.NA``. The round-trip through Int64 drops any stray ``.0`` suffix.
    """
    return (
        pd.to_numeric(series, errors="coerce").astype("Int64").astype("string")
    )
