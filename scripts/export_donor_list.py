"""Build the fall-2026 donor-list draft (local-only, PII).

First cut of the final mailing list (Don, 2026-09-10). Categories are applied in
priority order so each household lands in exactly one; every row carries an address
(believed good — best per the address-book precedence; conflicts are flagged in the
board sheet's notes). Successive cuts change the constants below and re-run.

Outputs (data/20_processed/, never published):
  final-mailing-list-draft.xlsx  - sheet 1 "board" (full detail), sheet 2 "printer" (labels),
                                    sheet 3 "do_not_contact" (would-qualify-but-DNC review,
                                    ids from 1000), sheet 4 "not_in_neon" (so they can be
                                    added to Neon)
  final-mailing-list-draft.md    - annotated category table, individuals listed per category

Usage:
    python scripts/export_donor_list.py [suffix]   # suffix labels draft file names
"""
from __future__ import annotations

import re
import sys

import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from hh import config, io
from hh.analytics.donors import INTERNAL_ACCOUNT_IDS
from hh.analytics.mailing import DON_FY_COLUMNS, GIVING_FYS, gifts_by_fy
from hh.clean.accounts import clean_accounts
from hh.clean.donations import clean_donations
from hh.external import mailing as ml
from hh.external.mailing import match_households

XLSX_FILENAME = "final-mailing-list-draft.xlsx"
MD_FILENAME = "final-mailing-list-draft.md"

# -- category rules (Don, 2026-09-10, draft 1) -------------------------------------
MIN_DONOR_5YR = 150.0       # cat 2: gave to no campaign, FY22-26 total at least this
MIN_ENGAGED_SPEND = 500.0   # cat 4: no 5-yr gift, FY22-26 spend at least this
MIN_NEW_ACCOUNT_REG = 50.0  # cat 5: Judy's new-accounts workbook, lifetime registrations

# cat 6: the silent keep-list rows below every bar, minus rulings (Don, 2026-09-10)
LAPSED_EXCLUDE = {"george scurria"}

# cat 9: MfS rows ruled the SAME household as an existing Neon record (Don, 2026-09-10:
# "definitely don't want to add Akland" + the near-certain fuzzy matches accepted for
# draft 1). They fold into their Neon households, which the Neon categories already
# count — they are not new prospects.
MFS_FOLD_INTO_NEON = {
    "andrew miller", "anne miller & donald minkel", "clancy & darlene king",
    "don patten", "eleanor devries", "graham kerr", "jennifer wiebe & syrus sipperly",
    "kathy idleman", "ken strickler", "laura & edward bernard", "lynne gelber",
    "michelle nagai", "patricia towers", "paula j. sawyer", "robert & carolyn akland",
    "rulyn & tom graves", "susan & stephen snyder", "susan kenyon & tim troy",
    "tara & scott smith", "donna & harry orlik",
}

# Labels carry their cutoffs so the board sheet's category column reads standalone
CATEGORY_LABELS = {
    1: "2025 appeal giver",                       # $10+ to the campaign, Oct 25-Jan 26
    2: "donor $150+ FY22-26",                     # no campaign gift
    3: "donor <$150 w/ steward",                  # gave, under the bar, steward assigned
    4: "engaged non-donor $500+ spend",           # no 5-yr gift; classes/tickets spend
    5: "new account FY25-26 $50+ reg",            # Judy's list, lifetime registrations
    6: "lapsed donor - keep",                     # hand-picked, below every bar
    7: "MfS donor in Neon, no other category",    # Don, 2026-09-11: keep the whole MfS list
    8: "FST sponsor w/ address",                  # Fort Salem, not in Neon
    9: "MfS donor w/ address",                    # Music from Salem, not in Neon
    10: "board add - in Neon",                    # Don-nominated, in Neon, no screen passed
    11: "board add - not in Neon",                # Don-nominated, address supplied by hand
}

IN_NEON_CATEGORIES = {1, 2, 3, 4, 5, 6, 7, 10}
SUPER = {k: ("In Neon" if k in IN_NEON_CATEGORIES else "Not in Neon") for k in CATEGORY_LABELS}

# md display order keeps the In-Neon / Not-in-Neon groups contiguous even though the
# board-add numbers (10/11) were assigned after 8/9 already existed
CATEGORY_DISPLAY_ORDER = [1, 2, 3, 4, 5, 6, 7, 10, 8, 9, 11]

PRINTER_COLUMNS = ["id", "mailing_name", "salutation", "address", "city", "state", "zip"]
BOARD_COLUMNS = PRINTER_COLUMNS + [
    "category", "email", "phone",
    "neon_hh_id", "last_name", "donations_2025_26", "donations_5yr",
    "steward", "notes",
    "in_neon", "do_not_contact", "deceased",
]

# xlsx column widths (Don, 2026-09-11: "see the names, and most of the address" without
# having to widen every column by hand) and the plain-number format for the donation
# columns ("comma formatted, no decimals, no dollar sign")
COLUMN_WIDTHS = {
    "mailing_name": 28, "salutation": 18, "address": 26, "city": 14, "category": 26,
    "email": 24, "notes": 40,
}
DOLLAR_COLUMNS = {"donations_2025_26", "donations_5yr"}
DOLLAR_FORMAT = "#,##0"

# constructed (not from Neon) salutations get flagged for review - Don, 2026-09-11
REVIEW_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
REVIEW_FONT = Font(bold=True)

