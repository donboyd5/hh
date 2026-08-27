"""Potential-donor mailing list: one row per household across all inclusion sources.

Built from the cleaned Neon tables plus the external workbook lists (see
``hh.external.mailing`` and ``hh.external.fortsalem``). Everything here is PII — the output
lives under gitignored ``data/20_processed/`` and is never published.

Conventions (confirmed with Don, 2026-08-27):

- **Fiscal year** ends June 30 and is labeled by its ending year (FY24 = 2023-07-01 …
  2024-06-30), matching Judy's "2023-2024 Fiscal Yr" report columns and Neon campaign names.
- **Giving window** = FY22–FY26; **de minimis** for the 5-year donor rule = $10 total
  (the minimum on Judy's 3-year list).
- **Engagement window** = FY24–FY26. ``arts`` spend = registrations categorized
  performance + other (performances, events, films, galas); ``classes`` = class; community
  is reported separately. ``predominant_engagement`` compares arts vs class spend:
  arts / classes / both / none.
- **New households** (not in Neon) get codes ``new1``, ``new2``, … in name order.
- The **household contact** is the member account with the most lifetime gifts, breaking
  ties by earliest account creation; contact fields fall back across the household's other
  accounts when the contact's own are blank.

Fort Salem individuals that are *not* in Neon are included with ``needs_review=True``:
Don decides who to keep and who to drop before any outreach (never an automated mailing).
Individuals already in Neon are only *flagged* ``fst`` when they qualify via a Neon source —
being a Fort Salem sponsor alone does not add an existing Neon household, per the spec.
"""
from __future__ import annotations

import pandas as pd

from ..analytics.donors import succeeded_individual_gifts

FY_MONTH = 7  # fiscal year starts July 1

GIVING_FYS = (2022, 2023, 2024, 2025, 2026)
ENGAGEMENT_FYS = (2024, 2025, 2026)
DE_MINIMIS_5YR = 10.0

# registration category -> engagement group for the mailing list
CATEGORY_GROUPS = {
    "performance": "arts",
    "other": "arts",  # galas, fundraisers, films — events in Don's "arts" sense
    "class": "classes",
    "community": "community",
}

DON_FY_COLUMNS = [f"don_fy{fy}" for fy in GIVING_FYS]

OUTPUT_COLUMNS = [
    # identity
    "id", "neon_ids", "new_code", "household_name", "in_neon",
    # inclusion sources
    "src_donor_5yr", "src_donor3", "src_new_accounts", "src_appeal_responded",
    "src_silent_selected", "fst", "needs_review",
    # donor indicators and totals
    "never_donated", "gave_fy26", "gave_fy25", "no_gift_last_5yrs",
    *DON_FY_COLUMNS, "don_5yr_total", "don_lifetime",
    # engagement
    "arts_spend_3fy", "classes_spend_3fy", "community_spend_3fy", "regs_3fy",
    "predominant_engagement",
    # contact / mailing
    "contact_first_name", "contact_last_name", "salutation", "address", "city",
    "state_province", "zip_code", "phone", "email", "do_not_contact", "deceased",
    "distance_miles",
    # stewardship
    "steward", "steward_detail", "note_donor3", "note_new", "note_silent", "note_neon",
    # Fort Salem detail
    "fst_years", "fst_years_list", "fst_best_tier",
]


def fiscal_year(dates: pd.Series | pd.Index | list) -> pd.Series:
    """FY label (ending year) for each date; July 1 starts a new fiscal year."""
    d = pd.to_datetime(pd.Series(dates), errors="coerce")
    return (d.dt.year + (d.dt.month >= FY_MONTH)).astype("Int64")


def gifts_by_fy(donations: pd.DataFrame, fys: tuple[int, ...]) -> pd.DataFrame:
    """Household × FY succeeded-gift totals: one row per rollup id, one column per FY."""
    g = succeeded_individual_gifts(donations)
    g = g.assign(fy=fiscal_year(g["donation_date"]))
    g = g[g["fy"].isin(fys)]
    table = g.pivot_table(
        index="id", columns="fy", values="donation_amount", aggfunc="sum", fill_value=0.0
    )
    table = table.reindex(columns=list(fys), fill_value=0.0)
    table.columns = [f"don_fy{int(c)}" for c in table.columns]
    return table.reset_index()


