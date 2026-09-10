"""The consolidated address book: one row per mailable identity across every source.

Single place where address knowledge lives (Don, 2026-09-10): everyone in Neon plus the
add-on lists (Fort Salem sponsors, Music from Salem donors, Friends to add, MfS concert
attendees), every candidate address with its source, and one *best* address chosen by a
documented precedence. Filtering to an actual mailing happens downstream — this table is
the knowledge base, so rows are flagged, never silently dropped (web-confirmed deaths
stay, flagged; the mailing-list export drops them instead).

Identity anchor: the Neon household rollup id when the person is in Neon, otherwise the
listed name. Standalone rows from different lists merge only on an *exact* canonical-key
match (surname + nickname-folded given names, :func:`fortsalem._canonical_key`) —
conservative by design, since a subset match across lists would fuse relatives. Fuzzy
Neon candidates are shown (``possible_neon_match``), never auto-folded.

Sources and precedence are catalogued in ``meta-docs/address-sources.md``.
"""
from __future__ import annotations

import re

import pandas as pd

from ..analytics.fst_match import fuzzy_fst_candidates
from ..analytics.mailing import fst_keep_mask, pick_contact
from ..geo.geocode import is_po_box
from .fortsalem import TIER_RANK, _canonical_key, fst_vs_neon
from .mailing import match_households

# Best-address precedence (Don, 2026-09-10): lower rank wins among the addresses that
# exist for an identity. Neon is the CRM of record; the ranks order the *fallbacks*,
# and every candidate stays visible on the candidates table regardless of which wins.
ADDRESS_SOURCE_RANK = {
    "neon": 0,
    "roll-strong": 1,
    "mfs-list": 2,
    "roll-probable": 3,
    "web-business": 4,
}

# display order of the book: identity, presence, address, exclusions, research help
BOOK_COLUMNS = [
    "neon_hh_id", "name", "also_listed_as",
    "in_neon",
    "fst", "fst_best_tier", "fst_years", "fst_rule_b",
    "mfs_donor", "friends_to_add", "mfs_attendee",
    "mailed_2025", "in_mailing_list", "letter",
    "address", "city", "state_province", "zip_code", "address_source",
    "address_conflict", "po_box",
    "deceased", "deceased_members", "do_not_contact",
    "web_note", "possible_neon_match", "note_boyd", "neon_company_only",
]

CANDIDATE_COLUMNS = [
    "identity", "name", "source", "rank", "street", "city", "state_province",
    "zip_code", "detail",
]

# streets compared for conflicts after casefold + punctuation/whitespace squeeze
_STREET_NORM = re.compile(r"[^a-z0-9]+")

_BOOL_FLAGS = ("fst", "mfs_donor", "friends_to_add", "mfs_attendee", "deceased")


def _norm_street(street: pd.Series) -> pd.Series:
    return (
        street.astype("string").str.lower()
        .str.replace(_STREET_NORM, " ", regex=True).str.strip()
    )


def _union_years(values) -> str:
    """Sorted union of comma-separated year lists ("2021,2024" + "2024,2025")."""
    return ",".join(sorted({y for v in values for y in str(v).split(",") if y and y != "<NA>"}))