# below-table individual rosters (in the md): only for categories small enough that a
# full name list is itself useful, not a wall of text (Don, 2026-09-11)
INDIVIDUAL_LIST_MAX = 10

# do_not_contact sheet ids start here (Don, 2026-09-11: keep them visibly distinct from
# the board sheet's own 1..N ids)
DNC_ID_START = 1000

# "Ann & Bob Smith" -> ("smith", "ann"): labels sort by surname, then first listed name
_JUNK = re.compile(r"\b(?:mr|mrs|ms|dr|and|the|family)\b|[.,]", re.I)


def _sort_key(name: str) -> tuple[str, str]:
    s = re.sub(r"\(.*?\)", "", str(name))
    s = re.sub(r"\s+", " ", _JUNK.sub(" ", s)).strip()
    toks = s.split()
    if not toks:
        return ("", "")
    return (toks[-1].lower(), toks[0].lower())


def _last_name(name: str) -> str | None:
    """Same surname token _sort_key already uses to sort (last token once the
    Mr/Mrs/and/parens junk is stripped), exposed as its own column."""
    s = re.sub(r"\(.*?\)", "", str(name))
    s = re.sub(r"\s+", " ", _JUNK.sub(" ", s)).strip()
    toks = s.split()
    return toks[-1] if toks else None


def _construct_salutation(name: str) -> str | None:
    """Best-effort salutation when Neon has none on file: first name(s) only, e.g.
    "Ann & Bob Smith" -> "Ann & Bob", "Katherine Kelleher & John Franklin" -> "Katherine
    & John", "Elizabeth L. Ellard" -> "Elizabeth", "Mary Ann Spiezio" -> "Mary Ann"
    (a compound given name survives; a bare initial does not). A guess, not a lookup -
    callers flag these for review rather than trusting them outright (Don, 2026-09-11)."""
    s = re.sub(r"\s+", " ", str(name)).strip()
    if not s:
        return None
    parts = re.split(r"\s*(?:&|\band\b)\s*", s, flags=re.I)
    firsts = []
    for p in parts:
        toks = p.split()
        if not toks:
            continue
        if len(toks) == 1:            # bare mononym part, e.g. "Smith & Assoc"
            firsts.append(toks[0])
            continue
        given = toks[:-1]             # everything but the surname token
        while len(given) > 1 and re.fullmatch(r"[A-Za-z]\.?", given[-1]):
            given = given[:-1]        # drop trailing middle initials ("Elizabeth L.")
        firsts.append(" ".join(given))
    return " & ".join(firsts) if firsts else s


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name)).strip().lower()


def _label_name(name: str) -> str:
    """Mailing-label name: FST/MfS annotations like '(in memory of ...)' come off."""
    return re.sub(r"\s*\(.*?\)\s*", " ", str(name)).strip() or str(name)


# Business addresses arrive as one free-text line ("4 Care Ln, Saratoga Springs, NY
# 12866 (practice)"); the printer needs them split. Keyed by book name (Don, 2026-09-11:
# both FST business-address donors stay on the list).
BUSINESS_ADDRESS = {
    "lionel bulford": ("4 Care Ln", "Saratoga Springs", "NY", "12866"),
    "rana bitar and joseph jacob": ("2125 River Rd Ste 100", "Niskayuna", "NY", "12309"),
}

# cat 7 (MfS donor in Neon): Don reviewed all 8 Neon/MfS address conflicts in this
# category (2026-09-11) and confirmed Neon is correct for everyone except these two,
# who carry a real second (NYC) address on the MfS list - noted, not conflict-flagged.
MFS_2ND_ADDRESS = {
    "sarah gallagher": "1136 First Avenue, New York, NY 10065",
    "susan crile": "168 West 86th Street, Apt. 6B, New York, NY 10024",
}

# Hand rulings (Don, 2026-09-13), applied on top of every category path so the
# household cannot resurface through a different screen:
#   - Joan Duff-Bohrer is Neon household "Joan Bohrer & Stephen Schatz" (543): removed
#     at Don's direction; her partner Stephen Schatz is deceased (also recorded in the
#     md - worth having Judy mark him deceased in Neon).
#   - Kenneth Strickler (2344): Don believes he has moved. His MfS row folds into this
#     same Neon household, so excluding both name forms covers either path.
#   - Lucas Sconzo (3945, $310 5-yr donor): removed at Don's direction (2026-09-13,
#     same evening). Larry Sconzo (132) is a separate household and stays.
MAILING_EXCLUDE = {
    "joan bohrer & stephen schatz", "kenneth strickler", "ken strickler", "lucas sconzo",
}


def _excluded(name: str) -> bool:
    return _norm(name) in MAILING_EXCLUDE


