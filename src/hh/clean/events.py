"""Clean raw Neon events (from the API) into a standardized, categorized table.

Maps the API's output-field names to the project's standard names, parses types, and applies the
two-stage categorizer (major/minor) ported from R. Category values come straight from Neon, so
running this on live data is the real test of whether the R-ported rules still apply (de novo from
API data, per the project directive).
"""
from __future__ import annotations

import pandas as pd

from ..categorize import add_major_minor
from ..io import load_raw
from .standardize import standardize_columns

# Neon API output-field name -> standard name (events).
EVENT_FIELDS = {
    "Event ID": "event_id",
    "Event Name": "event_name",
    "Event Category Name": "category",
    "Event Topic": "topic",
    "Event Code": "code",
    "Event Start Date": "starts_on",
    "Event End Date": "ends_on",
    "Event Capacity": "capacity",
    "Event Registration Attendee Count": "attendees",
}


def clean_events(raw: pd.DataFrame | None = None, *, pull_dir=None) -> pd.DataFrame:
    """Return cleaned, categorized events. Reads the latest saved pull if ``raw`` is None."""
    df = raw if raw is not None else load_raw("events", pull_dir=pull_dir)
    df = standardize_columns(df, mapping=EVENT_FIELDS)
    for col in ("category", "event_name"):
        if col not in df.columns:
            df[col] = pd.NA
    for col in ("starts_on", "ends_on"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ("attendees", "capacity"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = add_major_minor(df)
    return df