def build_address_book(
    accounts: pd.DataFrame,
    donations: pd.DataFrame,
    *,
    received: dict[str, pd.DataFrame],
    roll_hits: pd.DataFrame,
    contact_notes: pd.DataFrame,
    appeal_ids: pd.DataFrame,
    mailing_list: pd.DataFrame,
    fst_summary: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Assemble the book and its per-address candidates table.

    ``received`` maps a list key to its parsed frame (``hh.external.lists`` loaders):
    ``mfs_donor`` carries ``street/city/state_province/zip_code``, the others only
    ``name``. ``roll_hits`` is the assessment-roll research output
    (``data/10_interim/fst_contacts.parquet``), ``contact_notes`` the web-research
    notes (``load_fst_contact_notes``), ``appeal_ids`` the Fall 2025 appeal's Neon ids
    (``load_appeal2025_ids``), and ``mailing_list`` the built mailing list (letter and
    Don's-notes context). ``fst_summary`` defaults to :func:`fortsalem.fst_vs_neon`.
    """
    if fst_summary is None:
        fst_summary = fst_vs_neon(accounts)

    individuals = accounts[accounts["account_type"].ne("Company")]
    # matching pool is ALL households (an add-on list can vouch for a person whose Neon
    # rollup happens to hold only Company-typed accounts); the row universe is not
    households = accounts.drop_duplicates(subset=["id"])[["id", "name", "city"]]
    list_matches = {
        key: (
            match_households(frame["name"], households,
                             cities=frame["city"] if "city" in frame.columns else None)
            if not frame.empty else None
        )
        for key, frame in received.items()
    }

    # -- Neon universe: individual households, plus company-only rollups an add-on list
    #    matched (list-vouched people — kept and flagged, not silently dropped) ---------
    contact = pick_contact(individuals, donations).rename(columns={"id": "neon_hh_id"})
    matched_any = set(fst_summary.loc[fst_summary["in_neon"], "id"].astype(str))
    for matched in list_matches.values():
        if matched is not None:
            matched_any |= set(matched["id"].dropna().astype(str))
    extra = pick_contact(accounts, donations).rename(columns={"id": "neon_hh_id"})
    extra = extra[
        extra["neon_hh_id"].astype(str).isin(matched_any)
        & ~extra["neon_hh_id"].astype(str).isin(set(contact["neon_hh_id"].astype(str)))
    ].assign(neon_company_only=True)
    contact = pd.concat([contact.assign(neon_company_only=False), extra], ignore_index=True)
    book = contact.merge(
        households[["id", "name"]].rename(columns={"id": "neon_hh_id"}),
        on="neon_hh_id", how="left",
    )
    book["neon_hh_id"] = book["neon_hh_id"].astype("string")
    book["name"] = book["name"].fillna(book["neon_hh_id"])
    book = book.rename(columns={"address": "street"})
    for col in BOOK_COLUMNS:
        if col not in book.columns:
            book[col] = pd.NA
    book["in_neon"] = True

    # -- Fall 2025 appeal: who was actually mailed, by Neon id (exact, no name match) --
    mailed = set(appeal_ids["neon_hh_id"].dropna().astype(str))
    acct_to_hh = (
        accounts.dropna(subset=["account_id"])
        .drop_duplicates(subset=["account_id"])
        .set_index(accounts.dropna(subset=["account_id"]).drop_duplicates(subset=["account_id"])["account_id"].astype(str))["id"]
        .astype(str)
    )
    mailed |= {
        hh for hh in (acct_to_hh.get(a) for a in appeal_ids["account_id"].dropna().astype(str))
        if hh is not None
    }
    book["mailed_2025"] = book["neon_hh_id"].isin(mailed)

    # -- Fort Salem: flags onto matched Neon rows; standalone rows for the rest --------
    variants: dict[str, set[str]] = {}  # neon hh id -> other names we know them by
    for hh_id, grp in fst_summary[fst_summary["in_neon"]].groupby("id"):
        at = book["neon_hh_id"].eq(str(hh_id))
        book.loc[at, "fst"] = True
        book.loc[at, "fst_best_tier"] = max(
            grp["best_tier"], key=lambda t: TIER_RANK.get(str(t).strip().lower(), 0)
        )
        book.loc[at, "fst_years"] = _union_years(grp["years"])
        variants.setdefault(str(hh_id), set()).update(str(n) for n in grp["name"])

    notes = contact_notes.drop_duplicates("household_name").set_index("household_name")
    original_name: dict[str, str] = {}  # listed Fort Salem name -> book display name
    fst_solo = fst_summary[~fst_summary["in_neon"]].reset_index(drop=True)
    fst_solo_kept = fst_keep_mask(fst_solo)
    solo_rows: list[dict] = []
    for i, r in enumerate(fst_solo.itertuples(index=False)):
        name = str(r.name)
        note = notes.loc[name] if name in notes.index else None
        # survivor relabel (the mailing-list fold's policy): mail goes to the living
        display = name
        if note is not None and isinstance(note["survivor"], str) and note["survivor"]:
            display = str(note["survivor"])
        original_name[name] = display
        solo_rows.append(
            {
                "name": display,
                "fst": True,
                "fst_best_tier": r.best_tier,
                "fst_years": r.years,
                "fst_rule_b": "kept" if fst_solo_kept.iloc[i] else "below-bar",
                "deceased": bool(note["deceased"]) if note is not None else False,
                "web_note": note["contact_note"] if note is not None else None,
            }
        )

    # -- received lists: exact matches flag Neon rows; the rest join the solo pool -----
    mfs_hh: dict[str, str] = {}  # mfs donor name -> Neon household id, when matched
    for key, frame in received.items():
        matched = list_matches.get(key)
        if matched is None:
            continue
        hit = matched["id"].notna()
        for name, hh_id in zip(frame.loc[hit, "name"], matched.loc[hit, "id"], strict=True):
            at = book["neon_hh_id"].eq(str(hh_id))
            book.loc[at, key] = True
            variants.setdefault(str(hh_id), set()).add(str(name))
            if key == "mfs_donor":
                mfs_hh[str(name)] = str(hh_id)
        for r in frame.loc[~hit].itertuples(index=False):
            row = {"name": str(r.name), key: True}
            if key == "mfs_donor":
                row = row | {
                    "_mfs_street": getattr(r, "street", pd.NA),
                    "_mfs_city": getattr(r, "city", pd.NA),
                    "_mfs_state": getattr(r, "state_province", pd.NA),
                    "_mfs_zip": getattr(r, "zip_code", pd.NA),
                }
            solo_rows.append(row)
    book["also_listed_as"] = book["neon_hh_id"].map(
        {k: "; ".join(sorted(v)) for k, v in variants.items()}
    )

    solo, display_name = _merge_solo_across_lists(pd.DataFrame(solo_rows))

    # -- candidates: every address on file, with source + rank ------------------------
    mfs_identity: dict[str, str] = {}  # mfs donor name -> identity (hh id or display)
    for name in {str(n) for n in received.get("mfs_donor", pd.DataFrame(columns=["name"]))["name"]}:
        mfs_identity[name] = mfs_hh.get(name) or display_name.get(name, name)
    candidates = _address_candidates(
        book, solo, roll_hits, contact_notes, original_name,
        mfs_frame=received.get("mfs_donor", pd.DataFrame()), mfs_identity=mfs_identity,
    )

    # -- best address per identity (lowest rank; stable order breaks ties) ------------
    best = (
        candidates.sort_values(["rank", "source"], kind="stable")
        .drop_duplicates("identity", keep="first")
        .set_index("identity")[["street", "city", "state_province", "zip_code", "source"]]
        .rename(columns={"street": "address", "source": "address_source"})
    )
    conflicts = (
        candidates.assign(_norm=_norm_street(candidates["street"]))
        .groupby("identity")["_norm"].nunique().gt(1)
    )

    # -- assemble: Neon rows + standalone rows, then fill chosen addresses -------------
    solo_book = pd.DataFrame(
        {
            "neon_hh_id": pd.NA,
            "name": solo["name"],
            "in_neon": False,
            "fst": solo.get("fst", False),
            "fst_best_tier": solo.get("fst_best_tier"),
            "fst_years": solo.get("fst_years"),
            "fst_rule_b": solo.get("fst_rule_b"),
            "mfs_donor": solo.get("mfs_donor", False),
            "friends_to_add": solo.get("friends_to_add", False),
            "mfs_attendee": solo.get("mfs_attendee", False),
            "deceased": solo.get("deceased", False),
            "web_note": solo.get("web_note"),
        }
    )
    book = pd.concat(
        [book[BOOK_COLUMNS], solo_book.reindex(columns=BOOK_COLUMNS)], ignore_index=True
    )
    identity = book["neon_hh_id"].fillna(book["name"])
    book = book.assign(
        address=identity.map(best["address"]),
        city=identity.map(best["city"]),
        state_province=identity.map(best["state_province"]),
        zip_code=identity.map(best["zip_code"]),
        address_source=identity.map(best["address_source"]),
        address_conflict=identity.map(conflicts).fillna(False),
        po_box=identity.map(best["address"]).apply(
            lambda s: bool(is_po_box(s)) if pd.notna(s) else False
        ),
    )

    # -- mailing-list context: the letter it would get, Don's notes --------------------
    if not mailing_list.empty:
        by_hh = (
            mailing_list.assign(_hh=mailing_list["neon_hh_id"].astype("string"))
            .dropna(subset=["_hh"])
            .drop_duplicates(subset=["_hh"])
            .set_index("_hh")
        )
        at = book["in_neon"] & book["neon_hh_id"].isin(by_hh.index)
        book.loc[at, "in_mailing_list"] = True
        book.loc[at, "letter"] = book.loc[at, "neon_hh_id"].map(by_hh["letter"])
        if "note_boyd" in by_hh.columns:
            book.loc[at, "note_boyd"] = book.loc[at, "neon_hh_id"].map(by_hh["note_boyd"])
        fst_ml = mailing_list[mailing_list["letter"].eq("fst-personal")]
        at_solo = ~book["in_neon"] & book["name"].isin(fst_ml["household_name"])
        book.loc[at_solo, "in_mailing_list"] = True
        book.loc[at_solo, "letter"] = "fst-personal"

    # -- fuzzy Neon candidates for standalone rows (shown, never folded) ---------------
    if not solo_book.empty:
        pool = pd.DataFrame(
            {"name": solo_book["name"], "fst_best_tier": pd.NA, "fst_years": pd.NA}
        )
        cands = fuzzy_fst_candidates(pool, accounts)
        top = (
            cands[cands["rank"].eq(1)]
            .set_index("fst_name")
            .apply(
                lambda r: f"{r['score']:.0f} {r['neon_household']} ({r['neon_city']})",
                axis=1,
            )
        )
        book.loc[~book["in_neon"], "possible_neon_match"] = (
            book.loc[~book["in_neon"], "name"].map(top)
        )

    book = book.sort_values(["in_neon", "name"], ascending=[False, True]).reset_index(drop=True)
    book.attrs["n_companies_excluded"] = int(accounts["account_type"].eq("Company").sum())
    return book[BOOK_COLUMNS], candidates[CANDIDATE_COLUMNS]


def _merge_solo_across_lists(solo: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """Merge standalone rows from different lists on exact canonical-key equality.

    The display name keeps the Fort Salem variant when one exists (it carries tier and
    years, and the assessment-roll research is keyed to it); flags union. Rows whose
    name has no parseable given name never merge — they stay single rather than
    guessed. Returns ``(merged, display_name)`` mapping every input name to the display
    name it folded into, so source-keyed research still attaches after a merge.
    """
    if solo.empty:
        return solo, {}
    keys = solo["name"].map(lambda n: _canonical_key(str(n)))
    by_key: dict[tuple, list[int]] = {}
    for i, k in enumerate(keys):
        if k is not None:
            by_key.setdefault(k, []).append(i)
    out: list[dict] = []
    display: dict[str, str] = {}
    claimed: set[int] = set()
    for i in range(len(solo)):
        if i in claimed:
            continue
        members = [i] + [j for j in by_key.get(keys.iloc[i], []) if j != i]
        claimed.update(members)
        grp = solo.iloc[sorted(members)]
        row: dict = {"name": grp.iloc[0]["name"]}
        for col in solo.columns:
            if col == "name":
                continue
            if col in _BOOL_FLAGS:
                row[col] = bool(grp[col].fillna(False).astype(bool).any())
            else:
                vals = grp[col].dropna()
                row[col] = vals.iloc[0] if len(vals) else pd.NA
        out.append(row)
        for n in grp["name"]:
            display[str(n)] = str(row["name"])
    return pd.DataFrame(out), display


def _address_candidates(
    book: pd.DataFrame,
    solo: pd.DataFrame,
    roll_hits: pd.DataFrame,
    contact_notes: pd.DataFrame,
    original_name: dict[str, str],
    *,
    mfs_frame: pd.DataFrame,
    mfs_identity: dict[str, str],
) -> pd.DataFrame:
    """One row per (identity, source) address — the provenance behind the best pick.

    ``original_name`` maps a listed Fort Salem name to the book's display name for it
    (survivor relabels); ``mfs_identity`` maps an MfS donor name to its identity
    (Neon household id when matched, display name otherwise), so an MfS address is a
    candidate for a matched household too — it can fill a blank Neon address.
    """
    rows: list[dict] = []
    for r in book.loc[book["street"].notna()].itertuples(index=False):
        rows.append(
            {
                "identity": r.neon_hh_id, "name": r.name, "source": "neon",
                "rank": ADDRESS_SOURCE_RANK["neon"], "street": r.street,
                "city": r.city, "state_province": r.state_province,
                "zip_code": r.zip_code, "detail": "current Neon pull",
            }
        )
    if not roll_hits.empty:
        for r in roll_hits.itertuples(index=False):
            strength = "strong" if str(r.confidence) == "strong" else "probable"
            source = f"roll-{strength}"
            identity = original_name.get(str(r.household_name), str(r.household_name))
            rows.append(
                {
                    "identity": identity, "name": str(r.household_name), "source": source,
                    "rank": ADDRESS_SOURCE_RANK[source], "street": r.street,
                    "city": r.city, "state_province": r.state, "zip_code": r.zip,
                    "detail": f"{r.source}; owner: {r.owners}",
                }
            )
    if not mfs_frame.empty:
        for r in mfs_frame.itertuples(index=False):
            if pd.isna(r.street):
                continue
            rows.append(
                {
                    "identity": mfs_identity.get(str(r.name), str(r.name)),
                    "name": str(r.name), "source": "mfs-list",
                    "rank": ADDRESS_SOURCE_RANK["mfs-list"], "street": r.street,
                    "city": r.city, "state_province": r.state_province,
                    "zip_code": r.zip_code, "detail": "MfS 2026 donor list",
                }
            )
    if not contact_notes.empty:
        for r in contact_notes.itertuples(index=False):
            if str(r.contact_confidence) == "business" and pd.notna(r.contact_address):
                identity = original_name.get(str(r.household_name), str(r.household_name))
                rows.append(
                    {
                        "identity": identity, "name": str(r.household_name),
                        "source": "web-business", "rank": ADDRESS_SOURCE_RANK["web-business"],
                        "street": r.contact_address, "city": pd.NA, "state_province": pd.NA,
                        "zip_code": pd.NA, "detail": str(r.contact_note or "web research"),
                    }
                )
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)