# Board adds (Don, 2026-09-13): hand-nominated households no screen catches. Keyed by
# the book name (normalized); the note is Don's reason. In-Neon keys land in category
# 10 (Carol Brownell: $1.50 in five years, no steward, no spend bar); not-in-Neon keys
# with a hand-supplied address (see BOARD_ADD_ADDRESSES in the address book) land in
# category 11. Re-check the keys after a fresh Neon pull.
BOARD_ADD_NOTES = {
    "carol brownell": "board add (Don 2026-09-13); failed every screen; Neon spelling of first name confirmed",
    "elsa jean brancaleone": "board add (Don 2026-09-13); personal friend; Don expects $500+ gift",
    "mary ann spiezio": (
        "board add (Don 2026-09-13); Neon acct 37929 mistyped Company; PO Box addr per "
        "Neon 'Mailing Address' note; business: 688 Wilbur Ave (Fort Miller Group)"
    ),
    # Don wrote "Sorenson"; Neon's household name spells it Sorensen - kept as Neon has it
    "diane kennedy & jon sorensen": (
        "board add (Don 2026-09-13); $129 5-yr giving is under the $150 bar, no steward"
    ),
}


def _clean_zip(z) -> str | None:
    """Label-ready 5-digit ZIP (Don, 2026-09-13: "5-digit zip instead of 9 digit").
    Leading zeros restored (Excel/Neon drop them for New England); ZIP+4 suffixes
    dropped. Anything unrecognizable passes through untouched."""
    if pd.isna(z):
        return None
    s = re.sub(r"[^0-9]", "", str(z))
    if re.fullmatch(r"\d{1,9}", s):
        return s.zfill(5)[:5]
    return str(z).strip() or None


def _clean_city(c) -> str | None:
    """Label-ready city: whitespace squeezed, a trailing ', NY' dropped, ALL-CAPS
    title-cased ('CAMBRIDGE' -> 'Cambridge'); mixed-case entries are left alone."""
    if pd.isna(c):
        return None
    s = re.sub(r"\s+", " ", str(c)).strip()
    s = re.sub(r",\s*[A-Z]{2}$", "", s)
    if s.isupper():
        s = s.title()
    return s or None


def _tidy(board: pd.DataFrame) -> pd.DataFrame:
    """Printer hygiene on the assembled rows (see the helpers above)."""
    board = board.copy()
    for r in board.itertuples():
        biz = BUSINESS_ADDRESS.get(_norm(r.mailing_name))
        if biz:
            board.loc[r.Index, ["address", "city", "state", "zip"]] = biz
    board["address"] = board["address"].map(
        lambda a: re.sub(r"\s+", " ", str(a)).strip().rstrip(",") if pd.notna(a) else a
    )
    board["city"] = board["city"].map(_clean_city)
    board["state"] = board["state"].map(lambda s: str(s).strip().upper() if pd.notna(s) else s)
    board["zip"] = board["zip"].map(_clean_zip)
    # a blank state is filled from other rows sharing the same city and ZIP (one Neon
    # record lacks it); unmatched blanks stay blank and are flagged in the md
    known = (
        board.dropna(subset=["state"])
        .loc[lambda d: d["state"].ne("")]
        .drop_duplicates(["city", "zip"])
        .set_index(["city", "zip"])["state"]
    )
    blank = board["state"].isna() | board["state"].eq("")
    for i in board.index[blank]:
        key = (board.at[i, "city"], board.at[i, "zip"])
        if key in known.index:
            board.at[i, "state"] = known[key]
    return board


def _classify(pop: pd.DataFrame) -> tuple[dict[int, pd.Series], pd.Series]:
    """cat[1..5] + the silent-keep(6) test, applied to any Neon-side population
    (the main `alive` pool, or the do-not-contact review pool - same rules either way)."""
    cat: dict[int, pd.Series] = {}
    cat[1] = pop["src_appeal_gift"] | (pop["don_appeal_window"].fillna(0) >= 10)
    taken = cat[1].copy()
    cat[2] = ~taken & (pop["don_5yr_total"].fillna(0) >= MIN_DONOR_5YR); taken |= cat[2]
    cat[3] = ~taken & pop["steward"].notna() & (pop["don_5yr_total"].fillna(0) > 0); taken |= cat[3]
    cat[4] = ~taken & pop["src_engaged_nondonor"]; taken |= cat[4]
    cat[5] = ~taken & pop["src_new_accounts"]
    silent = pop["src_silent_selected"] & ~(cat[1] | cat[2] | cat[3] | cat[4] | cat[5])
    silent &= ~pop["household_name"].map(lambda n: _norm(n) in LAPSED_EXCLUDE)
    return cat, silent


def _salutation_map(m: pd.DataFrame) -> pd.Series:
    """id -> Neon salutation (household-level wins, individual fills gaps - already
    resolved by build_mailing_list()); id -> None where a household isn't in `m` at all
    (Don, 2026-09-11: "add the salutation (from neon) to ALL tabs of the workbook")."""
    return (
        m.assign(_id=m["neon_hh_id"].astype(str)).drop_duplicates("_id")
        .set_index("_id")["salutation"]
    )


