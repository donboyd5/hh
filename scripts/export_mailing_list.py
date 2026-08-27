"""Build and export the potential-donor mailing list (local-only, PII).

Reads the latest Neon pull (offline; no API needed), the processed registration table, and
the external workbooks, then writes:

  data/20_processed/mailing_list.parquet
  data/20_processed/hh-mailing-list.xlsx   (mailing-list sheet + about sheet)

Everything names real people: the outputs stay under gitignored ``data/`` and must never be
published or committed. Rerun after ``scripts/pull.py`` + ``scripts/build.py`` and after any
edit to the external workbooks — the build is deterministic given the same inputs.

Usage:
    python scripts/export_mailing_list.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from hh import config, io
from hh.analytics.fst_match import fuzzy_fst_candidates
from hh.analytics.mailing import build_mailing_list
from hh.clean.accounts import clean_accounts
from hh.clean.donations import clean_donations
from hh.external import fortsalem as fst
from hh.external import mailing as ml
from hh.external.mailing import match_households
from hh.external.notes import load_boyd_notes
from hh.external.provenance import append_external_manifest, external_source_entry

XLSX_FILENAME = "hh-mailing-list.xlsx"

# Hand-maintained aliases for workbook names that no longer match Neon exactly (Neon
# household names get edited between pulls; the workbooks age). Keyed by the workbook's
# name -> rollup id. Add entries when the UNMATCHED list in the export output names a
# household you know is in Neon under a different name.
HOUSEHOLD_ALIASES = {
    # Neon renamed this household between the 2026-07-07 and 2026-08-27 pulls
    # (account 39722, household 1684); Don's silent-1000plus note must still attach
    "Tim Smith & Elizabeth Straiton": "1684",
}


def _matched(frame: pd.DataFrame, households: pd.DataFrame) -> pd.DataFrame:
    """A household_name-keyed external frame with the matched rollup ``id`` attached.

    Uses the city tiebreak when the frame carries a city (Judy's exports do), then the
    hand-maintained aliases for anything still unmatched.
    """
    cities = frame["city"] if "city" in frame.columns else None
    matched = match_households(frame["household_name"], households, cities=cities)
    ids = list(matched["id"].values)
    how = list(matched["match"].values)
    for i, name in enumerate(frame["household_name"]):
        if pd.isna(ids[i]) and str(name).strip() in HOUSEHOLD_ALIASES:
            ids[i] = HOUSEHOLD_ALIASES[str(name).strip()]
            how[i] = "alias"
    return frame.assign(id=ids, match=how)


def main() -> None:
    # processed tables carry the geocode/distance and event-category enrichment (build.py);
    # donations are re-cleaned from the latest pull since no processed donations table exists
    accounts = io.read_parquet("processed", "accounts_geocoded.parquet")
    donations = clean_donations(accounts=clean_accounts())
    registrations = io.read_parquet("processed", "registrations_enriched.parquet")
    households = accounts.drop_duplicates(subset=["id"])[["id", "name", "city"]]

    donor3 = _matched(ml.load_donor3(), households)
    # only new accounts with >= $100 lifetime registrations (Judy's column) qualify
    new_accounts_all = ml.load_new_accounts()
    new_accounts = _matched(ml.qualifying_new_accounts(new_accounts_all), households)
    djb = ml.load_djb_workbook()
    silent_selected = _matched(djb["silent_selected"], households)
    appeal_responded = _matched(djb["appeal_responded"], households)

    # Fort Salem: individuals only (the spec excludes orgs and anonymous listings)
    sponsors = fst.load_fst_sponsors()
    fst_summary = fst.summarize_sponsors(sponsors)
    fst_summary = fst_summary[~fst_summary["anonymous"] & ~fst_summary["org"]]
    fst_match = match_households(fst_summary["name"], households)
    fst_summary = fst_summary.assign(
        id=fst_match["id"].values,
        in_neon=fst_match["match"].isin(["name+city", "name"]),
    )

    table = build_mailing_list(
        accounts,
        donations,
        registrations,
        donor3=donor3,
        new_accounts=new_accounts,
        silent_selected=silent_selected,
        appeal_responded=appeal_responded,
        fst_summary=fst_summary,
        boyd_notes=load_boyd_notes(),
    )

    # Fort Salem fuzzy candidates for Don to confirm (review sheet; never auto-merged)
    fst_review = fuzzy_fst_candidates(fst_summary, accounts)
    fst_review.insert(0, "confirm", "")  # Don marks Y / N

    io.write_parquet(table, "processed", "mailing_list.parquet")
    io.write_parquet(fst_review, "processed", "fst_candidates.parquet")
    with pd.ExcelWriter(config.layer_dir("processed") / XLSX_FILENAME, engine="openpyxl") as xw:
        table.to_excel(xw, sheet_name="mailing-list", index=False)
        fst_review.to_excel(xw, sheet_name="fst-candidates", index=False)
        pd.DataFrame(
            {
                "item": [
                    "rows", "in_neon", "needs_review (Fort Salem, not in Neon)",
                    "src_donor_5yr", "src_donor3", "src_new_accounts",
                    "src_silent_selected", "src_appeal_responded",
                    "src_appeal_gift (>= $10 in Oct 2025-Jan 2026)", "fst flagged",
                    "do_not_contact", "deceased",
                ],
                "detail": [
                    len(table),
                    int(table["in_neon"].sum()),
                    int(table["needs_review"].sum()),
                    int(table["src_donor_5yr"].sum()),
                    int(table["src_donor3"].sum()),
                    int(table["src_new_accounts"].sum()),
                    int(table["src_silent_selected"].sum()),
                    int(table["src_appeal_responded"].sum()),
                    int(table["src_appeal_gift"].sum()),
                    int(table["fst"].sum()),
                    int(table["do_not_contact"].fillna(False).sum()),
                    int(table["deceased"].fillna(False).sum()),
                ],
            }
        ).to_excel(xw, sheet_name="about", index=False)

    # provenance: one entry per distinct file version of each hand-maintained source
    for filename, note in [
        (ml.DONOR3_FILENAME, "Judy's FY24-FY26 donor export with Don's Ambassador/notes"),
        (ml.NEW_ACCOUNTS_FILENAME, "Judy's FY25-26 new-accounts export for AF mailing"),
        (
            ml.DJB_WORKBOOK_FILENAME,
            "Don's edited donor workbook (bold silent-1000plus, action notes)",
        ),
    ]:
        path: Path = config.layer_dir("external") / filename
        if path.exists():
            append_external_manifest(external_source_entry(path, note), slug="mailing-list")

    unmatched = {
        source: frame.loc[frame["id"].isna(), "household_name"].tolist()
        for source, frame in [
            ("donor3", donor3),
            ("new_accounts", new_accounts),
            ("silent_selected", silent_selected),
            ("appeal_responded", appeal_responded),
        ]
    }
    qa = table.attrs.get("exclusion_qa", {})
    print(
        f"new accounts: {len(new_accounts)} of {len(new_accounts_all)} clear "
        f"${ml.MIN_NEW_ACCOUNT_REGISTRATION:.0f} in lifetime registrations"
    )
    strong = int(((fst_review["rank"] == 1) & (fst_review["score"] >= 92)).sum())
    print(
        f"fst candidates: {fst_review['fst_name'].nunique()} Fort Salem names have a close "
        f"Neon candidate ({strong} at score 92+); "
        f"{int(table['fst_candidate_id'].notna().sum())} auto-filled on the main sheet"
    )
    print(
        f"mailing list: {len(table)} rows "
        f"({int(table['in_neon'].sum())} in Neon, {int(table['needs_review'].sum())} FST new)"
    )
    print(
        f"exclusions: {len(qa.get('dropped_deceased_neon', []))} deceased (Neon flag), "
        f"{len(qa.get('dropped_deceased_note', []))} deceased (notes), "
        f"{len(qa.get('dropped_small_donor', []))} rows under $200 not keep-identified"
    )
    for label in ("dropped_deceased_note", "kept_deceased_note_survivor"):
        names = qa.get(label, [])
        if names:
            print(f"  {label}: {names}")
    for source, names in unmatched.items():
        if names:
            print(f"  UNMATCHED {source} ({len(names)}): {names[:8]}")
    print(f"saved: data/20_processed/mailing_list.parquet and {XLSX_FILENAME}")


if __name__ == "__main__":
    main()
