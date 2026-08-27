"""Harvest Don's Y/N marks from a saved mailing-list workbook into fst-confirmations.yaml.

Usage:
    python scripts/harvest_fst_confirmations.py [path/to/hh-mailing-list_djb.xlsx]

Default: data/20_processed/hh-mailing-list_djb.xlsx (where Excel's Save-As lands), else
data/30_external/hh-mailing-list_djb.xlsx. Run this once after marking; then
scripts/export_mailing_list.py applies the decisions. Re-running is safe: the YAML is
pair-keyed and only changed decisions are replaced (and printed).
"""
from __future__ import annotations

import sys
from pathlib import Path

from hh import config
from hh.external.fst_confirmations import (
    load_confirmations,
    merge_decisions,
    read_review_marks,
    write_confirmations,
)
from hh.external.provenance import append_external_manifest, external_source_entry

CANDIDATES = [
    config.layer_dir("processed") / "hh-mailing-list_djb.xlsx",
    config.layer_dir("external") / "hh-mailing-list_djb.xlsx",
]


def main() -> None:
    if len(sys.argv) > 1:
        workbook = Path(sys.argv[1])
    else:
        workbook = next((p for p in CANDIDATES if p.exists()), None)
    if workbook is None or not workbook.exists():
        sys.exit("no marked workbook found; pass its path")
    marks = read_review_marks(workbook)
    decisions, changes = merge_decisions(load_confirmations(), marks)
    dest = write_confirmations(decisions)
    append_external_manifest(
        external_source_entry(workbook, "Don's marked fst-candidates review sheet"),
        slug="fst-confirmations",
    )
    print(f"harvested {len(marks)} marked rows from {workbook.name} -> {dest}")
    print(f"decisions on file: {len(decisions)} "
          f"(Y={int((decisions['confirm'] == 'Y').sum())}, N={int((decisions['confirm'] == 'N').sum())})")
    for c in changes:
        print("  changed:", c)


if __name__ == "__main__":
    main()