def build() -> pd.DataFrame:
    m = io.read_parquet("processed", "mailing_list.parquet")
    book = io.read_parquet("processed", "address_book.parquet")
    b = book.set_index(book["neon_hh_id"].fillna("__" + book["name"].astype(str)))
    salutation = _salutation_map(m)

    # fresh id -> FY-giving lookup, computed directly from donations (not restricted to
    # mailing_list.parquet's prospect universe, so it covers every row including the
    # cat-7/do-not-contact edge cases that universe leaves out)
    accounts = clean_accounts()
    gfy = gifts_by_fy(clean_donations(accounts=accounts), GIVING_FYS)
    gfy = gfy.assign(id=gfy["id"].astype(str)).set_index("id")
    fy2026 = gfy["don_fy2026"]
    fy5yr = gfy[DON_FY_COLUMNS].sum(axis=1)
    # the cash-drawer/online-registration placeholder accounts aren't real households -
    # exclude them from any ranking over "biggest donors" (mirrors build_mailing_list())
    internal_ids = set(
        accounts.loc[accounts["account_id"].isin(INTERNAL_ACCOUNT_IDS), "id"]
        .dropna().astype(str)
    )

    # -- Neon side: categories in priority order over living, contactable rows -------
    neon = m[m["neon_hh_id"].notna()].copy()
    deceased_mask = neon["deceased"].fillna(False).astype(bool)
    dnc_mask = neon["do_not_contact"].fillna(False).astype(bool)
    set_aside = neon[deceased_mask | dnc_mask]
    alive = neon[~(deceased_mask | dnc_mask)].copy()
    cat, silent = _classify(alive)

    # cat 5 expansion: Judy's $50-100 registration band, absent from the current list
    na = ml.load_new_accounts()
    reg = pd.to_numeric(na["lifetime_registration_amount"], errors="coerce").fillna(0)
    band = na[(reg >= MIN_NEW_ACCOUNT_REG) & (reg < ml.MIN_NEW_ACCOUNT_REGISTRATION)]
    households = (
        book[book["in_neon"]]
        .drop_duplicates("neon_hh_id")[["neon_hh_id", "name", "city"]]
        .rename(columns={"neon_hh_id": "id", "name": "name"})
    )
    matched = match_households(band["household_name"], households, cities=band["city"] if "city" in band.columns else None)
    band = band.assign(neon_hh_id=matched["id"].values)
    band_hit = band[band["neon_hh_id"].notna()].drop_duplicates("neon_hh_id")

    # cat 7: every household on the original MfS donor list, including ones already in
    # Neon that failed every other screen above, or that aren't in the mailing-list
    # prospect universe (m) at all (Don, 2026-09-11: "we'll want to include ALL of our
    # original list, even if in neon and failed the neon screens" - 12 of the 17 MfS
    # donors matched to a Neon household never made mailing_list.parquet's cut because
    # that table only holds households meeting some other prospect criterion already).
    # Sourced straight from the book (not `alive`/`m`) so it reaches households `m`
    # never included; the same deceased/do-not-contact set-aside applies here by hand.
    mfs_neon_ids = set(
        book.loc[book["mfs_donor"].fillna(False) & book["in_neon"], "neon_hh_id"]
        .dropna().astype(str)
    )
    captured_ids = set(
        alive.loc[cat[1] | cat[2] | cat[3] | cat[4] | cat[5] | silent, "neon_hh_id"].astype(str)
    ) | set(band_hit["neon_hh_id"].astype(str))
    cat7_ids = sorted(mfs_neon_ids - captured_ids)
    in_m_ids = set(neon["neon_hh_id"].astype(str))

    rows = []
    for k in (1, 2, 3, 4, 5):
        for r in alive[cat[k]].itertuples(index=False):
            rows.append(_neon_row(r, b, k))
    for r in band_hit.itertuples(index=False):
        rows.append(_band_row(r, b, salutation))
    for r in alive[silent].itertuples(index=False):
        rows.append(_neon_row(r, b, 6))
    for hh_id in cat7_ids:
        bk = b.loc[hh_id]
        if bool(bk["do_not_contact"]) or bool(bk["deceased"]):
            continue
        note = (
            "on the MfS donor list; no other qualifying category"
            if hh_id in in_m_ids
            else "on the MfS donor list; not otherwise in the prospect universe"
        )
        second_addr = MFS_2ND_ADDRESS.get(_norm(bk["name"]))
        if second_addr:
            note = f"2nd address: {second_addr}; {note}"
        rows.append({
            "mailing_name": _label_name(bk["name"]), "salutation": salutation.get(hh_id),
            "address": bk["address"],
            "city": bk["city"], "state": bk["state_province"], "zip": bk["zip_code"],
            "category": CATEGORY_LABELS[7], "email": bk["email"], "phone": bk["phone"],
            "steward": None, "notes": note, "neon_hh_id": hh_id, "in_neon": True,
            "do_not_contact": bool(bk["do_not_contact"]), "deceased": bool(bk["deceased"]),
        })

    # -- not-in-Neon side ------------------------------------------------------------
    solo = book[~book["in_neon"]]
    fst = solo[solo["fst_rule_b"].eq("kept") & solo["address"].notna()]
    for r in fst.itertuples(index=False):
        rows.append(
            {
                "mailing_name": _label_name(r.name), "salutation": None,
                "address": r.address, "city": r.city,
                "state": r.state_province, "zip": r.zip_code,
                "category": CATEGORY_LABELS[8],
                "email": r.research_email, "phone": r.research_phone, "steward": None,
                "notes": f"FST {r.fst_best_tier} {r.fst_years}; addr {r.address_source}",
                "neon_hh_id": None,
                "in_neon": False, "do_not_contact": bool(r.do_not_contact) if pd.notna(r.do_not_contact) else None,
                "deceased": bool(r.deceased),
            }
        )
    mfs = solo[
        solo["mfs_donor"].fillna(False) & solo["address"].notna()
        & ~solo["name"].map(lambda n: _norm(n) in MFS_FOLD_INTO_NEON)
        & ~solo["fst_rule_b"].eq("kept")  # an FST+MfS household rides category 7 once
    ]
    for r in mfs.itertuples(index=False):
        note = f"addr {r.address_source}"
        if pd.notna(r.possible_neon_match):
            note += f"; possible Neon match: {r.possible_neon_match}"
        rows.append(
            {
                "mailing_name": _label_name(r.name), "salutation": None,
                "address": r.address, "city": r.city,
                "state": r.state_province, "zip": r.zip_code,
                "category": CATEGORY_LABELS[9],
                "email": r.research_email, "phone": r.research_phone, "steward": None,
                "notes": note, "neon_hh_id": None,
                "in_neon": False, "do_not_contact": bool(r.do_not_contact) if pd.notna(r.do_not_contact) else None,
                "deceased": bool(r.deceased),
            }
        )

    # -- board adds (Don, 2026-09-13) -----------------------------------------------
    for key, note in BOARD_ADD_NOTES.items():
        for r in book[book["name"].map(lambda n: _norm(n) == key)].itertuples(index=False):
            if r.in_neon:
                hh_id = str(r.neon_hh_id)
                if hh_id in captured_ids or bool(r.deceased) or bool(r.do_not_contact):
                    continue  # a real screen already caught it, or it's set aside
                rows.append({
                    "mailing_name": _label_name(r.name), "salutation": salutation.get(hh_id),
                    "address": r.address, "city": r.city, "state": r.state_province,
                    "zip": r.zip_code, "category": CATEGORY_LABELS[10],
                    "email": r.email, "phone": r.phone, "steward": None,
                    "notes": note, "neon_hh_id": hh_id, "in_neon": True,
                    "do_not_contact": bool(r.do_not_contact), "deceased": bool(r.deceased),
                })
            elif r.address is not None and not pd.isna(r.address) and (
                r.fst_rule_b != "kept"  # an FST+friend household rides category 8
                and not (r.mfs_donor if pd.notna(r.mfs_donor) else False)  # MfS rides 7/9
            ):
                rows.append({
                    "mailing_name": _label_name(r.name), "salutation": None,
                    "address": r.address, "city": r.city, "state": r.state_province,
                    "zip": r.zip_code, "category": CATEGORY_LABELS[11],
                    "email": r.research_email, "phone": r.research_phone, "steward": None,
                    "notes": note, "neon_hh_id": None, "in_neon": False,
                    "do_not_contact": None, "deceased": bool(r.deceased),
                })

    # hand removals last, so they override every path above
    hand_removed = sum(1 for r in rows if _excluded(r["mailing_name"]))
    rows = [r for r in rows if not _excluded(r["mailing_name"])]

    n_built = len(rows)
    board = _finalize(pd.DataFrame(rows), fy2026, fy5yr, id_start=1)
    board.attrs["qa"] = {
        "set_aside_deceased_dnc": len(set_aside),
        "band_unmatched": int(band["neon_hh_id"].isna().sum()),
        "mfs_folded": len(MFS_FOLD_INTO_NEON),
        "hand_removed": hand_removed,
        "dropped_no_address": n_built - len(board),
    }
    dnc_raw = _dnc_review(neon, dnc_mask, deceased_mask, book, b, salutation)
    board.attrs["dnc_review"] = _finalize(dnc_raw, fy2026, fy5yr, id_start=DNC_ID_START)
    reception_raw = _reception_draft(board, book, b, m, fy5yr, internal_ids)
    board.attrs["reception_draft"] = _finalize(reception_raw, fy2026, fy5yr, id_start=1)
    return board


