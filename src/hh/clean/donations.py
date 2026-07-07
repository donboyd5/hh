"""Clean raw Neon donations into a standardized table with household rollup.

The API's donation records carry ``account_id`` but not ``household_id``, so household membership
is recovered by joining the cleaned accounts table on ``account_id`` (the R project did the same
via its "linkages" file). Amounts/dates are parsed; deceased/DNC become booleans.
"""
from __future__ import annotations

import pandas as pd

from ..io import load_raw
from .households import add_rollup
from .standardize import standardize_columns, yes_to_bool

# Neon API output-field name -> standard name (donations).
DONATION_FIELDS = {
    "Donation ID": "donation_id",
    "Account ID": "account_id",
    "Account Type": "account_type",
    "Donation Date": "donation_date",
    "Donation Amount": "donation_amount",
    "Donation Type": "donation_type",
    "Donation Status": "donation_status",
    "Payment Status": "payment_status",
    "Fund": "fund",
    "Campaign Name": "campaign",
    "Purpose": "purpose",
    "Source": "source",
    "Full Name (F)": "full_name",
    "Company Name": "company_name",
    "City": "city",
    "Address Line 1": "address_line1",
    "State/Province": "state_province",
    "Zip Code": "zip_code",
    "Deceased": "deceased",
    "Do Not Contact": "do_not_contact",
}


def clean_donations(
    raw: pd.DataFrame | None = None,
    *,
    pull_dir=None,
    accounts: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return cleaned donations. Pass cleaned ``accounts`` to recover household_id/name."""
    df = raw if raw is not None else load_raw("donations", pull_dir=pull_dir)
    df = standardize_columns(df, mapping=DONATION_FIELDS)
    if "donation_amount" in df.columns:
        df["donation_amount"] = pd.to_numeric(df["donation_amount"], errors="coerce")
    if "donation_date" in df.columns:
        df["donation_date"] = pd.to_datetime(df["donation_date"], errors="coerce")
    for flag in ("deceased", "do_not_contact"):
        if flag in df.columns:
            df[flag] = yes_to_bool(df[flag])
    if accounts is not None and "account_id" in df.columns and "account_id" in accounts.columns:
        link = (
            accounts[["account_id", "household_id", "household_name"]]
            .dropna(subset=["account_id"])
            .drop_duplicates(subset=["account_id"])
        )
        df = df.merge(link, on="account_id", how="left", suffixes=("", "_from_acct"))
    df = add_rollup(df, name_cols=("household_name", "full_name", "company_name"))
    return df
