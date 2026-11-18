"""Campaign-prospect workbook: last year's donors in a window who haven't given this season.

Takes every gift in a past date window, rolls it up to households, labels each with its
current-season status from Judy's campaign tracker, and DROPS board members and households
her sheet shows have already given. Everyone else stays - including households on her sheet
with no gift yet (the prospects) and donors not on her sheet at all (status unknown, shaded
grey). Logic and status definitions: ``hh.analytics.prospects``; tracker layout:
``hh.external.campaign_tracker``.

Refreshing the tracker: download Judy's Drive xlsx ("Master List - choosing_board_stewards_
final_prep-V2.xlsx") and save it as data/30_external/campaign-tracker_YYYY-MM-DD.xlsx. The
newest such file is used unless --tracker is given; each run records the file's sha256 in
data/manifest/external-campaign-tracker.yaml.

Hand facts that name donors (company gift account -> contact's household; notes such as
"believed moved") live in data/30_external/prospect-crosswalk.yaml, gitignored because this
repo is public. Company gifts missing from it are printed so they can be added.

Output (data/20_processed/, PII, never published):
  prospects_<start>_<end>_<YYYY-MM-DD_HHMM>.xlsx - tabs: combined (one row per household,
  a column per month), one tab per month (partial months labelled, e.g. "Nov 17-30 2025"),
  excluded (dropped households + reason), summary (with a check row), notes.

Usage:
    python scripts/export_prospects.py --start 2025-11-17 --end 2026-01-31
    python scripts/export_prospects.py --start 2025-11-17 --end 2026-01-31 --tracker PATH
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill

from hh import config, io
from hh.analytics import prospects as pr
from hh.clean.accounts import clean_accounts
from hh.clean.donations import clean_donations
from hh.external.campaign_tracker import load_tracker
from hh.external.provenance import append_external_manifest, external_source_entry

GREY = PatternFill("solid", fgColor="EEEEEE")
WIDTHS = {"donor": 40, "gift_dates": 22, "campaigns": 44, "account_type": 13, "status": 18,
          "steward": 11, "account_ids": 16, "neon_note": 30, "reason": 38, "note": 150,
          "group": 46}


def newest_tracker() -> Path:
    files = sorted(config.layer_dir("external").glob("campaign-tracker_*.xlsx"))
    if not files:
        raise FileNotFoundError(
            "no data/30_external/campaign-tracker_*.xlsx - see module docstring")
    return files[-1]


def notes_table(tracker: Path, board_lump: float, start, end, pull: Path) -> pd.DataFrame:
    return pd.DataFrame({"note": [
        f"Window: gifts dated {start:%b %d, %Y} through {end:%b %d, %Y}, from Neon pull "
        f"{pull.name}. SUCCEEDED DONATION/PLEDGEPAYMENT; individuals + companies; canceled "
        "and internal house accounts excluded; rolled up to household.",
        f"Current-season status from {tracker.name} (Judy's tracker, tab full_prep).",
        "Dropped: households with an amount in Judy's season column, and board members "
        f"(their gifts are one lumped 'Board Donations' line, ${board_lump:,.0f}, so no "
        "individual status exists). See the 'excluded' tab.",
        "status 'not yet' = on Judy's sheet, no gift so far this season. 'not on Judy's list' "
        "= not a row in her sheet, so status is unknown (grey rows).",
        "combined tab: company gift accounts fold into their contact's household (hand "
        f"crosswalk, data/30_external/{pr.CROSSWALK_FILE}); month tabs keep them separate.",
        "neon_note: deceased flags from Neon (every household member flagged) and known "
        "facts (e.g. believed moved).",
    ]})


def write_workbook(path: Path, sheets: dict[str, pd.DataFrame]) -> None:
    """House style: bold header, freeze B2, #,##0 money, readable widths."""
    money = {"amount", "total"}
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name, index=False)
            ws = xw.sheets[name]
            ws.freeze_panes = "B2"
            cols = list(df.columns)
            month_cols = {c for c in cols if c[:3] in
                          {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep",
                           "Oct", "Nov", "Dec"}}
            for i, col in enumerate(cols, start=1):
                ws.cell(row=1, column=i).font = Font(bold=True)
                ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = \
                    WIDTHS.get(col, max(10, len(col) + 2))
                if col in money or col in month_cols:
                    for r in range(2, len(df) + 2):
                        ws.cell(row=r, column=i).number_format = "#,##0"
            if "status" in cols:
                j = cols.index("status") + 1
                for r in range(2, len(df) + 2):
                    if ws.cell(row=r, column=j).value == pr.NOT_LISTED:
                        for c in range(1, len(cols) + 1):
                            ws.cell(row=r, column=c).fill = GREY


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--start", required=True, help="first gift date, YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="last gift date (inclusive), YYYY-MM-DD")
    ap.add_argument("--tracker", type=Path, help="Judy's tracker xlsx (default: newest)")
    args = ap.parse_args()
    start, end = pd.Timestamp(args.start), pd.Timestamp(args.end)
    tracker_path = args.tracker or newest_tracker()

    append_external_manifest(
        external_source_entry(tracker_path, "Judy's campaign tracker (Drive xlsx download)"),
        slug="campaign-tracker")
    tracker, board_lump = load_tracker(tracker_path)

    accounts = clean_accounts()
    company_to_hh, notes = pr.load_crosswalk()
    gifts = pr.window_gifts(clean_donations(accounts=accounts), start, end,
                            company_to_hh=company_to_hh)
    gifts["donor"] = pr.label_companies(gifts, accounts)
    gifts = pr.add_status(gifts, tracker, deceased=pr.deceased_households(accounts),
                          notes=notes, company_to_hh=company_to_hh)
    unmapped = gifts.loc[gifts["account_type"].astype(str).eq("Company")
                         & ~gifts["rid"].isin(company_to_hh), "donor"].unique()
    if len(unmapped):
        print("company gift accounts with no crosswalk entry (check "
              f"data/30_external/{pr.CROSSWALK_FILE}):", "; ".join(unmapped))
    tabs = pr.prospect_tables(gifts, start, end)
    summary = pr.summary_table(gifts, tabs)

    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out = config.layer_dir("processed") / f"prospects_{start:%Y-%m-%d}_{end:%Y-%m-%d}_{stamp}.xlsx"
    write_workbook(out, {**tabs, "summary": summary,
                         "notes": notes_table(tracker_path, board_lump, start, end,
                                              io.latest_pull_dir())})
    print(summary.to_string(index=False))
    print(out)


if __name__ == "__main__":
    main()