RECEPTION_TOP_N = 30  # Don, 2026-09-11: 34 FST sponsors + the 30 largest 5yr donors

# Reception invites among the board adds - NOT every board add comes to the reception
# (Don, 2026-09-13: Mary Ann Spiezio yes; Carol Brownell and Elsa Brancaleone no).
# Keep this hand list deliberate as board adds grow.
RECEPTION_BOARD_ADDS = {"mary ann spiezio"}


def _reception_draft(
    board: pd.DataFrame, book: pd.DataFrame, b: pd.DataFrame, m: pd.DataFrame,
    fy5yr: pd.Series, internal_ids: set[str],
) -> pd.DataFrame:
    """FST sponsors + HH's largest living 5-year donors, for reception planning.

    The top-donor half is built fresh from the book/donations, not reused from `board`,
    because the largest donors aren't guaranteed to be reachable through it - the ranking
    isn't restricted to mailing_list.parquet's narrower prospect universe (same reason
    category 7 needed a book-sourced fallback).
    """
    fst = board.loc[board["category"].eq(CATEGORY_LABELS[8]), BOARD_COLUMNS[1:]].copy()

    living_ids = set(
        book.loc[book["in_neon"] & ~book["deceased"].fillna(False), "neon_hh_id"]
        .dropna().astype(str)
    ) - internal_ids
    living_ids -= set(  # hand-removed households don't rank (Don, 2026-09-13)
        book.loc[book["name"].map(_excluded), "neon_hh_id"].dropna().astype(str)
    )
    ranked = fy5yr[fy5yr.index.isin(living_ids)].sort_values(ascending=False)
    top = ranked.head(RECEPTION_TOP_N)

    steward_map = (
        m.assign(_id=m["neon_hh_id"].astype(str)).drop_duplicates("_id")
        .set_index("_id")["steward"]
    )
    salutation = _salutation_map(m)
    rows = []
    for rank, (hh_id, _total) in enumerate(top.items(), start=1):
        bk = b.loc[hh_id]
        rows.append({
            "mailing_name": _label_name(bk["name"]), "salutation": salutation.get(hh_id),
            "address": bk["address"],
            "city": bk["city"], "state": bk["state_province"], "zip": bk["zip_code"],
            "category": f"top {RECEPTION_TOP_N} 5yr donor", "email": bk["email"],
            "phone": bk["phone"], "neon_hh_id": hh_id, "steward": steward_map.get(hh_id),
            "notes": f"5yr total rank #{rank} of Neon donors",
            "in_neon": True, "do_not_contact": bool(bk["do_not_contact"]),
            "deceased": bool(bk["deceased"]),
        })
    # the hand-picked board adds join the reception list too (RECEPTION_BOARD_ADDS is
    # deliberate, not automatic - see its comment)
    for key in sorted(RECEPTION_BOARD_ADDS):
        for r in book[book["name"].map(lambda n: _norm(n) == key)].itertuples(index=False):
            if r.address is None or pd.isna(r.address):
                continue  # a reception row must carry an address
            hh_id = str(r.neon_hh_id) if pd.notna(r.neon_hh_id) else None
            rows.append({
                "mailing_name": _label_name(r.name), "salutation": salutation.get(hh_id),
                "address": r.address,
                "city": r.city, "state": r.state_province, "zip": r.zip_code,
                "category": "board add - reception invite",
                "email": r.email if pd.notna(r.email) else r.research_email,
                "phone": r.phone if pd.notna(r.phone) else r.research_phone,
                "neon_hh_id": hh_id, "steward": steward_map.get(hh_id),
                "notes": "reception invite per Don (2026-09-13)",
                "in_neon": bool(r.in_neon),
                "do_not_contact": bool(r.do_not_contact) if pd.notna(r.do_not_contact) else None,
                "deceased": bool(r.deceased),
            })
    donors = pd.DataFrame(rows, columns=BOARD_COLUMNS[1:])
    return pd.concat([fst, donors], ignore_index=True)


