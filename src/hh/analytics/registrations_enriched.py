"""Enrich registrations with attendee geography (distance band) and event timing (weekday).

This is the flexible attendance table for free-form questions: each registration row carries the
event's major/minor category, start date, weekday, and the attendee household's distance band +
geo precision. Slice freely, e.g.:
  music by weekday:        df[df.event_minorcat == 'music'].groupby('weekday')
  theater by day x band:   df[df.event_minorcat == 'theater']
                            .groupby(['weekday', 'distance_band'])
  class-takers <= 10 mi:   df[(df.event_majorcat == 'class')
                            & (df.distance_band == '<= 10 mi')]
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


def enrich_registrations(
    registrations: pd.DataFrame,
    accounts_geo: pd.DataFrame,
) -> pd.DataFrame:
    """Add distance_band, geo_precision (from attendee account) and weekday (from event date)."""
    reg = registrations.copy()
    band = (
        accounts_geo[["account_id", "distance_band", "geo_precision"]]
        .drop_duplicates(subset=["account_id"])
    )
    reg = reg.merge(band, on="account_id", how="left")
    if "starts_on" in reg.columns:
        reg["weekday"] = pd.Categorical(
            reg["starts_on"].dt.day_name(), categories=WEEKDAY_ORDER, ordered=True
        )
    return reg
