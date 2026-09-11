"""Build the fall-2026 donor-list draft (local-only, PII).

First cut of the final mailing list (Don, 2026-09-10). Categories are applied in
priority order so each household lands in exactly one; every row carries an address
(believed good — best per the address-book precedence; conflicts are flagged in the
board sheet's notes). Successive cuts change the constants below and re-run.

Outputs (data/20_processed/, never published):
  donor-list-draft.xlsx  - sheet 1 "board" (full detail), sheet 2 "printer" (labels)
  donor-list-draft.md    - annotated category table, individuals listed per category

Usage:
    python scripts/export_donor_list.py [suffix]   # suffix labels draft file names
"""
from __future__ import annotations

import re
import sys

import pandas as pd
from openpyxl.styles import Font

from hh import config, io
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

# cat 8: MfS rows ruled the SAME household as an existing Neon record (Don, 2026-09-10:
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
    7: "FST sponsor w/ address",                  # Fort Salem, not in Neon
    8: "MfS donor w/ address",                    # Music from Salem, not in Neon
}

SUPER = {k: ("In Neon" if k <= 6 else "Not in Neon") for k in CATEGORY_LABELS}

PRINTER_COLUMNS = ["id", "mailing_name", "address", "city", "state", "zip"]
BOARD_COLUMNS = PRINTER_COLUMNS + [
    "category", "email", "phone", "steward", "notes",
    "in_neon", "do_not_contact", "deceased",
]

# below-table individual rosters (in the md): only for categories small enough that a
# full name list is itself useful, not a wall of text (Don, 2026-09-11)
INDIVIDUAL_LIST_MAX = 10

# "Ann & Bob Smith" -> ("smith", "ann"): labels sort by surname, then first listed name
_JUNK = re.compile(r"\b(?:mr|mrs|ms|dr|and|the|family)\b|[.,]", re.I)


def _sort_key(name: str) -> tuple[str, str]:
    s = re.sub(r"\(.*?\)", "", str(name))
    s = re.sub(r"\s+", " ", _JUNK.sub(" ", s)).strip()
    toks = s.split()
    if not toks:
        return ("", "")
    return (toks[-1].lower(), toks[0].lower())


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


def _clean_zip(z) -> str | None:
    """Label-ready ZIP: leading zeros restored (Excel/Neon drop them for New England),
    ZIP+4 hyphenated. Anything unrecognizable passes through untouched."""
    if pd.isna(z):
        return None
    s = re.sub(r"[^0-9-]", "", str(z))
    if re.fullmatch(r"\d{9}", s):
        return f"{s[:5]}-{s[5:]}"
    if re.fullmatch(r"\d{1,5}", s):
        return s.zfill(5)
    if re.fullmatch(r"\d{1,5}-\d{4}", s):
        base, plus4 = s.split("-")
        return f"{base.zfill(5)}-{plus4}"
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