def _enrich(df: pd.DataFrame, fy2026: pd.Series, fy5yr: pd.Series) -> pd.DataFrame:
    """Adds last_name, the two donation-total columns, and fills any blank salutation
    with a constructed guess (Don, 2026-09-11). `salutation_needs_review` is not an
    exported column - main() reads it to highlight the constructed cells in the xlsx."""
    df = df.copy()
    df["last_name"] = df["mailing_name"].map(_last_name)
    has_id = df["neon_hh_id"].notna()
    ids = df["neon_hh_id"].where(has_id, "")
    df["donations_2025_26"] = ids.map(fy2026).fillna(0.0).where(has_id)
    df["donations_5yr"] = ids.map(fy5yr).fillna(0.0).where(has_id)
    df["salutation_needs_review"] = df["salutation"].isna() | df["salutation"].astype(str).str.strip().eq("")
    df.loc[df["salutation_needs_review"], "salutation"] = (
        df.loc[df["salutation_needs_review"], "mailing_name"].map(_construct_salutation)
    )
    return df


def _finalize(df: pd.DataFrame, fy2026: pd.Series, fy5yr: pd.Series, *, id_start: int) -> pd.DataFrame:
    """Address filter, label hygiene, enrichment, surname sort, and id numbering -
    shared by the board and the do_not_contact review sheet so both go through the
    exact same pipeline (Don, 2026-09-11: the review sheet should have every column
    the board sheet has)."""
    df = _tidy(df[df["address"].notna()])  # every row must be mailable
    df = _enrich(df, fy2026, fy5yr)
    df["__key"] = df["mailing_name"].map(_sort_key)
    # stable: equal sort keys (two "William Cormier" rows) keep build order run to run
    df = df.sort_values("__key", kind="stable").drop(columns="__key").reset_index(drop=True)
    df.insert(0, "id", range(id_start, id_start + len(df)))
    return df


def _dnc_review(
    neon: pd.DataFrame, dnc_mask: pd.Series, deceased_mask: pd.Series,
    book: pd.DataFrame, b: pd.DataFrame, salutation: pd.Series,
) -> pd.DataFrame:
    """Households excluded from the board only because do_not_contact is set (not
    deceased): everyone who WOULD have qualified for a category, for Don to examine
    before deciding whether any should actually be mailed (Don, 2026-09-11: "I don't
    think we want to [exclude every do-not-contact record] without examination")."""
    dnc_pop = neon[dnc_mask & ~deceased_mask].copy()
    dnc_pop = dnc_pop[dnc_pop["neon_hh_id"].astype(str).isin(set(b.index.astype(str)))]
    dnc_cat, dnc_silent = _classify(dnc_pop)
    rows = []
    for k in (1, 2, 3, 4, 5):
        for r in dnc_pop[dnc_cat[k]].itertuples(index=False):
            rows.append(_neon_row(r, b, k))
    for r in dnc_pop[dnc_silent].itertuples(index=False):
        rows.append(_neon_row(r, b, 6))

    mfs_neon_ids = set(
        book.loc[book["mfs_donor"].fillna(False) & book["in_neon"], "neon_hh_id"]
        .dropna().astype(str)
    )
    dnc_book_ids = set(
        book.loc[book["do_not_contact"].fillna(False) & ~book["deceased"].fillna(False), "neon_hh_id"]
        .dropna().astype(str)
    )
    captured = set(
        dnc_pop.loc[dnc_cat[1] | dnc_cat[2] | dnc_cat[3] | dnc_cat[4] | dnc_cat[5] | dnc_silent, "neon_hh_id"]
        .astype(str)
    )
    for hh_id in sorted((mfs_neon_ids & dnc_book_ids) - captured):
        bk = b.loc[hh_id]
        rows.append({
            "mailing_name": _label_name(bk["name"]), "salutation": salutation.get(hh_id),
            "address": bk["address"],
            "city": bk["city"], "state": bk["state_province"], "zip": bk["zip_code"],
            "category": CATEGORY_LABELS[7], "email": bk["email"], "phone": bk["phone"],
            "steward": None, "notes": "on the MfS donor list; no other qualifying category",
            "neon_hh_id": hh_id, "in_neon": True, "do_not_contact": True, "deceased": False,
        })
    rows = [r for r in rows if not _excluded(r["mailing_name"])]  # hand removals apply here too
    return pd.DataFrame(rows, columns=BOARD_COLUMNS[1:])


