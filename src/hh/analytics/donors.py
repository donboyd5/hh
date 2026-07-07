"""Donor geography: donor households and donation $ by distance band.

Answers "How many donors (and what $ share) live within 1 / 10 / 20+ miles?" using the geocoded
accounts' distance band. Applies R's clean-donor filter: SUCCEEDED DONATION/PLEDGEPAYMENT from
living, contactable individuals, excluding the junk account 36805.
"""
from __future__ import annotations

import pandas as pd

JUNK_ACCOUNT_IDS = ("36805",)


def succeeded_individual_gifts(donations: pd.DataFrame) -> pd.DataFrame:
    """SUCCEEDED DONATION/PLEDBGEPAYMENT gifts from individual accounts."""
    return donations[
        donations["donation_status"].astype(str).eq("SUCCEEDED")
        & donations["donation_type"].isin(["DONATION", "PLEDBGEPAYMENT"])
        & donations["account_type"].astype(str).eq("Individual")
    ].copy()


def donors_by_band(
    accounts_geo: pd.DataFrame,
    donations: pd.DataFrame,
    *,
    exclude_account_ids: tuple[str, ...] = JUNK_ACCOUNT_IDS,
) -> pd.DataFrame:
    """Donor households, gift count, and total $ by distance band (clean donors only)."""
    gifts = succeeded_individual_gifts(donations)
    # use account-level deceased/do_not_contact (drop any donation-side copies to avoid collisions)
    gifts = gifts.drop(
        columns=[c for c in ("deceased", "do_not_contact") if c in gifts.columns],
        errors="ignore",
    )
    flags = accounts_geo.set_index("account_id")[
        ["distance_band", "geo_precision", "deceased", "do_not_contact"]
    ]
    gifts = gifts.merge(flags, on="account_id", how="left")
    gifts = gifts[
        ~gifts["deceased"].fillna(False)
        & ~gifts["do_not_contact"].fillna(False)
        & ~gifts["account_id"].isin(exclude_account_ids)
        & gifts["distance_band"].notna()
    ]
    table = (
        gifts.groupby("distance_band", observed=True)
        .agg(
            total_donations=("donation_amount", "sum"),
            n_gifts=("donation_id", "count"),
            donor_households=("household_id", "nunique"),
            donor_accounts=("account_id", "nunique"),
        )
        .reset_index()
    )
    grand = table["total_donations"].sum()
    table["share_of_donations"] = table["total_donations"] / grand if grand else 0.0
    return table


def centroid_share_by_band(accounts_geo: pd.DataFrame) -> pd.Series:
    """Share of accounts in each band that are ZIP-centroid (approximate) placements."""
    have = accounts_geo[accounts_geo["distance_band"].notna()]
    if have.empty:
        return pd.Series(dtype=float)
    return have.groupby("distance_band", observed=True)["geo_precision"].apply(
        lambda s: (s == "centroid").mean()
    )
