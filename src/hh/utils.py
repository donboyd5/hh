"""Small helpers ported from the R project (ns() peek, fiscal year)."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd


def ns(df: pd.DataFrame) -> pd.DataFrame:
    """Print column names and dimensions; return df unchanged (R-style peek)."""
    names = ", ".join(df.columns.astype(str))
    print(f"[{len(df):,} rows x {df.shape[1]} cols] {names}")
    return df


def hhfy(d, start_month: int = 7):
    """Hubbard Hall fiscal year: month >= start_month -> year + 1, else year.

    Port of R ``analysis.qmd`` (``hhfy = ifelse(month(date) >= 7, year(date)+1, year(date))``).
    Accepts a single date/datetime/Timestamp or a pandas Series of datetimes.
    """
    if isinstance(d, pd.Series):
        year = d.dt.year
        return year.where(d.dt.month < start_month, year + 1)
    if isinstance(d, pd.Timestamp | date | datetime):
        return d.year + 1 if d.month >= start_month else d.year
    raise TypeError(f"hhfy() expected a date or pandas Series, got {type(d)!r}")
