"""FY26 fall-appeal response analysis at the household level.

Answers "who was appealed, who responded, and what distinguished them?" using the Neon pull as
the donation source of truth and the appeal workbook only for *who was mailed* (and its staff
segment labels). All "prior" features are computed **as of the appeal start** — engagement counts
use event ``starts_on``, not ``registered_at``, so registering in September for a November show
does not count as prior engagement, and ``households_summary`` (all-time counts) cannot be
substituted.

Response definition (confirmed with Don): a SUCCEEDED DONATION/PLEDBGEPAYMENT gift to campaign
``Annual Fund Drive - 2025-2026`` dated 2025-10-01 through 2026-01-31, rolled up to the
household — the rollup matters: ~18% of responding households gave only through a household
member's account.
"""
from __future__ import annotations

import pandas as pd

from .donors import size_tier, succeeded_individual_gifts

APPEAL_CAMPAIGN = "Annual Fund Drive - 2025-2026"
APPEAL_START = pd.Timestamp("2025-10-01")  # as-of date for every "prior" feature
APPEAL_END = pd.Timestamp("2026-01-31")  # response window close (inclusive)
PRIOR_FY = (pd.Timestamp("2024-07-01"), pd.Timestamp("2025-06-30"))  # FY25
LAPSED_AFTER = pd.Timedelta(days=730)  # no gift in 24 months pre-appeal => lapsed

# sheet priority when a household appears on more than one appeal sheet
_SEGMENT_PRIORITY = ["top", "theater", "gen"]


def campaign_gifts(
    donations: pd.DataFrame,
    *,
    campaign: str = APPEAL_CAMPAIGN,
    start: pd.Timestamp = APPEAL_START,
    end: pd.Timestamp = APPEAL_END,
) -> pd.DataFrame:
    """SUCCEEDED appeal-campaign gifts inside the window (all account types, type carried).

    Unlike :func:`succeeded_individual_gifts` this keeps Company accounts, so the corporate
    gifts that land in the same campaign stay visible and flaggable rather than silently
    excluded.
    """
    return donations[
        donations["campaign"].eq(campaign)
        & donations["donation_status"].eq("SUCCEEDED")
        & donations["donation_type"].isin(["DONATION", "PLEDBGEPAYMENT"])
        & donations["donation_date"].between(start, end)
    ].copy()


def prior_giving_features(
    donations: pd.DataFrame,
    *,
    asof: pd.Timestamp = APPEAL_START,
    prior_fy: tuple[pd.Timestamp, pd.Timestamp] = PRIOR_FY,
) -> pd.DataFrame:
    """Prior-donor profile per household rollup id, counting only gifts before ``asof``."""
    gifts = succeeded_individual_gifts(donations)
    gifts = gifts[gifts["donation_date"] < asof]
    fy_lo, fy_hi = prior_fy
    fy = gifts[gifts["donation_date"].between(fy_lo, fy_hi)]

    out = (
        gifts.groupby("id")
        .agg(
            prior_lifetime_amount=("donation_amount", "sum"),
            prior_n_gifts=("donation_id", "count"),
            prior_first_gift=("donation_date", "min"),
            prior_last_gift=("donation_date", "max"),
        )
        .reset_index()
    )
    out["prior_donor"] = out["prior_n_gifts"] > 0
    out["prior_size_tier"] = out["prior_lifetime_amount"].map(size_tier)
    out["lapsed_donor"] = out["prior_donor"] & (
        (asof - out["prior_last_gift"]) > LAPSED_AFTER
    )

    fy_roll = (
        fy.groupby("id")["donation_amount"].sum().rename("prior_fy_amount").reset_index()
    )
    out = out.merge(fy_roll, on="id", how="left")
    out["prior_fy_amount"] = out["prior_fy_amount"].fillna(0.0)
    out["prior_fy_donor"] = out["prior_fy_amount"] > 0
    return out


