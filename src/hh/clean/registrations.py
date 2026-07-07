"""Clean raw Neon registrations into a standardized table with event category + household rollup.

Registration records use camelCase API fields (``eventId``, ``registrantAccountId``,
``registrationAmount``, ``registrationDateTime``) and carry no name/household, so we join the
cleaned events (for ``event_majorcat``) and accounts (for household membership). The per-event
sweep annotated each record with ``_swept_event_id`` as a fallback for ``eventId``.
"""
from __future__ import annotations

import pandas as pd

from ..io import load_raw
from .households import add_rollup
from .standardize import standardize_columns

# Neon API field (camelCase) -> standard name (registrations).
REGISTRATION_FIELDS = {
    "id": "registration_id",
    "eventId": "event_id",
    "registrantAccountId": "account_id",
    "registrationAmount": "amount",
    "registrationDateTime": "registered_at",
    "source": "source",
    "origin": "origin",
}


def clean_registrations(
    raw: pd.DataFrame | None = None,
    *,
    pull_dir=None,
    events: pd.DataFrame | None = None,
    accounts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return cleaned registrations with event category and household rollup."""
    df = raw if raw is not None else load_raw("registrations", pull_dir=pull_dir)
    df = standardize_columns(df, mapping=REGISTRATION_FIELDS)
    # fall back to the swept event id if the record's own eventId is missing
    if "_swept_event_id" in df.columns:
        if "event_id" not in df.columns:
            df["event_id"] = df["_swept_event_id"]
        else:
            df["event_id"] = df["event_id"].fillna(df["_swept_event_id"])
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if "registered_at" in df.columns:
        df["registered_at"] = pd.to_datetime(df["registered_at"], errors="coerce")

    if events is not None and "event_id" in df.columns and "event_id" in events.columns:
        ev = (
            events[["event_id", "event_majorcat", "event_name", "starts_on"]]
            .dropna(subset=["event_id"])
            .drop_duplicates(subset=["event_id"])
        )
        df = df.merge(ev, on="event_id", how="left", suffixes=("", "_ev"))

    if accounts is not None and "account_id" in df.columns and "account_id" in accounts.columns:
        link = (
            accounts[["account_id", "household_id", "household_name", "full_name"]]
            .dropna(subset=["account_id"])
            .drop_duplicates(subset=["account_id"])
        )
        df = df.merge(link, on="account_id", how="left", suffixes=("", "_acct"))

    df = add_rollup(df, name_cols=("household_name", "full_name"))
    return df