def _neon_row(r, book_indexed: pd.DataFrame, k: int, extra_note: str | None = None) -> dict:
    bk = book_indexed.loc[str(r.neon_hh_id)]
    notes = []
    if bool(bk["address_conflict"]):
        notes.append("address conflict - sources disagree")
    if isinstance(bk["web_note"], str) and bk["web_note"]:
        notes.append(str(bk["web_note"])[:80])
    if extra_note:
        notes.append(extra_note)
    return {
        "mailing_name": _label_name(r.household_name), "salutation": r.salutation,
        "address": bk["address"], "city": bk["city"], "state": bk["state_province"],
        "zip": bk["zip_code"], "category": CATEGORY_LABELS[k],
        "email": bk["email"], "phone": bk["phone"], "steward": r.steward,
        "notes": "; ".join(notes) or None, "neon_hh_id": str(r.neon_hh_id),
        "in_neon": True, "do_not_contact": bool(bk["do_not_contact"]),
        "deceased": bool(bk["deceased"]),
    }


def _band_row(r, book_indexed: pd.DataFrame, salutation: pd.Series) -> dict:
    bk = book_indexed.loc[str(r.neon_hh_id)]
    return {
        "mailing_name": _label_name(r.household_name),
        "salutation": salutation.get(str(r.neon_hh_id)),
        "address": bk["address"], "city": bk["city"], "state": bk["state_province"],
        "zip": bk["zip_code"], "category": CATEGORY_LABELS[5],
        "email": bk["email"], "phone": bk["phone"], "steward": None,
        "notes": "new account, $50-99 lifetime registrations", "neon_hh_id": str(r.neon_hh_id),
        "in_neon": True, "do_not_contact": bool(bk["do_not_contact"]),
        "deceased": bool(bk["deceased"]),
    }


