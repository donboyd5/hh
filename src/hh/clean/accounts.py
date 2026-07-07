"""Clean raw Neon accounts into a standardized table with the household rollup.

Maps API output-field names to standard names, converts the deceased / do-not-contact flags to
booleans (R converted from "Yes"/NA), and adds the canonical id/name/group rollup.
"""
from __future__ import annotations

import pandas as pd

from ..io import load_raw
from .households import add_rollup
from .standardize import standardize_columns, yes_to_bool

# Neon API output-field name -> standard name (accounts).
ACCOUNT_FIELDS = {
    "Account ID": "account_id",
    "Account Type": "account_type",
    "First Name": "first_name",
    "Last Name": "last_name",
    "Full Name (F)": "full_name",
    "Company Name": "company_name",
    "Household ID": "household_id",
    "Household Name": "household_name",
    "Contact Type": "contact_type",
    "Deceased": "deceased",
    "Do Not Contact": "do_not_contact",
    "Full Street Address (F)": "full_street_address",
    "Address Line 1": "address_line1",
    "Address Line 2": "address_line2",
    "City": "city",
    "State/Province": "state_province",
    "Zip Code": "zip_code",
    "Country": "country",
    "Email 1": "email_1",
    "Phone 1 Full Number (F)": "phone_1",
}


def clean_accounts(raw: pd.DataFrame | None = None, *, pull_dir=None) -> pd.DataFrame:
    """Return cleaned accounts with id/name/group; reads the latest pull if ``raw`` is None."""
    df = raw if raw is not None else load_raw("accounts", pull_dir=pull_dir)
    df = standardize_columns(df, mapping=ACCOUNT_FIELDS)
    if "deceased" in df.columns:
        df["deceased"] = yes_to_bool(df["deceased"])
    if "do_not_contact" in df.columns:
        df["do_not_contact"] = yes_to_bool(df["do_not_contact"])
    df = add_rollup(df, name_cols=("household_name", "full_name", "company_name"))
    return df
