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

import re

import numpy as np
import pandas as pd

from ..analytics.donors import succeeded_individual_gifts

FY_MONTH = 7  # fiscal year starts July 1

GIVING_FYS = (2022, 2023, 2024, 2025, 2026)
ENGAGEMENT_FYS = (2024, 2025, 2026)
DE_MINIMIS_5YR = 10.0
# rows under this 5-year total are dropped unless keep-identified (Don, 2026-08-27)
MIN_DONOR_5YR = 200.0

# last year's annual-campaign period: a household that RECEIVED the appeal (appealed=TRUE
# in the appeal workbook) and gave at least this much to the campaign in the window is
# kept regardless of the floor (Don, 2026-08-28). Only gifts coded to the Annual Fund
# Drive campaign count (Don, 2026-08-28 — matches Judy's campaign total; the ~$2k of
# window gifts coded Misc/Sustaining show up as "rest of FY26" instead).
APPEAL_WINDOW = (pd.Timestamp("2025-10-01"), pd.Timestamp("2026-01-31"))
APPEAL_CAMPAIGN = "Annual Fund Drive - 2025-2026"
MIN_APPEAL_GIFT = 10.0

# engaged non-donors: households with no successful gift in the 5-year window but at
# least this much FY22-26 registration spending (arts + classes + community) enter the
# list and are exempt from the giving floor (Don, 2026-08-28; window widened from 3 to 5
# years 2026-08-28 so giving and spending are judged over the same period). In practice
# this is the parents-of-class-kids pool — families spending $500-$4,000 on classes.
MIN_ENGAGED_NONDONOR_SPEND = 500.0
ENGAGED_NONDONOR_FYS = GIVING_FYS

# Fort Salem sponsors NOT in Neon are kept only if serious (rule B, Don 2026-08-28):
# a $100+ tier (Inner Circle or higher) in any year 2021-2025, or sponsorship in two or
# more years at any level. 2020-only "Opening Angels" (a one-time reopening gesture,
# amount unpublished) are dropped unless they reappeared later. Dropped names are
# reported, not deleted, so one can be pulled back by hand.
FST_TIER_RANK = {
    "founding": 7, "opening angels": 6, "platinum": 6, "gold": 5, "silver": 4,
    "bronze": 3, "inner circle": 2, "friends of fort salem": 1,
}
FST_KEEP_MIN_RANK = 2  # inner circle ($100-499) and up
FST_KEEP_MIN_YEARS = 2

# a note that says someone died — unless it also says someone survives (e.g. Don's
# "Tim has died; wife/gf still around; Sue will contact" keeps the household: mail
# goes to the survivor). Only explicit survivor phrases guard: "husband died 2024"
# names the deceased, not a survivor. Every note-based drop is listed in the export
# QA for eyeballing, so an ambiguous note surfaces rather than silently dropping.
_DEATH_NOTE = re.compile(r"\b(?:died|deceased|passed away|passing)\b", re.I)
_SURVIVOR_NOTE = re.compile(r"\b(?:still around|surviving|survivor)\b", re.I)

# registration category -> engagement group for the mailing list
CATEGORY_GROUPS = {
    "performance": "arts",
    "other": "arts",  # galas, fundraisers, films — events in Don's "arts" sense
    "class": "classes",
    "community": "community",
}

DON_FY_COLUMNS = [f"don_fy{fy}" for fy in GIVING_FYS]

