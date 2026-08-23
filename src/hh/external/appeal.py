"""FY26 fall-appeal mailing list (``Fall Appeal 2025 L With Donations.xlsx``).

Three sheets make up the mailing list: ``top`` (top prospects, with an appeal segment),
``gen`` (the general list), and ``theater`` (a tailored letter to theater artists). The sheets
carry Neon ids in ``accountid`` / ``hhid`` — the join into Neon — plus a staff-maintained
``Annual Appeal Donation`` column recording what each recipient gave during the appeal.

Known quirks, all handled here: trailing subtotal rows (nameless, id-less) and a ``Total`` row;
a literal ``'Not on List'`` placeholder; fully blank rows; five exact duplicate rows; a few
real donors with no Neon id at all (kept and flagged); staff notes typed into headerless
columns to the right of the gift column; and a duplicated ``who to personalize`` header that
pandas mangles to ``.1``.

The workbook's column-A ``id`` is *not* the Neon household id (it is legacy numbering that
matches ``hhid`` only by coincidence on the ``gen`` sheet) — never join on it; use
``accountid``.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .. import config
from .ids import coerce_id

APPEAL_FILENAME = "Fall Appeal 2025 L With Donations.xlsx"

# workbook sheet name -> short alias used in source_sheet
SHEET_ALIASES = {
    "top for segments and personaliz": "top",
    "gen appeal": "gen",
    "theater appeal to artists": "theater",
}

# canonical column -> header name in each sheet (missing key = column absent on that sheet)
_SHEET_COLUMNS = {
    "top": {
        "account_id": "accountid",
        "workbook_hhid": "hhid",
        "workbook_name": "name",
        "group": "group",
        "appeal_segment_raw": "appeal segment",
        "appeal_gift_recorded": "Annual Appeal Donation",
    },
    "gen": {
        "account_id": "accountid",
        "workbook_hhid": "hhid",
        "workbook_name": "name",
        "group": "group",
        "appeal_gift_recorded": "Annual Appeal Donation",
    },
    "theater": {
        "account_id": "Account ID",
        "workbook_name": "Household Name/Account Name",
        "appeal_gift_recorded": "Annual Appeal Donation",
    },
}

_PLACEHOLDER_NAMES = {"total", "not on list"}

# output column order for clean_appeal_recipients
OUTPUT_COLUMNS = [
    "source_sheet",
    "excel_row",
    "account_id",
    "workbook_hhid",
    "workbook_name",
    "group",
    "appeal_segment",
    "appeal_gift_recorded",
    "staff_notes",
    "missing_account_id",
]


def appeal_path() -> Path:
    """Default location of the appeal workbook under the external data layer."""
    return config.layer_dir("external") / APPEAL_FILENAME


def load_appeal_sheets(path: Path | None = None) -> dict[str, pd.DataFrame]:
    """Read all appeal sheets as ``{alias: raw DataFrame}`` (exact filename; never a glob)."""
    src = Path(path) if path is not None else appeal_path()
    book = pd.read_excel(src, sheet_name=None)  # every sheet, in workbook order
    missing = set(SHEET_ALIASES) - set(book)
    if missing:
        raise ValueError(
            f"{src.name} is missing expected sheet(s) {sorted(missing)}; "
            f"found {list(book)}"
        )
    return {SHEET_ALIASES[name]: df for name, df in book.items() if name in SHEET_ALIASES}


def _notes_column(df: pd.DataFrame, gift_col: str) -> pd.DataFrame:
    """Staff notes live in headerless columns to the right of the gift column."""
    after = [c for c in df.columns[df.columns.get_loc(gift_col) + 1 :]]
    if not after:
        return pd.Series(pd.NA, index=df.index, dtype="string")
    notes = df[after].apply(
        lambda row: "; ".join(str(v) for v in row if pd.notna(v)), axis=1
    )
    return notes.mask(notes == "").astype("string")


def _clean_sheet(df: pd.DataFrame, alias: str) -> pd.DataFrame:
    """Apply one sheet's column picks and row cleaning; keep the workbook row number."""
    picks = _SHEET_COLUMNS[alias]
    out = pd.DataFrame(index=df.index)
    all_canonical = {c for p in _SHEET_COLUMNS.values() for c in p}
    for canonical in all_canonical:
        header = picks.get(canonical)
        out[canonical] = (
            df[header] if header is not None and header in df.columns else pd.NA
        )

    gift_col = picks["appeal_gift_recorded"]
    out["staff_notes"] = _notes_column(df, gift_col) if gift_col in df.columns else pd.NA

    # workbook row number (header is Excel row 1) so any kept row can be traced to the file
    out["excel_row"] = np.arange(len(out)) + 2
    out["source_sheet"] = alias

    # row cleaning — drop junk from the bottom of each sheet, then real duplicates
    keep = out["workbook_name"].notna() | out["account_id"].notna()
    out = out[keep]
    named = out["workbook_name"].astype("string").str.strip().str.lower()
    out = out[~named.isin(_PLACEHOLDER_NAMES)]
    out = out.drop_duplicates(
        subset=["source_sheet", "account_id", "workbook_hhid", "workbook_name"], keep="first"
    )

    # types and derived fields
    out["account_id"] = coerce_id(out["account_id"])
    out["workbook_hhid"] = coerce_id(out["workbook_hhid"])
    out["appeal_gift_recorded"] = pd.to_numeric(out["appeal_gift_recorded"], errors="coerce")
    if "appeal_segment_raw" in out.columns:
        segment = out["appeal_segment_raw"].astype("string").str.strip()
    else:
        segment = pd.Series(pd.NA, index=out.index, dtype="string")
    if alias == "gen":
        segment = pd.Series("general", index=out.index, dtype="string")
    elif alias == "theater":
        segment = pd.Series("theater-artists", index=out.index, dtype="string")
    out["appeal_segment"] = segment
    out["missing_account_id"] = out["account_id"].isna()

    return out[OUTPUT_COLUMNS].reset_index(drop=True)


