"""Judy's live campaign tracker: who has given so far this season.

Judy records each household's current-season giving in a Drive xlsx (Don's
"Master List - choosing_board_stewards_final_prep-V2.xlsx"; a copy of the mailing-list board
sheet she keeps up to date). We read a downloaded copy saved as
``data/30_external/campaign-tracker_YYYY-MM-DD.xlsx``.

Layout of the ``full_prep`` tab, as found 2026-11-17:

- row 1 holds running totals, row 2 the headers (located by searching for ``mailing_name``
  so an extra title row does not break the read);
- one row per mailing-list household, keyed by ``neon_hh_id`` (our household rollup id);
- the season column ("Donations Oct 1st, 2026 to Jan 31, 2027") is ONE cumulative amount per
  household - no dates, so it cannot be split by month;
- below the list, an "Added" block of donors who are not on the mailing list (no Neon id - match
  by name), then summary rows ("Board Donations", "Prior to AF", "Matches Goal Meter");
- **board members' gifts are lumped into the single "Board Donations" row**, so a board
  member's own row is blank whether or not they have given;
- amounts can include gifts announced but not yet received (cell comments such as
  "Fidelity Trust DAF due 11-18-26").

Cell comments are real notes (gift details, returned mail, thank-yous sent) and are kept.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from .ids import coerce_id
from .mailing import norm_name

TRACKER_TAB = "full_prep"
SEASON_PREFIX = "Donations "  # "Donations Oct 1st, 2026 to Jan 31, 2027"
BOARD_LUMP_LABEL = "Board Donations"

# openpyxl renders threaded comments as "======\nID#<id>\nAuthor (time)\ntext" with
# "------\nID#<id>" between replies. The separators must go: a cell whose text starts with "="
# is written to xlsx as a formula, and Excel then shows it blank (bit us 2026-11-17).
_COMMENT_SEPARATOR = re.compile(r"[=-]{3,}\s*ID#\S+")


def clean_comment(text: str | None) -> str | None:
    """One-line comment thread: separators and ids dropped, author/time/text kept."""
    if not text:
        return None
    parts = [p.strip() for p in _COMMENT_SEPARATOR.split(text) if p.strip()]
    out = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return out or None


def _header_row(ws, *, search_rows: int = 10) -> int:
    for r in range(1, search_rows + 1):
        if any(c.value == "mailing_name" for c in ws[r]):
            return r
    raise ValueError(f"no 'mailing_name' header in the first {search_rows} rows of {ws.title!r}")


def load_tracker(path: Path | str, *, tab: str = TRACKER_TAB) -> tuple[pd.DataFrame, float]:
    """Read the tracker tab.

    Returns ``(people, board_lump)``. ``people`` has one row per named row in the tab:
    ``neon_hh_id`` (str or NA), ``mailing_name``, ``name_key`` (normalized name), ``steward``,
    ``season_amount`` (float, NaN when blank), ``comments`` (all cell comments on the row).
    ``board_lump`` is the amount on the "Board Donations" row (0 if absent).
    """
    # data_only: Judy types some amounts as formulas ("=100+1000"); read the saved values.
    # (Comments still load in this mode.)
    wb = load_workbook(path, data_only=True)
    ws = wb[tab]
    hdr = _header_row(ws)
    headers = [c.value for c in ws[hdr]]
    season_cols = [h for h in headers if isinstance(h, str) and h.startswith(SEASON_PREFIX)]
    if len(season_cols) != 1:
        raise ValueError(f"expected one '{SEASON_PREFIX}...' column, found {season_cols}")
    col = {h: i for i, h in enumerate(headers) if h is not None}

    rows, board_lump = [], 0.0
    for r in range(hdr + 1, ws.max_row + 1):
        cells = ws[r]

        def val(name, cells=cells):
            return cells[col[name]].value if name in col else None

        steward, amount = val("steward"), val(season_cols[0])
        if isinstance(steward, str) and steward.strip() == BOARD_LUMP_LABEL:
            board_lump += float(amount or 0)
        name = val("mailing_name")
        if name is None or str(name).strip() == "":
            continue
        notes = [clean_comment(c.comment.text) for c in cells if c.comment is not None]
        rows.append({
            "neon_hh_id": val("neon_hh_id"),
            "mailing_name": str(name).strip(),
            "steward": steward,
            "season_amount": float(amount) if isinstance(amount, (int, float)) else float("nan"),
            "comments": " // ".join(n for n in notes if n) or None,
        })
    people = pd.DataFrame(rows, columns=["neon_hh_id", "mailing_name", "steward",
                                         "season_amount", "comments"])
    people["neon_hh_id"] = coerce_id(people["neon_hh_id"])
    people.insert(2, "name_key", norm_name(people["mailing_name"]))
    return people, board_lump