# column order in the exported table (Don, 2026-08-27): the three id codes, the
# household name, donation history, contact info, then everything else
OUTPUT_COLUMNS = [
    # the three codes, then the household name and which letter it gets
    "neon_hh_id", "neon_account_ids", "new_code", "household_name", "letter", "neon_household_name",
    # donation history
    *DON_FY_COLUMNS, "don_5yr_total", "don_lifetime", "don_appeal_window",
    # contact info
    "contact_first_name", "contact_last_name", "salutation", "address", "city",
    "state_province", "zip_code", "phone", "email",
    # everything else: identity/source flags, indicators, engagement, stewardship,
    # notes, Fort Salem detail
    "in_neon", "src_donor_5yr", "src_donor3", "src_new_accounts",
    "src_appeal_responded", "src_appeal_gift", "appealed_last_year", "src_silent_selected",
    "src_engaged_nondonor", "fst", "needs_review",
    "never_donated", "gave_fy26", "gave_fy25", "no_gift_last_5yrs",
    "arts_spend_3fy", "classes_spend_3fy", "community_spend_3fy", "regs_3fy",
    "arts_spend_5fy", "classes_spend_5fy", "community_spend_5fy", "regs_5fy",
    "predominant_engagement", "do_not_contact", "deceased", "deceased_members", "distance_miles",
    "steward", "steward_detail", "note_donor3", "note_new", "note_silent",
    "note_boyd", "note_neon", "fst_years", "fst_years_list", "fst_best_tier",
    "fst_candidate_id", "fst_candidate_name",
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


def appeal_window_gifts(
    donations: pd.DataFrame,
    *,
    window: tuple[pd.Timestamp, pd.Timestamp] = APPEAL_WINDOW,
    campaign: str | None = APPEAL_CAMPAIGN,
) -> pd.DataFrame:
    """Household succeeded-gift totals to the campaign inside its window -> [id, don_appeal_window].

    ``campaign=None`` counts every gift in the window regardless of campaign code.
    """
    g = succeeded_individual_gifts(donations)
    g = g[g["donation_date"].between(window[0], window[1])]
    if campaign is not None and "campaign" in g.columns:
        g = g[g["campaign"].eq(campaign)]
    return (
        g.groupby("id")["donation_amount"].sum().rename("don_appeal_window").reset_index()
    )


def engagement_spend(
    registrations: pd.DataFrame, fys: tuple[int, ...], *, suffix: str = "3fy"
) -> pd.DataFrame:
    """Household registration dollars by engagement group (arts/classes/community) + counts.

    ``suffix`` names the window in the output columns (``arts_spend_3fy`` …).
    """
    r = registrations.copy()
    r["fy"] = fiscal_year(r["starts_on"])
    r = r[r["fy"].isin(fys) & r["event_majorcat"].isin(CATEGORY_GROUPS)]
    r["group"] = r["event_majorcat"].map(CATEGORY_GROUPS)
    # key on the rollup ``id`` (household id, else account id): ``household_id`` is
    # blank for single-account households — 6,259 of 28k registrations — and keying on
    # it silently zeroed their engagement (found 2026-08-28)
    spend = r.pivot_table(
        index="id", columns="group", values="amount", aggfunc="sum", fill_value=0.0
    )
    spend = spend.reindex(columns=["arts", "classes", "community"], fill_value=0.0)
    spend.columns = [f"{c}_spend_{suffix}" for c in spend.columns]
    counts = r.groupby("id").size().rename(f"regs_{suffix}")
    return spend.join(counts).reset_index()


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


def _any_living_flag(flags: pd.Series, members: pd.DataFrame) -> bool:
    """True if any LIVING member of the group carries the flag."""
    return bool((flags.fillna(False).astype(bool) & ~members.loc[flags.index, "_dead"]).any())


def _deceased_names(names: pd.Series, members: pd.DataFrame) -> str | None:
    """"; "-joined names of the group's deceased members, or None."""
    dead = members.loc[names.index, "_dead"]
    joined = "; ".join(str(n) for n, d in zip(names, dead, strict=True) if d)
    return joined or None


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
    a["_dead"] = a["deceased"].fillna(False).astype(bool)
    # living members first: a widow/widower is the contact, never the late spouse
    a = a.sort_values(["id", "_dead", "n_gifts", "created"], ascending=[True, True, False, True])
    a = a.rename(columns=_CONTACT_FIELDS)

    fields = list(_CONTACT_FIELDS.values())
    present = [f for f in fields if f in a.columns]
    contact = a.groupby("id", sort=True)[present].first().reset_index()
    for missing in set(fields) - set(present):
        contact[missing] = pd.NA  # e.g. pre-enrichment frames without the 2026-08 fields

    # household flags (2026-08-28, after six widows who gave to the campaign were dropped):
    #   deceased       = EVERY member deceased (a surviving spouse keeps the household)
    #   do_not_contact = any LIVING member flagged (Neon sets the flag on deceased members,
    #                    which is why 422 households incl. top donors carry it)
    #   deceased_members = names of the deceased, so a letter can avoid the late spouse
    flags = a.groupby("id", sort=True).agg(
        deceased=("_dead", "all"),
        do_not_contact=("do_not_contact", lambda s: _any_living_flag(s, a)),
        deceased_members=("full_name", lambda s: _deceased_names(s, a)),
    ).reset_index()
    contact = contact.merge(flags, on="id")

    line1 = contact.pop("address").astype("string").str.strip()
    line2 = contact.pop("address2").astype("string").str.strip()
    both_blank = line1.isna() & line2.isna()
    joined = (line1.fillna("") + " " + line2.fillna("")).str.strip()
    contact["address"] = joined.mask(both_blank, pd.NA)

    # salutation: the household-level field wins, the account-level one fills gaps
    hh_sal = contact.pop("salutation_hh").astype("string")
    ind_sal = contact.pop("salutation_ind").astype("string")
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


def _combined_notes(table: pd.DataFrame) -> pd.Series:
    """Don's hand notes joined into one string per row (for death-note scanning).

    Deliberately excludes ``note_neon`` (Neon staff narratives): those mention deaths
    of non-account people ("my uncle… passed away") and contradict themselves
    ("passed away according to Benjie… now 93 and still lives in NYC"), and Don's
    instruction was to honor notes *from him*, not staff notes.
    """
    cols = [
        c for c in ("note_donor3", "note_new", "note_silent", "note_boyd")
        if c in table.columns
    ]
    if not cols:
        return pd.Series("", index=table.index, dtype="string")
    joined = table[cols].astype("string").apply(
        lambda row: " | ".join(part for part in row if pd.notna(part)), axis=1
    )
    return joined.fillna("")


def apply_exclusions(
    table: pd.DataFrame,
    *,
    min_donor_5yr: float = MIN_DONOR_5YR,
    drop_do_not_contact: bool = False,
) -> tuple[pd.DataFrame, dict]:
    """Drop households Don excluded (2026-08-27), returning the table and a QA report.

    - **Deceased**: the Neon deceased flag, or any hand/Neon note saying someone died —
      unless the note also names a survivor ("Tim has died; wife/gf still around"),
      since the mail then goes to the surviving partner.
    - **Do-not-contact**: flagged, NOT dropped by default. Neon's flag sits on 422
      households with $674k of lifetime giving — Dorothy Ashton, the Neubohns, Estey, Katz,
      Merrill, Slack, Kruger — so it cannot mean "never contact" (2026-08-28; likely an
      email opt-out or import artifact — Judy to confirm). ``drop_do_not_contact=True``
      drops them once the flag's meaning is settled; the QA lists them either way.
    - **Small givers**: rows with under ``min_donor_5yr`` ($200) in 5 years drop unless
      keep-identified — a new person (Judy's new-accounts list, or Fort Salem), one of
      Don's hand notes or a steward assignment, the bolded silent keep-list, an appeal
      responder, a household that gave >= $10 in last year's campaign window, or an
      engaged non-donor (>= $500 FY22-26 spending, no 5-year gift) (Don, 2026-08-27/28).
      Neon staff notes do not identify a keeper, consistent
      with the deceased scan.

    QA names every dropped household and why, so nothing disappears silently.
    """
    notes = _combined_notes(table)
    died = notes.str.contains(_DEATH_NOTE).fillna(False)
    survivor = notes.str.contains(_SURVIVOR_NOTE).fillna(False)
    neon_deceased = table["deceased"].fillna(False).astype(bool)
    by_note = died & ~survivor
    deceased = neon_deceased | by_note

    keep_identified = (
        table["src_new_accounts"].fillna(False)
        | table["fst"].fillna(False)
        | table["src_silent_selected"].fillna(False)
        | table["src_appeal_responded"].fillna(False)
        | table["src_appeal_gift"].fillna(False)
        | table["src_engaged_nondonor"].fillna(False)
        | (notes.str.len() > 0)
        | table["steward"].notna()
    )
    small = (table["don_5yr_total"].fillna(0) < min_donor_5yr) & ~keep_identified
    dnc = table["do_not_contact"].fillna(False).astype(bool)
    if not drop_do_not_contact:
        dnc = pd.Series(False, index=table.index)

    qa = {
        "do_not_contact": table.loc[
            table["do_not_contact"].fillna(False).astype(bool) & ~deceased & ~small,
            "household_name",
        ].tolist(),
        "dropped_do_not_contact": table.loc[dnc & ~deceased, "household_name"].tolist(),
        "dropped_deceased_neon": table.loc[
            neon_deceased & ~by_note, "household_name"
        ].tolist(),
        "dropped_deceased_note": table.loc[by_note, "household_name"].tolist(),
        "kept_deceased_note_survivor": table.loc[
            died & survivor, "household_name"
        ].tolist(),
        "dropped_small_donor": table.loc[small, "household_name"].tolist(),
    }
    return table[~deceased & ~small & ~dnc].reset_index(drop=True), qa


def fst_candidates(fst_summary: pd.DataFrame, accounts: pd.DataFrame) -> pd.DataFrame:
    """The single strong Neon candidate per non-exact Fort Salem name, for the main sheet.

    Thin wrapper over :mod:`hh.analytics.fst_match`: a name gets ``fst_candidate_*`` only
    when exactly one household scores at/above ``AUTO_FILL_SCORE``; the full ranked
    candidate list (including weaker ones) goes to the workbook's review sheet. Never a
    merge — Don confirms each.
    """
    from .fst_match import auto_candidates, fuzzy_fst_candidates

    return auto_candidates(fuzzy_fst_candidates(fst_summary, accounts))


def fst_keep_mask(fst_summary: pd.DataFrame) -> pd.Series:
    """Rule B: which Fort Salem sponsors are serious enough to keep (see constants)."""
    tier = fst_summary["best_tier"].astype(str).str.strip().str.lower()
    rank = tier.map(FST_TIER_RANK).fillna(0)
    years = fst_summary["years"].astype(str).str.split(",")
    last_year = years.map(lambda ys: max((int(y) for y in ys if y.strip().isdigit()), default=0))
    n_years = pd.to_numeric(fst_summary["n_years"], errors="coerce").fillna(0)
    angels_2020_only = tier.eq("opening angels") & last_year.eq(2020)
    return ((rank >= FST_KEEP_MIN_RANK) & ~angels_2020_only) | (n_years >= FST_KEEP_MIN_YEARS)


# which letter template a household gets (Don, 2026-08-28). One mail merge branches on
# this instead of hand-sorting the sheet; it stays right when the list is regenerated.
LETTER_DONOR = "donor"  # has given in the last five years, or a hand-kept lapsed donor
LETTER_CLASS_FAMILY = "class-family"  # engaged non-donor: paid for classes/tickets, never asked
LETTER_NEW_ATTENDER = "new-attender"  # new Neon account, no gift yet
LETTER_FST = "fst-personal"  # Fort Salem sponsor not in Neon: Don's personal letter, not the appeal


def assign_letter(table: pd.DataFrame) -> pd.Series:
    """Letter template per row, in the same priority order as the summary categories."""
    return pd.Series(
        np.select(
            [
                ~table["in_neon"].fillna(False).astype(bool),
                table["don_5yr_total"].fillna(0) > 0,
                table["src_engaged_nondonor"].fillna(False).astype(bool),
                table["src_new_accounts"].fillna(False).astype(bool),
            ],
            [LETTER_FST, LETTER_DONOR, LETTER_CLASS_FAMILY, LETTER_NEW_ATTENDER],
            default=LETTER_DONOR,  # the hand-kept lapsed donors
        ),
        index=table.index,
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
    boyd_notes: dict[str, str] | None = None,
    appealed_ids: set[str] | None = None,
) -> pd.DataFrame:
    """Assemble the mailing list.

    External frames are keyed by matched rollup ``id`` (from
    :func:`hh.external.mailing.match_households`); ``fst_summary`` additionally carries
    ``in_neon`` (bool). ``boyd_notes`` is Don's ``{rollup id: note}`` file
    (:func:`hh.external.notes.load_boyd_notes`). ``appealed_ids`` are the rollup ids that
    received last year's appeal (``appeal_households.appealed``); the campaign-window keep
    rule applies only to them (None = no restriction, for tests). Returns one row per household in
    :data:`OUTPUT_COLUMNS` order; the exclusion QA (who was dropped and why) rides
    along on ``table.attrs["exclusion_qa"]``.
    """
    households = accounts[["id", "name"]].drop_duplicates(subset=["id"])

    gifts_fy = gifts_by_fy(donations, GIVING_FYS)
    lifetime = (
        succeeded_individual_gifts(donations)
        .groupby("id")["donation_amount"].sum().rename("don_lifetime").reset_index()
    )
    engage = engagement_spend(registrations, ENGAGEMENT_FYS)
    engage5 = engagement_spend(registrations, ENGAGED_NONDONOR_FYS, suffix="5fy")
    appeal_win = appeal_window_gifts(donations)
    contact = pick_contact(accounts, donations)
    neon_ids = neon_ids_by_household(accounts)

    # -- id sets per source --------------------------------------------------------
    donor5_ids = set(gifts_fy.loc[gifts_fy[DON_FY_COLUMNS].sum(axis=1) >= DE_MINIMIS_5YR, "id"])
    d3_ids = set(donor3["id"].dropna())
    na_ids = set(new_accounts["id"].dropna())
    silent_ids = set(silent_selected["id"].dropna())
    resp_ids = set(appeal_responded["id"].dropna())
    appeal_gift_ids = set(
        appeal_win.loc[appeal_win["don_appeal_window"] >= MIN_APPEAL_GIFT, "id"]
    )
    if appealed_ids is not None:
        appeal_gift_ids &= set(appealed_ids)
    spend_5fy = engage5.set_index("id")[
        ["arts_spend_5fy", "classes_spend_5fy", "community_spend_5fy"]
    ].sum(axis=1)
    gave_5yr = set(gifts_fy.loc[gifts_fy[DON_FY_COLUMNS].sum(axis=1) > 0, "id"])
    engaged_ids = set(spend_5fy[spend_5fy >= MIN_ENGAGED_NONDONOR_SPEND].index) - gave_5yr
    ids = donor5_ids | d3_ids | na_ids | silent_ids | resp_ids | appeal_gift_ids | engaged_ids

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
    fst_not_neon = fst_summary[~in_neon_flag]
    keep = fst_keep_mask(fst_not_neon)
    fst_dropped = fst_not_neon.loc[~keep, ["name", "best_tier", "n_years", "years"]]
    fst_dropped = fst_dropped.reset_index(drop=True)
    fst_new = fst_not_neon[keep].copy()
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
    table = table.merge(appeal_win, on="id", how="left")
    table = table.merge(engage, on="id", how="left")
    table = table.merge(engage5, on="id", how="left")
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
            columns={
                "n_years": "fst_years", "years": "fst_years_list", "best_tier": "fst_best_tier",
            }
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

    # Fort Salem candidate households for the non-exact names (review, never auto-merge)
    candidates = fst_candidates(fst_summary, accounts)
    if candidates.empty:
        table["fst_candidate_id"] = pd.NA
        table["fst_candidate_name"] = pd.NA
    else:
        table = table.merge(
            candidates.rename(columns={"name": "household_name"}),
            on="household_name", how="left",
        )

    # -- flags and indicators --------------------------------------------------------
    table["in_neon"] = table["id"].notna()
    table["src_donor_5yr"] = table["id"].isin(donor5_ids)
    table["src_donor3"] = table["id"].isin(d3_ids)
    table["src_new_accounts"] = table["id"].isin(na_ids)
    table["src_silent_selected"] = table["id"].isin(silent_ids)
    table["src_appeal_responded"] = table["id"].isin(resp_ids)
    table["src_appeal_gift"] = table["id"].isin(appeal_gift_ids)
    table["src_engaged_nondonor"] = table["id"].isin(engaged_ids)
    table["appealed_last_year"] = (
        table["id"].isin(appealed_ids) if appealed_ids is not None else pd.NA
    )
    table["don_appeal_window"] = table["don_appeal_window"].fillna(0.0)
    table["fst"] = table["fst"].fillna(False) | table.pop("is_fst_new").fillna(False)
    table["needs_review"] = ~table["in_neon"]

    table["never_donated"] = table["don_lifetime"].fillna(0) == 0
    table["gave_fy26"] = table["don_fy2026"].fillna(0) > 0
    table["gave_fy25"] = table["don_fy2025"].fillna(0) > 0
    table["no_gift_last_5yrs"] = (table["don_lifetime"].fillna(0) > 0) & (
        table["don_5yr_total"].fillna(0) == 0
    )

    for col in ("arts_spend_3fy", "classes_spend_3fy", "community_spend_3fy", "regs_3fy",
                "arts_spend_5fy", "classes_spend_5fy", "community_spend_5fy", "regs_5fy"):
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

    # -- Don's hand notes (boyd-notes.yaml), as a column and as a death-note source --
    if boyd_notes:
        table["note_boyd"] = table["id"].map(boyd_notes).astype("string")
    elif "note_boyd" not in table.columns:
        table["note_boyd"] = pd.NA

    # -- exclusions (deceased; small donor-rule rows) -------------------------------
    table, exclusion_qa = apply_exclusions(table)

    # a household with a deceased member is addressed to the living contact, not the
    # Neon label that still names both ("Linda & Richard Slack" -> "Linda Slack");
    # the Neon label is kept alongside
    table["neon_household_name"] = table["household_name"]
    survivor = table["deceased_members"].notna() & ~table["deceased"].fillna(False).astype(bool)
    living_name = (
        table["contact_first_name"].fillna("").astype(str)
        + " "
        + table["contact_last_name"].fillna("").astype(str)
    ).str.strip()
    relabel = survivor & living_name.ne("")
    table.loc[relabel, "household_name"] = living_name[relabel]

    table["letter"] = assign_letter(table)

    # sort (Don, 2026-08-28): 2025-campaign gift, then 5-year giving, then class spending,
    # all descending; name breaks ties. Campaign gift counts only for appealed responders.
    table["_campaign"] = table["don_appeal_window"].where(table["src_appeal_gift"], 0.0)
    table = table.sort_values(
        ["_campaign", "don_5yr_total", "classes_spend_5fy", "household_name"],
        ascending=[False, False, False, True],
    ).drop(columns="_campaign").reset_index(drop=True)
    if table.duplicated(subset=["household_name", "id"]).any():
        # a merge exploded rows (an NA id keying against another frame) — fail loudly
        # rather than ship a silently duplicated mailing list. (Distinct ids that share
        # a name are legitimate — duplicate person records in Neon, e.g. Krauss — and
        # surface in the export QA instead.)
        dups = table.loc[table.duplicated(subset=["household_name", "id"]), "household_name"]
        raise ValueError(
            f"duplicated households in mailing list (merge explosion?): {list(dups.head())}"
        )

    # output-facing names: the join key becomes the household id code, and the member
    # account ids read as what they are (internal callers still use id / neon_ids)
    out = table.rename(columns={"id": "neon_hh_id", "neon_ids": "neon_account_ids"})
    out.attrs["exclusion_qa"] = exclusion_qa
    out.attrs["fst_dropped"] = fst_dropped.to_dict(orient="records")  # JSON-safe for parquet
    return out[OUTPUT_COLUMNS]
