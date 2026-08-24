"""End-of-year FY26 campaign donation export (``End of Yr Campaign Donations FY26.xlsx``).

A single-sheet Neon export of gifts to the FY26 annual fund, taken mid-campaign — earlier and
less complete than the July 2026 Neon pull, and carrying **no Neon ids**. It is used purely as
a QA cross-check (:func:`hh.analytics.appeal.reconcile_eoy_export`), never as a donation source.

One trailing TOTAL row (name fields all null) must be dropped before use.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .. import config

EOY_FILENAME = "End of Yr Campaign Donations FY26.xlsx"

# export header -> standard name
EOY_FIELDS = {
    "First Name": "donor_first",
    "Last Name": "donor_last",
    "Household Name": "household_name",
    "Household Salutation": "household_salutation",
    "Address Line 1": "address_line1",
    "Address Line 2": "address_line2",
    "City": "city",
    "State/Province": "state_province",
    "Zip Code": "zip_code",
    "Email 1": "email",
    "Phone 1 Full Number (F)": "phone",
    "Donation Date": "donation_date",
    "Donation Amount": "donation_amount",
    "Source": "source",
    "Campaign Name": "campaign",
    "Donor Covered Fees": "donor_covered_fees",
    "First Donation Date": "first_donation_date",
    "Last Donation Date": "last_donation_date",
    "Anonymous Donation": "anonymous_raw",
    "2025-2026 Fiscal Yr Donations": "fy26_total",
}


def eoy_path() -> Path:
    """Default location of the EoY export under the external data layer."""
    return config.layer_dir("external") / EOY_FILENAME


def load_eoy_gifts(path: Path | None = None) -> pd.DataFrame:
    """Read the export sheet (exact filename; never a glob)."""
    src = Path(path) if path is not None else eoy_path()
    return pd.read_excel(src, sheet_name="export")


def _to_datetime(series: pd.Series) -> pd.Series:
    """Dates may arrive as datetimes (openpyxl converts date-formatted cells) or Excel serials."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series
    numeric = pd.to_numeric(series, errors="coerce")
    dt = pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")
    # non-serial strings (e.g. "2025-12-01") fall back to plain parsing
    return dt.fillna(pd.to_datetime(series, errors="coerce"))


def clean_eoy_gifts(raw: pd.DataFrame | None = None, *, path: Path | None = None) -> pd.DataFrame:
    """Standardized EoY gift rows with the TOTAL row dropped and emails normalized."""
    df = raw if raw is not None else load_eoy_gifts(path)
    df = df.rename(columns={k: v for k, v in EOY_FIELDS.items() if k in df.columns})

    # the trailing TOTAL row carries only amount/date/total fields — no donor identity
    df = df[~(df["donor_first"].isna() & df["donor_last"].isna() & df["household_name"].isna())]

    df["donation_date"] = _to_datetime(df["donation_date"])
    for c in ("first_donation_date", "last_donation_date"):
        if c in df.columns:
            df[c] = _to_datetime(df[c])
    df["donation_amount"] = pd.to_numeric(df["donation_amount"], errors="coerce")

    def _opt(name: str) -> pd.Series:
        """Optional column as a clean string series when the export includes it."""
        if name not in df.columns:
            return pd.Series(pd.NA, index=df.index, dtype="string")
        return df[name].astype("string").str.strip()

    df["email"] = _opt("email").str.lower()
    # Neon/Excel zips arrive as 5201.0 or "05201" — normalize to zero-padded 5 digits
    df["zip5"] = _opt("zip_code").str.replace(".0", "", regex=False).str.zfill(5).str.slice(0, 5)
    df["anonymous"] = _opt("anonymous_raw").eq("Donor Name Anonymous")
    return df.reset_index(drop=True)
