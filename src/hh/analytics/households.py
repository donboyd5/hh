"""Household-level summary: geography + donations + attendance by category + flags.

One row per constituent rollup id (a household, or a standalone account) carrying everything needed
for donor/patron/class overlap and profiling questions. The flexible companion to
``enrich_registrations``.
"""
from __future__ import annotations

import pandas as pd

from .donors import succeeded_individual_gifts

_CATEGORY_COLS = ["performance", "class", "community", "other"]
_PERF_MINOR_COLS = ["theater", "music", "dance", "opera"]


def _first_nonnull(series: pd.Series):
    s = series.dropna()
    return s.iloc[0] if not s.empty else None


def household_summary(
    accounts_geo: pd.DataFrame,
    donations: pd.DataFrame,
    registrations: pd.DataFrame,
) -> pd.DataFrame:
    """One row per rollup id with geography, donation totals, attendance counts, and flags."""
    # geography + identity per id
    geo = (
        accounts_geo.groupby("id")
        .agg(
            name=("name", _first_nonnull),
            group=("group", _first_nonnull),
            distance_band=("distance_band", _first_nonnull),
            geo_precision=("geo_precision", _first_nonnull),
            city=("city", _first_nonnull),
            state_province=("state_province", _first_nonnull),
            zip_code=("zip_code", _first_nonnull),
            n_accounts=("account_id", "nunique"),
        )
        .reset_index()
    )

    # donations (succeeded individual gifts) per id
    don = succeeded_individual_gifts(donations)
    don_roll = (
        don.groupby("id")
        .agg(
            total_donations=("donation_amount", "sum"),
            n_donations=("donation_id", "count"),
            first_donation=("donation_date", "min"),
            last_donation=("donation_date", "max"),
        )
        .reset_index()
    )

    # registrations per id: total + by major category + by performance minor
    reg = registrations
    rolls = [reg.groupby("id")["registration_id"].count().rename("n_registrations")]
    for cat in _CATEGORY_COLS:
        rolls.append(
            reg[reg["event_majorcat"] == cat]
            .groupby("id")["registration_id"]
            .count()
            .rename(f"n_{cat}")
        )
    for minor in _PERF_MINOR_COLS:
        rolls.append(
            reg[reg["event_minorcat"] == minor]
            .groupby("id")["registration_id"]
            .count()
            .rename(f"n_perf_{minor}")
        )
    reg_roll = pd.concat(rolls, axis=1).reset_index()

    h = geo.merge(don_roll, on="id", how="left").merge(reg_roll, on="id", how="left")

    count_cols = (
        ["total_donations", "n_donations", "n_registrations"]
        + [f"n_{c}" for c in _CATEGORY_COLS]
        + [f"n_perf_{m}" for m in _PERF_MINOR_COLS]
    )
    for c in count_cols:
        if c in h.columns:
            h[c] = h[c].fillna(0)

    h["is_donor"] = h["total_donations"] > 0
    h["is_patron"] = h["n_performance"] > 0
    h["is_class_taker"] = h["n_class"] > 0
    return h