def _md(board: pd.DataFrame) -> str:
    qa = board.attrs.get("qa", {})
    lines = [
        "# Final mailing list - draft 1",
        "",
        f"*{len(board)} households, every row addressed (best address per the",
        "address-book precedence: Neon > assessment-roll strong > MfS list > roll",
        "probable > web business). Sorted by surname. Board sheet carries category,",
        "contact info, steward, notes, and in_neon/do_not_contact/deceased flags;",
        "printer sheet is the label feed.*",
        "",
        "| Group | # | Category | Definition | Households |",
        "|---|---|---|---|---:|",
    ]
    counts = board["category"].value_counts()
    defs = {
        CATEGORY_LABELS[1]: "gave $10+ to last year's Annual Fund campaign (Oct 2025 - Jan 2026)",
        CATEGORY_LABELS[2]: f"no campaign gift, ${MIN_DONOR_5YR:.0f}+ total giving FY22-26",
        CATEGORY_LABELS[3]: "gave under $150 in five years; steward assigned",
        CATEGORY_LABELS[4]: f"no gift in five years; ${MIN_ENGAGED_SPEND:.0f}+ classes/tickets spend",
        CATEGORY_LABELS[5]: f"Neon account new in FY25-26 with ${MIN_NEW_ACCOUNT_REG:.0f}+ lifetime registrations",
        CATEGORY_LABELS[6]: "lapsed donors kept by hand (pre-2019 hopes); George Scurria removed 9/10",
        CATEGORY_LABELS[7]: "on the MfS donor list; in Neon but didn't pass any other screen above",
        CATEGORY_LABELS[8]: "Fort Salem sponsor, not in Neon, address found (2 are business addresses: Bitar, Bulford)",
        CATEGORY_LABELS[9]: "Music from Salem donor, not in Neon, address on the MfS list",
        CATEGORY_LABELS[10]: "Don-nominated addition, already in Neon but no screen caught them",
        CATEGORY_LABELS[11]: "Don-nominated addition, not in Neon, address supplied by hand",
    }
    super_label = ""
    for k in CATEGORY_DISPLAY_ORDER:
        label = CATEGORY_LABELS[k]
        if SUPER[k] != super_label and super_label:
            n_super = sum(
                int(counts.get(CATEGORY_LABELS[j], 0))
                for j in CATEGORY_LABELS if SUPER[j] == super_label
            )
            lines.append(f"| | | | **{super_label} subtotal** | **{n_super}** |")
            lines.append(f"| **{SUPER[k]}** | {k} | {label} | {defs[label]} | {int(counts.get(label, 0))} |")
        elif SUPER[k] != super_label:
            lines.append(f"| **{SUPER[k]}** | {k} | {label} | {defs[label]} | {int(counts.get(label, 0))} |")
        else:
            lines.append(f"| | {k} | {label} | {defs[label]} | {int(counts.get(label, 0))} |")
        super_label = SUPER[k]
    n_super = sum(
        int(counts.get(CATEGORY_LABELS[j], 0))
        for j in CATEGORY_LABELS if SUPER[j] == super_label
    )
    lines.append(f"| | | | **{super_label} subtotal** | **{n_super}** |")
    lines += [
        f"| | | | **total** | **{len(board)}** |",
        "",
        f"*Set aside: {qa.get('set_aside_deceased_dnc', 0)} Neon households deceased or",
        f"do-not-contact; {qa.get('mfs_folded', 0)} MfS rows folded into existing Neon",
        f"households as duplicates; {qa.get('band_unmatched', 0)} new-account workbook rows",
        f"could not be matched to a Neon household; 41 of the 75 rule-B Fort Salem keeps",
        "have no researched address and stay out of this draft. Matt Witten & Nancy Seid",
        "(board add, Kelvin steward) are not in Neon; await address research and join a",
        f"later cut. {len(board.attrs.get('dnc_review', []))} do-not-contact households",
        "would otherwise qualify for a category above - see the xlsx's do_not_contact",
        "sheet for review before deciding whether any should actually be mailed.*",
        "",
        "*Removed by hand (Don, 2026-09-13): Joan Duff-Bohrer (Neon household \"Joan Bohrer",
        "& Stephen Schatz\") at Don's direction - her partner Stephen Schatz is deceased;",
        "Kenneth Strickler - Don believes he has moved; Lucas Sconzo.*",
        "",
    ]
    # individuals, listed per category below the table - only for categories small
    # enough that a full roster is itself useful (Don, 2026-09-11)
    for k in CATEGORY_DISPLAY_ORDER:
        label = CATEGORY_LABELS[k]
        grp = board[board["category"].eq(label)]
        if len(grp) > INDIVIDUAL_LIST_MAX:
            continue
        lines.append(f"## {k}. {label} — {len(grp)} households")
        lines.append("")
        for r in grp.sort_values("mailing_name", key=lambda s: s.map(_sort_key)).itertuples(index=False):
            where = f"{r.city}, {r.state}" if pd.notna(r.city) else ""
            extra = f" — {r.notes}" if pd.notna(r.notes) else ""
            lines.append(f"- {r.mailing_name} ({where}){extra}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    board = build()
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    xlsx = config.layer_dir("processed") / XLSX_FILENAME.replace(".xlsx", f"{suffix}.xlsx")
    md_path = config.layer_dir("processed") / MD_FILENAME.replace(".md", f"{suffix}.md")
    dnc_review = board.attrs["dnc_review"]
    not_in_neon = board[~board["in_neon"]].reset_index(drop=True)
    reception_draft = board.attrs["reception_draft"]
    sources = {
        "printer": board, "board": board, "do_not_contact": dnc_review,
        "not_in_neon": not_in_neon, "reception_draft": reception_draft,
    }
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        board[PRINTER_COLUMNS].to_excel(xw, sheet_name="printer", index=False)
        board[BOARD_COLUMNS].to_excel(xw, sheet_name="board", index=False)
        dnc_review[BOARD_COLUMNS].to_excel(xw, sheet_name="do_not_contact", index=False)
        not_in_neon[BOARD_COLUMNS].to_excel(xw, sheet_name="not_in_neon", index=False)
        reception_draft[BOARD_COLUMNS].to_excel(xw, sheet_name="reception_draft", index=False)
        for name, sheet in xw.sheets.items():
            sheet.freeze_panes = "A2"
            columns = PRINTER_COLUMNS if name == "printer" else BOARD_COLUMNS
            for i, col in enumerate(columns, start=1):
                letter = get_column_letter(i)
                sheet.column_dimensions[letter].width = COLUMN_WIDTHS.get(col, 12)
                if col in DOLLAR_COLUMNS:
                    for cell in sheet[letter][1:]:
                        cell.number_format = DOLLAR_FORMAT
                if col == "salutation":
                    review = sources[name]["salutation_needs_review"]
                    for cell, flagged in zip(sheet[letter][1:], review):
                        if flagged:
                            cell.font = REVIEW_FONT
                            cell.fill = REVIEW_FILL
            for cell in sheet[1]:
                cell.font = Font(bold=True)
    md_path.write_text(_md(board))
    print(board["category"].value_counts().to_string())
    print(f"\n{len(board)} households -> {xlsx.name}, {md_path.name}")
    print(
        f"printer sheet leftmost, then board, then do_not_contact ({len(dnc_review)}), "
        f"then not_in_neon ({len(not_in_neon)}, so they can be added to Neon), "
        f"then reception_draft ({len(reception_draft)} = FST sponsors + top "
        f"{RECEPTION_TOP_N} 5yr donors); sorted by surname; ids 1..{len(board)}"
    )


if __name__ == "__main__":
    main()