def build() -> pd.DataFrame:
    m = io.read_parquet("processed", "mailing_list.parquet")
    book = io.read_parquet("processed", "address_book.parquet")
    b = book.set_index(book["neon_hh_id"].fillna("__" + book["name"].astype(str)))

    # -- Neon side: categories in priority order over living, contactable rows -------
    neon = m[m["neon_hh_id"].notna()].copy()
    set_aside = neon[neon["deceased"].fillna(False) | neon["do_not_contact"].fillna(False)]
    alive = neon[~neon.index.isin(set_aside.index)].copy()
    cat: dict[str, int] = {}
    cat[1] = alive["src_appeal_gift"] | (alive["don_appeal_window"].fillna(0) >= 10)
    taken = cat[1].copy()
    cat[2] = ~taken & (alive["don_5yr_total"].fillna(0) >= MIN_DONOR_5YR); taken |= cat[2]
    cat[3] = ~taken & alive["steward"].notna() & (alive["don_5yr_total"].fillna(0) > 0); taken |= cat[3]
    cat[4] = ~taken & alive["src_engaged_nondonor"]; taken |= cat[4]
    cat[5] = ~taken & alive["src_new_accounts"]

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

    # cat 6: silent keep-list rows below every bar, minus exclusions
    silent = alive["src_silent_selected"] & ~(cat[1] | cat[2] | cat[3] | cat[4] | cat[5])
    silent &= ~alive["household_name"].map(lambda n: _norm(n) in LAPSED_EXCLUDE)

    rows = []
    for k in (1, 2, 3, 4, 5):
        for r in alive[cat[k]].itertuples(index=False):
            rows.append(_neon_row(r, b, k))
    for r in band_hit.itertuples(index=False):
        rows.append(_band_row(r, b))
    for r in alive[silent].itertuples(index=False):
        rows.append(_neon_row(r, b, 6))

    # -- not-in-Neon side ------------------------------------------------------------
    solo = book[~book["in_neon"]]
    fst = solo[solo["fst_rule_b"].eq("kept") & solo["address"].notna()]
    for r in fst.itertuples(index=False):
        rows.append(
            {
                "mailing_name": _label_name(r.name), "address": r.address, "city": r.city,
                "state": r.state_province, "zip": r.zip_code,
                "category": CATEGORY_LABELS[7],
                "email": r.research_email, "phone": r.research_phone, "steward": None,
                "notes": f"FST {r.fst_best_tier} {r.fst_years}; addr {r.address_source}",
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
                "mailing_name": _label_name(r.name), "address": r.address, "city": r.city,
                "state": r.state_province, "zip": r.zip_code,
                "category": CATEGORY_LABELS[8],
                "email": r.research_email, "phone": r.research_phone, "steward": None,
                "notes": note,
                "in_neon": False, "do_not_contact": bool(r.do_not_contact) if pd.notna(r.do_not_contact) else None,
                "deceased": bool(r.deceased),
            }
        )

    board = pd.DataFrame(rows)
    n_built = len(board)
    board = _tidy(board[board["address"].notna()])  # every row must be mailable
    board["__key"] = board["mailing_name"].map(_sort_key)
    board = board.sort_values("__key").drop(columns="__key").reset_index(drop=True)
    board.insert(0, "id", range(1, len(board) + 1))
    board.attrs["qa"] = {
        "set_aside_deceased_dnc": len(set_aside),
        "band_unmatched": int(band["neon_hh_id"].isna().sum()),
        "mfs_folded": len(MFS_FOLD_INTO_NEON),
        "dropped_no_address": n_built - len(board),
    }
    return board


def _neon_row(r, book_indexed: pd.DataFrame, k: int) -> dict:
    bk = book_indexed.loc[str(r.neon_hh_id)]
    notes = []
    if bool(bk["address_conflict"]):
        notes.append("address conflict - sources disagree")
    if isinstance(bk["web_note"], str) and bk["web_note"]:
        notes.append(str(bk["web_note"])[:80])
    return {
        "mailing_name": _label_name(r.household_name),
        "address": bk["address"], "city": bk["city"], "state": bk["state_province"],
        "zip": bk["zip_code"], "category": CATEGORY_LABELS[k],
        "email": bk["email"], "phone": bk["phone"], "steward": r.steward,
        "notes": "; ".join(notes) or None,
        "in_neon": True, "do_not_contact": bool(bk["do_not_contact"]),
        "deceased": bool(bk["deceased"]),
    }


def _band_row(r, book_indexed: pd.DataFrame) -> dict:
    bk = book_indexed.loc[str(r.neon_hh_id)]
    return {
        "mailing_name": _label_name(r.household_name),
        "address": bk["address"], "city": bk["city"], "state": bk["state_province"],
        "zip": bk["zip_code"], "category": CATEGORY_LABELS[5],
        "email": bk["email"], "phone": bk["phone"], "steward": None,
        "notes": "new account, $50-99 lifetime registrations",
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
        CATEGORY_LABELS[7]: "Fort Salem sponsor, not in Neon, address found (2 are business addresses: Bitar, Bulford)",
        CATEGORY_LABELS[8]: "Music from Salem donor, not in Neon, address on the MfS list",
    }
    super_label = ""
    for k in sorted(CATEGORY_LABELS):
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
        "(board add, Kelvin steward) await address research and join a later cut.*",
        "",
    ]
    # individuals, listed per category below the table - only for categories small
    # enough that a full roster is itself useful (Don, 2026-09-11)
    for k in sorted(CATEGORY_LABELS):
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
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        board[BOARD_COLUMNS].to_excel(xw, sheet_name="board", index=False)
        board[PRINTER_COLUMNS].to_excel(xw, sheet_name="printer", index=False)
        for sheet in xw.sheets.values():
            sheet.freeze_panes = "A2"
            for cell in sheet[1]:
                cell.font = Font(bold=True)
    md_path.write_text(_md(board))
    print(board["category"].value_counts().to_string())
    print(f"\n{len(board)} households -> {xlsx.name}, {md_path.name}")
    print(f"board sheet leftmost, then printer; sorted by surname; ids 1..{len(board)}")


if __name__ == "__main__":
    main()
