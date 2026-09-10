"""Build and export the consolidated address book (local-only, PII).

One row per mailable identity across every address-bearing source — everyone in Neon
plus the add-on lists — with every candidate address and one best address chosen by the
precedence in ``meta-docs/address-sources.md`` (Don, 2026-09-10). The book is the
knowledge base to cherry-pick a mailing from; it is not itself a mailing list.

Writes:

  data/20_processed/address_book.parquet
  data/20_processed/address_book_candidates.parquet
  data/20_processed/address_book.xlsx   (address-book, address-candidates, about sheets)

Everything names real people: outputs stay under gitignored ``data/`` and must never be
published or committed. Deterministic given the same inputs; rerun after
``scripts/pull.py`` + ``scripts/build.py``, after ``scripts/research_fst_contacts.py``,
after ``scripts/export_mailing_list.py``, or whenever a received list changes.

Usage:
    python scripts/export_address_book.py
"""
from __future__ import annotations

import pandas as pd
from openpyxl.styles import Font

from hh import config, io
from hh.clean.accounts import clean_accounts
from hh.clean.donations import clean_donations
from hh.external import lists
from hh.external.address_book import build_address_book
from hh.external.fortsalem import fst_vs_neon
from hh.external.notes import load_fst_contact_notes
from hh.external.provenance import append_external_manifest, external_source_entry

XLSX_FILENAME = "address_book.xlsx"
BOOK_PARQUET = "address_book.parquet"
CANDIDATES_PARQUET = "address_book_candidates.parquet"


def _freeze_header(ws) -> None:
    ws.freeze_panes = "A2"
    for cell in ws[1]:
        cell.font = Font(bold=True)


def main() -> None:
    accounts = io.read_parquet("processed", "accounts_geocoded.parquet")
    donations = clean_donations(accounts=clean_accounts())
    mailing_list = io.read_parquet("processed", "mailing_list.parquet")
    hits_path = config.layer_dir("interim") / "fst_contacts.parquet"
    roll_hits = (
        pd.read_parquet(hits_path)
        if hits_path.exists()
        else pd.DataFrame(
            columns=["household_name", "street", "city", "state", "zip", "source",
                     "confidence", "owners"]
        )
    )

    received = {
        "mfs_donor": lists.load_mfs_donors(),
        "friends_to_add": lists.load_friends(),
        "mfs_attendee": lists.load_attendees(),
    }
    book, candidates = build_address_book(
        accounts,
        donations,
        received=received,
        roll_hits=roll_hits,
        contact_notes=load_fst_contact_notes(),
        appeal_ids=lists.load_appeal2025_ids(),
        mailing_list=mailing_list,
        fst_summary=fst_vs_neon(accounts),
    )
    io.write_parquet(book, "processed", BOOK_PARQUET)
    io.write_parquet(candidates, "processed", CANDIDATES_PARQUET)

    about = pd.DataFrame(
        {
            "item": [
                "rows (identities)", "in Neon", "not in Neon",
                "with a best address", "address by source (best)",
                "identities with conflicting sources", "PO-box best address",
                "on the Fall 2025 appeal (mailed_2025)", "in current mailing list",
                "Fort Salem flagged", "FST not in Neon: rule B kept", "FST not in Neon: below bar",
                "MfS donors (list rows)", "Friends to add (rows)", "MfS attendees (names)",
                "deceased (household: all members)", "do-not-contact (any living member)",
                "company accounts excluded",
            ],
            "detail": [
                len(book),
                int(book["in_neon"].sum()),
                int((~book["in_neon"]).sum()),
                int(book["address"].notna().sum()),
                "; ".join(f"{k} {v}" for k, v in book["address_source"].value_counts().items()),
                int(book["address_conflict"].sum()),
                int(book["po_box"].sum()),
                int(book["mailed_2025"].sum()),
                int(book["in_mailing_list"].fillna(False).sum()),
                int(book["fst"].fillna(False).sum()),
                int(book["fst_rule_b"].eq("kept").sum()),
                int(book["fst_rule_b"].eq("below-bar").sum()),
                len(received["mfs_donor"]),
                len(received["friends_to_add"]),
                len(received["mfs_attendee"]),
                int(book["deceased"].fillna(False).sum()),
                int(book["do_not_contact"].fillna(False).sum()),
                book.attrs.get("n_companies_excluded", 0),
            ],
        }
    )
    xlsx_path = config.layer_dir("processed") / XLSX_FILENAME
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as xw:
        book.to_excel(xw, sheet_name="address-book", index=False)
        candidates.to_excel(xw, sheet_name="address-candidates", index=False)
        about.to_excel(xw, sheet_name="about", index=False)
        for sheet in xw.sheets.values():
            _freeze_header(sheet)

    # provenance: a manifest entry per received file, so a swapped revision leaves a trail
    for filename, note in [
        (lists.MFS_DONORS_FILENAME, "Music from Salem 2026 donor list (68-name revision with addresses)"),
        (lists.FRIENDS_FILENAME, "Friends-to-add names list"),
        (lists.ATTENDEES_FILENAME, "MfS concert attendees at Hubbard Hall (name fragments)"),
        (lists.APPEAL2025_FILENAME, "Fall 2025 appeal mail file (mailed-last-year flag)"),
    ]:
        for base in (config.layer_dir("raw") / "external", config.layer_dir("external")):
            path = base / filename
            if path.exists():
                append_external_manifest(external_source_entry(path, note), slug="address-book")
                break

    solo = book[~book["in_neon"]]
    print(
        f"address book: {len(book)} identities "
        f"({int(book['in_neon'].sum())} Neon, {len(solo)} not) — "
        f"{int(book['address'].notna().sum())} with a best address"
    )
    print(f"  best-address sources: {dict(book['address_source'].value_counts())}")
    print(
        f"  conflicts: {int(book['address_conflict'].sum())}, PO-box: {int(book['po_box'].sum())}, "
        f"mailed 2025: {int(book['mailed_2025'].sum())}, deceased: "
        f"{int(book['deceased'].fillna(False).sum())}"
    )
    unmatched = solo[solo["possible_neon_match"].isna()]
    print(
        f"  not in Neon: {int(solo['possible_neon_match'].notna().sum())} with a fuzzy Neon "
        f"candidate, {len(unmatched)} with none"
    )
    print(f"saved: {BOOK_PARQUET}, {CANDIDATES_PARQUET}, {XLSX_FILENAME}")


if __name__ == "__main__":
    main()
