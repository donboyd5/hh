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


# -- donor size & persistence -------------------------------------------------
# Ordered (label, lo_inclusive, hi_exclusive) giving bands. Same bands are used for
# annual giving (donors_by_size_year) and lifetime giving (preferences chapter).
ANNUAL_TIERS = [
    ("<$100", 0, 100),
    ("$100–999", 100, 1_000),
    ("$1,000–4,999", 1_000, 5_000),
    ("$5,000+", 5_000, float("inf")),
]
TIER_LABELS = [label for label, _, _ in ANNUAL_TIERS]
LIFETIME_TIERS = ANNUAL_TIERS  # displayed name; tiers are the same bands
LARGE_DONOR_MIN = 1_000  # annual or lifetime dollars to count as a "large" donor
MAJOR_DONOR_MIN = 5_000  # "major" donor threshold


def size_tier(amount, bands=ANNUAL_TIERS) -> str:
    """Giving-tier label for one dollar amount (first band whose [lo, hi) contains it)."""
    a = float(amount)
    for label, lo, hi in bands:
        if lo <= a < hi:
            return label
    return bands[-1][0]


def annual_gifts(donations: pd.DataFrame) -> pd.DataFrame:
    """Succeeded individual gifts with the household rollup ``id`` and a gift ``year``.

    Thin convenience over :func:`succeeded_individual_gifts`: drops gifts missing a date or
    amount and adds ``year`` from ``donation_date``. The input is expected to carry the
    household rollup ``id`` column (as ``clean_donations`` produces). Totals reconcile with
    ``households_summary.total_donations`` because both start from ``succeeded_individual_gifts``.
    """
    g = succeeded_individual_gifts(donations)
    g = g.dropna(subset=["donation_date", "donation_amount"]).copy()
    g["year"] = g["donation_date"].dt.year.astype("int64")
    return g


def donors_by_size_year(annual_gifts_df: pd.DataFrame, bands=ANNUAL_TIERS) -> pd.DataFrame:
    """Donor count and dollars by giving tier by year.

    Each household-year is summed to an annual total, then tiered. Returns long rows
    ``[year, tier, donors, dollars]``.
    """
    per = annual_gifts_df.groupby(["id", "year"], as_index=False)["donation_amount"].sum()
    per["tier"] = per["donation_amount"].map(lambda a: size_tier(a, bands))
    return (
        per.groupby(["year", "tier"], observed=True)
        .agg(donors=("id", "nunique"), dollars=("donation_amount", "sum"))
        .reset_index()
    )


def donors_above_threshold_by_year(
    annual_gifts_df: pd.DataFrame, min_amount: float = LARGE_DONOR_MIN
) -> pd.DataFrame:
    """Households whose annual giving reached ``min_amount``, by year -> ``[year, donors]``."""
    per = annual_gifts_df.groupby(["id", "year"], as_index=False)["donation_amount"].sum()
    big = per[per["donation_amount"] >= min_amount]
    return (
        big.groupby("year", as_index=False)["id"]
        .nunique()
        .rename(columns={"id": "donors"})
    )


def donor_retention(annual_gifts_df: pd.DataFrame) -> pd.DataFrame:
    """Year-over-year donor retention: of households active in year Y, share active in Y+1.

    Returns ``[year, active, returned_next_year, retention]``; the final year (no next year)
    is dropped. Note a donor who died appears as "not retained" — retention is thus an upper
    bound on voluntary churn.
    """
    g = annual_gifts_df[["id", "year"]].drop_duplicates()
    years = sorted(g["year"].unique())
    rows = []
    for y, y_next in zip(years, years[1:]):
        cur = set(g.loc[g["year"] == y, "id"])
        nxt = set(g.loc[g["year"] == y_next, "id"])
        active = len(cur)
        returned = len(cur & nxt)
        rows.append(
            {
                "year": y,
                "active": active,
                "returned_next_year": returned,
                "retention": returned / active if active else 0.0,
            }
        )
    return pd.DataFrame(rows)
