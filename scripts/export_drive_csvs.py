"""Regenerate the Drive-upload CSVs for the mailing-list sheets (local-only, PII).

The Drive backup folder "HH donor list drafts" mirrors the workbook as Google Sheets
(CSV -> Sheets import). Two import quirks the writer works around:
  - Sheets strips leading ZIP zeros on import (05773 renders as 5773), so every zip is
    wrapped as a ="05773" formula - it renders as text but keeps the zero.
  - CSV carries no cell formatting: the xlsx's column widths, #,##0 donation formats and
    bold-yellow review salutations do not travel (xlsx-only).

Writes data/20_processed/drive-csv/{board,printer,dnc,not_in_neon,reception}.csv from
final-mailing-list-draft[suffix].xlsx. Read via openpyxl (not pandas) so zip cells keep
their stored text form - pandas re-parsing invented 4-char zips and ".0" ids.

Usage:
    python scripts/export_drive_csvs.py [suffix]   # suffix as passed to export_donor_list.py
"""
from __future__ import annotations

import csv
import sys

from openpyxl import load_workbook

from hh import config

# xlsx sheet name -> upload file name (matches the titles on Drive: "Final mailing
# list - draft 1 - <board|printer|do_not_contact|not_in_neon|reception_draft>")
SHEETS = {
    "board": "board.csv",
    "printer": "printer.csv",
    "do_not_contact": "dnc.csv",
    "not_in_neon": "not_in_neon.csv",
    "reception_draft": "reception.csv",
}


def _cell(v, header: str) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if header == "zip":
        return f'="{v}"'
    return str(v)


def main() -> None:
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    xlsx = config.layer_dir("processed") / f"final-mailing-list-draft{suffix}.xlsx"
    out_dir = config.layer_dir("processed") / "drive-csv"
    out_dir.mkdir(exist_ok=True)
    wb = load_workbook(xlsx, read_only=True, data_only=True)
    for sheet, filename in SHEETS.items():
        ws = wb[sheet]
        rows = ws.iter_rows(values_only=True)
        header = [str(h) for h in next(rows)]
        out = out_dir / filename
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            n = 0
            for vals in rows:
                w.writerow([_cell(v, h) for v, h in zip(vals, header, strict=True)])
                n += 1
        print(f"{sheet}: {n} rows -> {out}")
    wb.close()


if __name__ == "__main__":
    main()
