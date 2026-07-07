"""Timing analysis: attendance and revenue by day of week, split by event category.

Answers "What days of the week are best for theater performances? Music?" using each event's
performance date (``starts_on``), aggregated from registrations. Attendance is proxied by the
count of registrations (true headcount would require flattening the nested ``tickets`` arrays).
"""
from __future__ import annotations

import pandas as pd

WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


def add_weekday(
    df: pd.DataFrame, *, date_col: str = "starts_on", out: str = "weekday"
) -> pd.DataFrame:
    """Return a copy of df with a ``weekday`` column (day name) derived from ``date_col``."""
    d = df.copy()
    d[out] = d[date_col].dt.day_name()
    return d


def timing_by_weekday(
    df: pd.DataFrame,
    *,
    category: str | None = None,
    minor: str | None = None,
    value_col: str = "amount",
    date_col: str = "starts_on",
    count_col: str = "registration_id",
) -> pd.DataFrame:
    """Attendance and revenue by weekday, optionally filtered to a major/minor category."""
    d = df
    if category is not None and "event_majorcat" in d.columns:
        d = d[d["event_majorcat"] == category]
    if minor is not None and "event_minorcat" in d.columns:
        d = d[d["event_minorcat"] == minor]
    d = d.dropna(subset=[date_col]).copy()
    d["weekday"] = d[date_col].dt.day_name()
    count = count_col if count_col in d.columns else d.columns[0]
    agg = (
        d.groupby("weekday", observed=True)
        .agg(attendance=(count, "count"), revenue=(value_col, "sum"))
        .reset_index()
    )
    agg["weekday"] = pd.Categorical(agg["weekday"], categories=WEEKDAY_ORDER, ordered=True)
    return agg.sort_values("weekday").reset_index(drop=True)


def best_weekday(df: pd.DataFrame, *, metric: str = "attendance", **kwargs):
    """Return (weekday, value) with the highest attendance or revenue for the given filter."""
    table = timing_by_weekday(df, **kwargs)
    if table.empty:
        return None, 0
    row = table.loc[table[metric].idxmax()]
    return str(row["weekday"]), row[metric]