def engagement_asof(
    registrations: pd.DataFrame, *, asof: pd.Timestamp = APPEAL_START
) -> pd.DataFrame:
    """Attendance profile per household rollup id, counting only events that started by ``asof``."""
    regs = registrations[
        registrations["starts_on"].notna() & (registrations["starts_on"] <= asof)
    ]

    rolls = [regs.groupby("id")["registration_id"].count().rename("eng_n_registrations")]
    for cat in ("performance", "class", "community", "other"):
        rolls.append(
            regs[regs["event_majorcat"] == cat]
            .groupby("id")["registration_id"]
            .count()
            .rename(f"eng_n_{cat}")
        )
    if "event_minorcat" in regs.columns:
        for minor in ("theater", "music", "dance", "opera"):
            rolls.append(
                regs[regs["event_minorcat"] == minor]
                .groupby("id")["registration_id"]
                .count()
                .rename(f"eng_perf_{minor}")
            )
    rolls.append(regs.groupby("id")["starts_on"].max().rename("eng_last_event"))
    out = pd.concat(rolls, axis=1).reset_index()

    arts = out.get("eng_n_performance", pd.Series(0, index=out.index)) > 0
    classes = out.get("eng_n_class", pd.Series(0, index=out.index)) > 0
    out["eng_profile"] = pd.Series(
        pd.NA, index=out.index, dtype="string"
    ).mask(arts & classes, "arts+class").mask(arts, "arts").mask(classes, "class")
    # households whose only pre-appeal activity was community/other events
    out["eng_profile"] = out["eng_profile"].fillna("community/other")
    return out


def _first_nonnull(series: pd.Series):
    s = series.dropna()
    return s.iloc[0] if not s.empty else None


def appeal_household_table(
    recipients: pd.DataFrame,
    accounts_geo: pd.DataFrame,
    donations: pd.DataFrame,
    registrations: pd.DataFrame,
    *,
    asof: pd.Timestamp = APPEAL_START,
    window: tuple[pd.Timestamp, pd.Timestamp] = (APPEAL_START, APPEAL_END),
    campaign: str = APPEAL_CAMPAIGN,
) -> pd.DataFrame:
    """The canonical appeal table: one row per rollup household in the full Neon universe.

    Appeal membership is resolved through current Neon accounts (``account_id`` -> rollup
    ``id``); recipients whose account no longer exists fall back to the workbook's ``hhid``,
    and recipients with no id at all cannot be placed on a household — they stay in the
    recipients table for the QA page instead of being force-fitted here.
    """
    # universe: every rollup id in Neon, with geography and contactability flags
    universe = (
        accounts_geo.groupby("id")
        .agg(
            name=("name", _first_nonnull),
            group=("group", _first_nonnull),
            distance_band=("distance_band", _first_nonnull),
            city=("city", _first_nonnull),
            state_province=("state_province", _first_nonnull),
            zip_code=("zip_code", _first_nonnull),
            n_accounts=("account_id", "nunique"),
            has_mail=("address_line1", lambda s: s.notna().any()),
            deceased_any=("deceased", lambda s: s.fillna(False).any()),
            dnc_any=("do_not_contact", lambda s: s.fillna(False).any()),
        )
        .reset_index()
    )

    # appeal side: map recipient accounts onto the household rollup via current Neon
    acct = (
        accounts_geo[["account_id", "id"]]
        .dropna(subset=["account_id"])
        .drop_duplicates(subset=["account_id"])
        .rename(columns={"id": "neon_rollup_id"})
    )
    rec = recipients.merge(acct, on="account_id", how="left")
    rec["appeal_rollup_id"] = rec["neon_rollup_id"].fillna(rec["workbook_hhid"])
    rec["appeal_matched_in_neon"] = rec["neon_rollup_id"].notna()
    placed = rec[rec["appeal_rollup_id"].notna()].copy()

    seg = {}
    for sheet in _SEGMENT_PRIORITY:  # later (lower-priority) sheets never overwrite
        part = placed[placed["source_sheet"] == sheet]
        seg.update(zip(part["appeal_rollup_id"], part["appeal_segment"], strict=True))
    appeal = (
        placed.groupby("appeal_rollup_id")
        .agg(
            appealed_sheets=("source_sheet", lambda s: ";".join(sorted(set(s)))),
            n_appeal_rows=("source_sheet", "count"),
            appeal_gift_recorded_sum=("appeal_gift_recorded", "sum"),
            appeal_matched_in_neon=("appeal_matched_in_neon", "any"),
        )
        .reset_index()
        .rename(columns={"appeal_rollup_id": "id"})
    )
    appeal["appeal_segment"] = appeal["id"].map(seg)

    # response side: campaign gifts in the window, rolled up to the household
    gifts = campaign_gifts(donations, campaign=campaign, start=window[0], end=window[1])
    response = (
        gifts.groupby("id")
        .agg(
            afd_n_gifts=("donation_id", "count"),
            afd_amount=("donation_amount", "sum"),
            afd_company_gift=("account_type", lambda s: (s == "Company").any()),
        )
        .reset_index()
    )

    table = (
        universe.merge(appeal, on="id", how="left")
        .merge(response, on="id", how="left")
        .merge(prior_giving_features(donations, asof=asof), on="id", how="left")
        .merge(engagement_asof(registrations, asof=asof), on="id", how="left")
    )

    table["appealed"] = table["appealed_sheets"].notna()
    table["responded"] = table["afd_n_gifts"].fillna(0) > 0
    for c in (
        "n_appeal_rows",
        "appeal_gift_recorded_sum",
        "afd_n_gifts",
        "afd_amount",
        "prior_lifetime_amount",
        "prior_n_gifts",
        "prior_fy_amount",
        "eng_n_registrations",
        "eng_n_performance",
        "eng_n_class",
        "eng_n_community",
        "eng_n_other",
        "eng_perf_theater",
        "eng_perf_music",
        "eng_perf_dance",
        "eng_perf_opera",
    ):
        if c in table.columns:
            table[c] = table[c].fillna(0)
    for c in (
        "afd_company_gift",
        "prior_donor",
        "prior_fy_donor",
        "lapsed_donor",
    ):
        if c in table.columns:
            table[c] = table[c].fillna(False)
    table["eng_profile"] = table["eng_profile"].fillna("none")

    return table