def engagement_spend(registrations: pd.DataFrame, fys: tuple[int, ...]) -> pd.DataFrame:
    """Household registration dollars by engagement group (arts/classes/community) + counts."""
    r = registrations.copy()
    r["fy"] = fiscal_year(r["starts_on"])
    r = r[r["fy"].isin(fys) & r["event_majorcat"].isin(CATEGORY_GROUPS)]
    r["group"] = r["event_majorcat"].map(CATEGORY_GROUPS)
    spend = r.pivot_table(
        index="household_id", columns="group", values="amount", aggfunc="sum", fill_value=0.0
    )
    spend = spend.reindex(columns=["arts", "classes", "community"], fill_value=0.0)
    spend.columns = [f"{c}_spend_3fy" for c in spend.columns]
    counts = r.groupby("household_id").size().rename("regs_3fy")
    return spend.join(counts).reset_index().rename(columns={"household_id": "id"})


def predominant_engagement(row: pd.Series) -> str:
    """arts / classes / both / none, comparing 3-FY arts vs class spend."""
    arts = float(row.get("arts_spend_3fy") or 0.0)
    classes = float(row.get("classes_spend_3fy") or 0.0)
    if arts > 0 and classes > 0:
        return "both"
    if arts > 0:
        return "arts"
    if classes > 0:
        return "classes"
    return "none"


# account field -> contact output field (picked contact-first, falling back across members)
_CONTACT_FIELDS = {
    "account_id": "contact_account_id",
    "first_name": "contact_first_name",
    "last_name": "contact_last_name",
    "household_salutation": "salutation_hh",
    "salutation": "salutation_ind",
    "address_line1": "address",
    "address_line2": "address2",
    "city": "city",
    "state_province": "state_province",
    "zip_code": "zip_code",
    "phone_1": "phone",
    "email_1": "email",
    "account_note_text": "note_neon",
    "distance_miles": "distance_miles",
}


def pick_contact(accounts: pd.DataFrame, donations: pd.DataFrame) -> pd.DataFrame:
    """One contact row per household rollup id (most lifetime gifts, earliest created first).

    String fields take the first non-null value down the household's member list sorted
    contact-first, so a blank on the contact falls back to other members. ``deceased`` and
    ``do_not_contact`` are household-level ANY-flags — one flagged member marks the
    household. Address lines 1 and 2 are concatenated into ``address``.
    """
    g = succeeded_individual_gifts(donations)
    gifts = g.groupby("account_id")["donation_id"].count().rename("n_gifts")
    a = accounts.drop_duplicates(subset=["account_id"]).merge(gifts, on="account_id", how="left")
    a["n_gifts"] = a["n_gifts"].fillna(0)
    a["created"] = pd.to_datetime(a.get("account_created_at"), errors="coerce")
    a = a.sort_values(["id", "n_gifts", "created"], ascending=[True, False, True])
    a = a.rename(columns=_CONTACT_FIELDS)

    fields = list(_CONTACT_FIELDS.values())
    present = [f for f in fields if f in a.columns]
    contact = a.groupby("id", sort=True)[present].first().reset_index()
    for missing in set(fields) - set(present):
        contact[missing] = pd.NA  # e.g. pre-enrichment frames without the 2026-08 fields
    anyflag = a.groupby("id", sort=True)[["deceased", "do_not_contact"]].max().reset_index()
    contact = contact.merge(anyflag, on="id")

    line1 = contact.pop("address").astype("string").str.strip()
    line2 = contact.pop("address2").astype("string").str.strip()
    both_blank = line1.isna() & line2.isna()
    joined = (line1.fillna("") + " " + line2.fillna("")).str.strip()
    contact["address"] = joined.mask(both_blank, pd.NA)

    # salutation: the household-level field wins, the account-level one fills gaps
    hh_sal = contact.pop("salutation_hh").astype("string") if "salutation_hh" in contact else pd.NA
    ind_sal = contact.pop("salutation_ind").astype("string") if "salutation_ind" in contact else pd.NA
    contact["salutation"] = hh_sal.fillna(ind_sal)
    return contact