def clean_appeal_recipients(
    sheets: dict[str, pd.DataFrame] | None = None, *, path: Path | None = None
) -> pd.DataFrame:
    """Cleaned appeal recipients from all three sheets: one row per kept workbook row."""
    if sheets is None:
        sheets = load_appeal_sheets(path)
    return pd.concat(
        [_clean_sheet(df, alias) for alias, df in sheets.items() if alias in _SHEET_COLUMNS],
        ignore_index=True,
    )


def appeal_load_qa(
    sheets: dict[str, pd.DataFrame], recipients: pd.DataFrame
) -> dict:
    """Counting guards on the appeal load: what was read, dropped, and kept, per sheet.

    Recomputed from the raw sheets (pure), so it can be asserted against the cleaning without
    threading counters through :func:`clean_appeal_recipients`.
    """
    qa: dict = {"rows_read": {a: len(df) for a, df in sheets.items()}}
    dropped: dict[str, int] = {}
    dups: dict[str, int] = {}
    for alias, df in sheets.items():
        picks = _SHEET_COLUMNS[alias]
        name = df[picks["workbook_name"]] if picks["workbook_name"] in df else pd.Series()
        acct = df[picks["account_id"]] if picks["account_id"] in df else pd.Series()
        named = name.astype("string").str.strip().str.lower()
        dropped[alias] = int(
            ((name.notna() | acct.notna()) == False).sum()  # noqa: E712 — blank/junk rows
            + named.isin(_PLACEHOLDER_NAMES).sum()
        )
        after_junk = df[(name.notna() | acct.notna()) & ~named.isin(_PLACEHOLDER_NAMES)]
        keep_cols = [picks["workbook_name"], picks["account_id"]]
        dups[alias] = int(after_junk.duplicated(subset=keep_cols).sum())
    qa["rows_dropped"] = dropped
    qa["duplicate_rows"] = dups
    qa["rows_kept"] = recipients.groupby("source_sheet").size().to_dict()
    qa["missing_account_id"] = int(recipients["missing_account_id"].sum())
    qa["missing_id_with_recorded_gift"] = int(
        (recipients["missing_account_id"] & recipients["appeal_gift_recorded"].notna()).sum()
    )
    qa["unique_account_ids"] = int(recipients["account_id"].nunique())
    qa["recorded_gift_total"] = float(recipients["appeal_gift_recorded"].sum())
    qa["rows_with_staff_notes"] = int(recipients["staff_notes"].notna().sum())
    return qa