def reconcile_eoy_export(
    eoy_gifts: pd.DataFrame, neon_donations: pd.DataFrame, accounts: pd.DataFrame
) -> pd.DataFrame:
    """Match each EoY export gift to Neon (email first, then first+last name + zip5).

    A QA artifact only — Neon drives every response flag. Beyond the match itself we report
    whether the matched household has appeal-window campaign gifts in Neon, which is what
    explains most workbook-vs-export dollar gaps (the export predates later gifts).
    """
    afd = campaign_gifts(neon_donations)
    afd_roll = (
        afd.groupby("id")
        .agg(neon_afd_n_gifts=("donation_id", "count"), neon_afd_amount=("donation_amount", "sum"))
        .reset_index()
    )

    acct = accounts[["account_id", "id", "email_1", "first_name", "last_name", "zip_code"]].copy()
    acct["email_key"] = acct["email_1"].astype("string").str.strip().str.lower()
    # zips normalize to zero-padded 5 digits (Neon stores 5201.0, exports say "05201")
    acct["name_zip_key"] = (
        acct["first_name"].astype("string").str.strip().str.lower()
        + "|"
        + acct["last_name"].astype("string").str.strip().str.lower()
        + "|"
        + acct["zip_code"]
        .astype("string")
        .str.strip()
        .str.replace(".0", "", regex=False)
        .str.zfill(5)
        .str.slice(0, 5)
    )
    by_email = acct.dropna(subset=["email_key"]).drop_duplicates(subset=["email_key"])
    by_name = acct.dropna(subset=["name_zip_key"]).drop_duplicates(subset=["name_zip_key"])

    out = eoy_gifts.merge(
        by_email[["email_key", "account_id", "id"]].rename(
            columns={"account_id": "matched_account_id", "id": "matched_rollup_id"}
        ),
        left_on="email",
        right_on="email_key",
        how="left",
    )
    via_email = out["matched_account_id"].notna()

    name_zip = eoy_gifts["donor_first"].astype("string").str.strip().str.lower() + "|" + (
        eoy_gifts["donor_last"].astype("string").str.strip().str.lower()
        + "|"
        + eoy_gifts["zip5"].astype("string")
    )
    unmatched = out["matched_account_id"].isna()
    fallback = (
        pd.DataFrame({"name_zip_key": name_zip[unmatched]})
        .merge(by_name[["name_zip_key", "account_id", "id"]], on="name_zip_key", how="left")
        .set_index(unmatched[unmatched].index)
    )
    out.loc[unmatched, "matched_account_id"] = fallback["account_id"]
    out.loc[unmatched, "matched_rollup_id"] = fallback["id"]

    out["match_method"] = "unmatched"
    out.loc[via_email, "match_method"] = "email"
    out.loc[~via_email & out["matched_account_id"].notna(), "match_method"] = "name-zip"

    out = out.drop(columns=["email_key"], errors="ignore").merge(
        afd_roll.rename(columns={"id": "matched_rollup_id"}), on="matched_rollup_id", how="left"
    )
    return out