def neon_ids_by_household(accounts: pd.DataFrame) -> pd.DataFrame:
    """Comma-joined, sorted Neon account ids per household rollup id."""
    return (
        accounts.dropna(subset=["id"])
        .groupby("id", sort=True)["account_id"]
        .agg(lambda s: ",".join(sorted(s.dropna().astype(str))))
        .rename("neon_ids")
        .reset_index()
    )


def _new_codes(names: pd.Series) -> pd.Series:
    """``new1``, ``new2``, … assigned in name order (stable across reruns)."""
    order = sorted(range(len(names)), key=lambda i: str(names.iloc[i]))
    codes = pd.Series(pd.NA, index=names.index, dtype="string")
    for rank, i in enumerate(order, start=1):
        codes.iloc[i] = f"new{rank}"
    return codes


def build_mailing_list(
    accounts: pd.DataFrame,
    donations: pd.DataFrame,
    registrations: pd.DataFrame,
    *,
    donor3: pd.DataFrame,
    new_accounts: pd.DataFrame,
    silent_selected: pd.DataFrame,
    appeal_responded: pd.DataFrame,
    fst_summary: pd.DataFrame,
) -> pd.DataFrame:
    """Assemble the mailing list.

    External frames are keyed by matched rollup ``id`` (from
    :func:`hh.external.mailing.match_households`); ``fst_summary`` additionally carries
    ``in_neon`` (bool). Returns one row per household in :data:`OUTPUT_COLUMNS` order.
    """
    households = accounts[["id", "name"]].drop_duplicates(subset=["id"])

    gifts_fy = gifts_by_fy(donations, GIVING_FYS)
    lifetime = (
        succeeded_individual_gifts(donations)
        .groupby("id")["donation_amount"].sum().rename("don_lifetime").reset_index()
    )
    engage = engagement_spend(registrations, ENGAGEMENT_FYS)
    contact = pick_contact(accounts, donations)
    neon_ids = neon_ids_by_household(accounts)

    # -- id sets per source --------------------------------------------------------
    donor5_ids = set(gifts_fy.loc[gifts_fy[DON_FY_COLUMNS].sum(axis=1) >= DE_MINIMIS_5YR, "id"])
    d3_ids = set(donor3["id"].dropna())
    na_ids = set(new_accounts["id"].dropna())
    silent_ids = set(silent_selected["id"].dropna())
    resp_ids = set(appeal_responded["id"].dropna())
    ids = donor5_ids | d3_ids | na_ids | silent_ids | resp_ids

    # -- base rows: every household from any source, even with no in-window gifts ---
    # (gifts_by_fy only holds households with in-window gifts; a listed household with
    # none of them — e.g. a lapsed donor whose only gift predates FY22 — must survive)
    table = pd.DataFrame({"id": sorted(ids)}).merge(gifts_fy, on="id", how="left")
    for col in DON_FY_COLUMNS:
        table[col] = table[col].fillna(0.0)
    table["don_5yr_total"] = table[DON_FY_COLUMNS].sum(axis=1)

    # -- Fort Salem split (robust to a nullable/float in_neon flag) -------------------
    in_neon_flag = fst_summary["in_neon"].fillna(False).astype(bool)
    fst_neon = fst_summary[in_neon_flag]
    fst_new = fst_summary[~in_neon_flag].copy()
    fst_new = fst_new.rename(
        columns={
            "name": "fst_name",
            "n_years": "fst_years",
            "years": "fst_years_list",
            "best_tier": "fst_best_tier",
        }
    )
    fst_new["is_fst_new"] = True
    for col in [*DON_FY_COLUMNS, "don_5yr_total"]:
        fst_new[col] = 0.0
    fst_new = fst_new.reset_index(drop=True)

    # -- merges attach Neon-side facts to the id rows only; FST-new rows stay out of
    # every merge so an NA id can never key-join against anything -------------------
    table = table.merge(lifetime, on="id", how="left")
    table = table.merge(engage, on="id", how="left")
    table = table.merge(contact, on="id", how="left")
    table = table.merge(neon_ids, on="id", how="left")
    table = table.merge(
        households.rename(columns={"name": "household_name"}), on="id", how="left"
    )

    # in-Neon Fort Salem matches: fill the fst_* detail columns from the matched row
    # (dedupe: two FST name variants can match the same household)
    table = table.merge(
        fst_neon[["id", "n_years", "years", "best_tier"]]
        .drop_duplicates(subset=["id"])
        .rename(
            columns={"n_years": "fst_years", "years": "fst_years_list", "best_tier": "fst_best_tier"}
        ),
        on="id", how="left",
    )
    table["fst"] = table["id"].isin(set(fst_neon["id"].dropna()))

    table = pd.concat(
        [table, fst_new[["fst_name", "is_fst_new", *DON_FY_COLUMNS, "don_5yr_total",
                         "fst_years", "fst_years_list", "fst_best_tier"]]],
        ignore_index=True,
    )
    table["household_name"] = table["household_name"].fillna(table.pop("fst_name"))

    # -- flags and indicators --------------------------------------------------------
    table["in_neon"] = table["id"].notna()
    table["src_donor_5yr"] = table["id"].isin(donor5_ids)
    table["src_donor3"] = table["id"].isin(d3_ids)
    table["src_new_accounts"] = table["id"].isin(na_ids)
    table["src_silent_selected"] = table["id"].isin(silent_ids)
    table["src_appeal_responded"] = table["id"].isin(resp_ids)
    table["fst"] = table["fst"].fillna(False) | table.pop("is_fst_new").fillna(False)
    table["needs_review"] = ~table["in_neon"]

    table["never_donated"] = table["don_lifetime"].fillna(0) == 0
    table["gave_fy26"] = table["don_fy2026"].fillna(0) > 0
    table["gave_fy25"] = table["don_fy2025"].fillna(0) > 0
    table["no_gift_last_5yrs"] = (table["don_lifetime"].fillna(0) > 0) & (
        table["don_5yr_total"].fillna(0) == 0
    )

    for col in ("arts_spend_3fy", "classes_spend_3fy", "community_spend_3fy", "regs_3fy"):
        table[col] = table[col].fillna(0.0)
    table["predominant_engagement"] = table.apply(predominant_engagement, axis=1)

    # -- steward + hand notes ---------------------------------------------------------
    # right-side NA-id rows (unmatched workbook names) must not key-join: pandas merges
    # NA==NA, which multiplies the table's own NA-id (Fort Salem new) rows. Duplicate
    # ids (two name variants matching one household) would multiply too — drop both.
    def _id_fields(frame: pd.DataFrame, cols: list[str], rename: dict) -> pd.DataFrame:
        return (
            frame.loc[frame["id"].notna(), ["id", *cols]]
            .drop_duplicates(subset=["id"])
            .rename(columns=rename)
        )

    table = table.merge(
        _id_fields(donor3, ["steward", "steward_raw", "note_hand"],
                   {"note_hand": "note_donor3", "steward_raw": "steward_detail"}),
        on="id", how="left",
    )
    table = table.merge(
        _id_fields(new_accounts, ["note_hand"], {"note_hand": "note_new"}),
        on="id", how="left",
    )
    table = table.merge(
        _id_fields(silent_selected, ["note_hand"], {"note_hand": "note_silent"}),
        on="id", how="left",
    )

    # -- new-household codes ----------------------------------------------------------
    is_new = ~table["in_neon"]
    table["new_code"] = pd.NA
    table.loc[is_new, "new_code"] = _new_codes(table.loc[is_new, "household_name"]).values

    table = table.sort_values("household_name").reset_index(drop=True)
    if table.duplicated(subset=["household_name", "id"]).any():
        # a merge exploded rows (an NA id keying against another frame) — fail loudly
        # rather than ship a silently duplicated mailing list. (Distinct ids that share
        # a name are legitimate — duplicate person records in Neon, e.g. Krauss — and
        # surface in the export QA instead.)
        dups = table.loc[table.duplicated(subset=["household_name", "id"]), "household_name"]
        raise ValueError(f"duplicated households in mailing list (merge explosion?): {list(dups.head())}")
    return table[OUTPUT_COLUMNS]
