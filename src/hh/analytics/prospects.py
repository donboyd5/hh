"""Campaign prospects: last year's donors in a date window who have not yet given this season.

Answers "who gave around this time last year and might still give before the year ends?"
by taking every gift in a past window (e.g. Nov 17, 2025 - Jan 31, 2026), rolling it up to
households, and labelling each household with its current-season status from Judy's tracker
(:mod:`hh.external.campaign_tracker`):

- ``yes`` - Judy's sheet shows a gift this season (dropped from the prospect list);
- ``not yet`` - on her sheet with no gift so far (kept);
- ``not on Judy's list`` - not a row in her sheet, so status is unknown (kept, flagged);
- ``board - lumped`` - a board member; Judy records board gifts only as one lumped
  "Board Donations" row, so no individual status exists (dropped - Don, 2026-11-17).

Gift basis is the clean-gift filter (SUCCEEDED ``DONATION``/``PLEDGEPAYMENT``) but, unlike the
individual-only donor analytics, **includes Company accounts** - a business gift is a real
prospect - and excludes only the internal house accounts.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from .. import config
from ..external.mailing import norm_name
from .board import BOARD_MEMBERS
from .donors import INTERNAL_ACCOUNT_IDS

PLEDGE_PAYMENT = "PLEDGE" + "PAYMENT"  # by concatenation - see the pledge-payment lesson

YES, NOT_YET, NOT_LISTED, BOARD = "yes", "not yet", "not on Judy's list", "board - lumped"
DROP_REASONS = {
    YES: "already gave this season (Judy's sheet)",
    BOARD: "board member",
}

# Hand facts that name donors live in a gitignored yaml (this repo is public):
# data/30_external/prospect-crosswalk.yaml - see load_crosswalk.
CROSSWALK_FILE = "prospect-crosswalk.yaml"


def load_crosswalk(path=None) -> tuple[dict[str, str], dict[str, str]]:
    """``(company_to_hh, notes)`` from the local crosswalk yaml; empty if the file is absent.

    company_to_hh maps a Company gift account id to its contact person's household rollup id
    (Judy's tracker lists the person, not the company). notes maps a rollup id to a fact the
    Neon data does not carry (e.g. believed moved).
    """
    p = Path(path) if path else config.layer_dir("external") / CROSSWALK_FILE
    if not p.exists():
        return {}, {}
    raw = yaml.safe_load(p.read_text()) or {}
    companies = {str(k): str(v["household"])
                 for k, v in (raw.get("company_households") or {}).items()}
    notes = {str(k): v["note"] for k, v in (raw.get("notes") or {}).items()}
    return companies, notes


def window_gifts(donations: pd.DataFrame, start, end, *,
                 company_to_hh: dict[str, str] | None = None) -> pd.DataFrame:
    """Clean gifts (individual AND company) dated ``start`` through ``end``, inclusive.

    Expects cleaned donations carrying the rollup ``id`` and ``name`` (``clean_donations``
    with accounts). Adds ``rid`` (rollup id as str) and ``hh`` (company accounts mapped to
    their contact's household via ``company_to_hh``, from :func:`load_crosswalk`).
    """
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    g = donations[
        donations["donation_status"].astype(str).eq("SUCCEEDED")
        & donations["donation_type"].isin(["DONATION", PLEDGE_PAYMENT])
        & ~donations["account_id"].astype(str).isin(INTERNAL_ACCOUNT_IDS)
        & donations["donation_date"].between(start, end + pd.Timedelta(days=1), inclusive="left")
    ].copy()
    g["rid"] = g["id"].astype(str)
    company_to_hh = company_to_hh or {}
    g["hh"] = g["rid"].map(lambda r: company_to_hh.get(r, r))
    return g


def label_companies(gifts: pd.DataFrame, accounts: pd.DataFrame) -> pd.Series:
    """Display name: "Company (contact)" for company gifts, the rollup name otherwise."""
    company = (accounts.assign(account_id=accounts["account_id"].astype(str))
               .drop_duplicates("account_id").set_index("account_id")["company_name"])
    co_name = gifts["account_id"].astype(str).map(company)
    is_co = gifts["account_type"].astype(str).eq("Company") & co_name.notna()
    return gifts["name"].astype(str).where(~is_co, co_name + " (" + gifts["name"].astype(str) + ")")


def deceased_households(accounts: pd.DataFrame) -> set[str]:
    """Rollup ids where EVERY member account is flagged deceased.

    Any-member would be wrong: a household often carries one late spouse's flag while the
    surviving spouse still gives.
    """
    a = accounts.assign(
        rid=accounts["household_id"].fillna(accounts["account_id"]).astype(str),
        _d=accounts["deceased"].fillna(False).astype(bool),
    )
    flags = a.groupby("rid")["_d"].all()
    return set(flags[flags].index)


def season_status(rid: str, name: str, tracker: pd.DataFrame, *,
                  board_ids=frozenset(BOARD_MEMBERS),
                  company_to_hh: dict[str, str] | None = None) -> dict:
    """Current-season status of one household (or company gift account).

    Match order: company -> contact household; board -> lumped; ``neon_hh_id``; then exact
    normalized name among tracker rows that have no Neon id (Judy's "Added" block).
    """
    via = "household id"
    company_to_hh = company_to_hh or {}
    if rid in company_to_hh:
        rid, via = company_to_hh[rid], "company contact's household"
    out = {"status": None, "season_amount": None, "steward": None, "judy_comments": None,
           "matched_via": via}
    if rid in board_ids:
        return out | {"status": BOARD}
    hit = tracker[tracker["neon_hh_id"].eq(rid).fillna(False)]
    if hit.empty:
        key = norm_name(pd.Series([name])).iloc[0]
        hit = tracker[tracker["neon_hh_id"].isna() & tracker["name_key"].eq(key).fillna(False)]
        out["matched_via"] = "exact name"
    if hit.empty:
        return out | {"status": NOT_LISTED, "matched_via": None}
    row = hit.iloc[0]
    amt = row["season_amount"]
    gave = pd.notna(amt) and amt > 0
    return out | {"status": YES if gave else NOT_YET,
                  "season_amount": round(float(amt), 2) if gave else None,
                  "steward": row["steward"], "judy_comments": row["comments"]}


def add_status(gifts: pd.DataFrame, tracker: pd.DataFrame, *, deceased: set[str] = frozenset(),
               notes: dict[str, str] | None = None, **kwargs) -> pd.DataFrame:
    """Attach status, season_amount, steward, judy_comments, matched_via, neon_note.

    ``kwargs`` pass through to :func:`season_status` (``company_to_hh``, ``board_ids``).
    """
    notes = notes or {}
    names = gifts.groupby("rid")["name"].first()
    status = pd.DataFrame({r: season_status(r, n, tracker, **kwargs) for r, n in names.items()}).T
    out = gifts.join(status, on="rid")
    out["neon_note"] = out["rid"].map(
        lambda r: notes.get(r) or ("deceased per Neon" if r in deceased else None))
    return out


def month_periods(start, end) -> list[tuple[str, pd.Timestamp, pd.Timestamp]]:
    """Calendar-month slices of [start, end] as (label, first day, last day).

    Partial months say so in the label ("Nov 17-30 2025"); whole months read "Dec 2025".
    """
    start, end = pd.Timestamp(start).normalize(), pd.Timestamp(end).normalize()
    out = []
    m = start.to_period("M")
    while m.start_time <= end:
        lo, hi = max(start, m.start_time), min(end, m.end_time.normalize())
        whole = lo == m.start_time and hi == m.end_time.normalize()
        label = (lo.strftime("%b %Y") if whole
                 else f"{lo.strftime('%b')} {lo.day}-{hi.day} {lo.year}")
        out.append((label, lo, hi))
        m += 1
    return out


def _join_unique(s: pd.Series) -> str:
    return "; ".join(sorted({str(x) for x in s.dropna()}))


def _roll(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """One row per ``key`` (``rid`` = gift account rollup, ``hh`` = folded household)."""
    df = df.sort_values("donation_amount", ascending=False)
    t = (df.groupby(key).agg(
            donor=("donor", lambda s: " + ".join(dict.fromkeys(s.astype(str)))),
            amount=("donation_amount", "sum"),
            status=("status", "first"), steward=("steward", "first"),
            neon_note=("neon_note", "first"), gifts=("donation_amount", "size"),
            gift_dates=("donation_date",
                        lambda s: "; ".join(x.strftime("%m/%d/%y") for x in sorted(set(s)))),
            campaigns=("campaign", _join_unique), account_type=("account_type", _join_unique),
            account_ids=("account_id", _join_unique))
         .reset_index().rename(columns={key: "neon_hh_id"}))
    t["amount"] = t["amount"].round(2)
    t = t[["donor", "amount", "status", "steward", "neon_note", "gifts", "gift_dates",
           "campaigns", "account_type", "neon_hh_id", "account_ids"]]
    return t.sort_values(["amount", "donor"], ascending=[False, True], ignore_index=True)


def prospect_tables(gifts: pd.DataFrame, start, end) -> dict[str, pd.DataFrame]:
    """Workbook tabs for status-labelled window gifts (output of :func:`add_status`).

    Needs a ``donor`` display column. Returns, in order: ``combined`` (one row per household,
    one amount column per month), one tab per month (gift accounts kept separate), and
    ``excluded`` (dropped households with the reason). Every tab sorts large to small.
    """
    periods = month_periods(start, end)
    keep = gifts[~gifts["status"].isin(DROP_REASONS)]
    drop = gifts[gifts["status"].isin(DROP_REASONS)]

    def period_of(d):
        return next(lbl for lbl, lo, hi in periods if lo <= d.normalize() <= hi)

    labels = [p[0] for p in periods]
    keep = keep.assign(period=keep["donation_date"].map(period_of))
    combined = _roll(keep, "hh").rename(columns={"amount": "total"})
    by_month = (keep.pivot_table(index="hh", columns="period", values="donation_amount",
                                 aggfunc="sum", fill_value=0)
                .reindex(columns=labels, fill_value=0).round(2))
    combined = combined.join(by_month, on="neon_hh_id")
    combined.insert(0, "rank", range(1, len(combined) + 1))
    lead = ["rank", "donor", "total", *labels]
    tabs = {"combined": combined[lead + [c for c in combined.columns if c not in lead]]}

    for label in labels:
        t = _roll(keep[keep["period"].eq(label)], "rid")
        t.insert(0, "rank", range(1, len(t) + 1))
        tabs[label] = t
    excluded = _roll(drop, "hh").rename(columns={"amount": "total"})
    excluded.insert(2, "reason", excluded["status"].map(DROP_REASONS))
    tabs["excluded"] = excluded.drop(columns="status")
    return tabs


def summary_table(gifts: pd.DataFrame, tabs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Households and dollars by group, with a check row that ties back to the raw gifts."""
    comb, ex = tabs["combined"], tabs["excluded"]
    rows = [("kept (combined tab)", len(comb), comb["total"].sum())]
    for s in (NOT_YET, NOT_LISTED):
        m = comb["status"].eq(s)
        rows.append((f"  kept: {s}", int(m.sum()), comb.loc[m, "total"].sum()))
    for reason in DROP_REASONS.values():
        m = ex["reason"].eq(reason)
        rows.append((f"dropped: {reason}", int(m.sum()), ex.loc[m, "total"].sum()))
    rows.append(("all households in window", len(comb) + len(ex),
                 comb["total"].sum() + ex["total"].sum()))
    rows.append(("check: sum of every gift in window", None, gifts["donation_amount"].sum()))
    out = pd.DataFrame(rows, columns=["group", "households", "amount"])
    out["amount"] = out["amount"].round(2)
    return out
