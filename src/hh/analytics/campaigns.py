"""The annual (fall) fund drive by year: window vs total-coded giving.

Neon codes gifts to an ``Annual Fund Drive - YYYY-YYYY`` campaign for every drive back to
FY12, which makes two distinct measures possible and worth keeping apart:

- **window** — gifts dated October 1 through January 31 of the drive's fiscal year: the
  four months after the fall letter mails; the mailed-appeal performance measure.
- **total** — everything ever coded to the drive's campaign, whenever it arrived: the
  revenue measure. The gap is mostly a single recurring five-figure gift that lands just
  after the window closes in most years, plus gifts coded to the campaign label in later
  months.

Basis is the clean-gift filter (SUCCEEDED ``DONATION``/``PLEDGEPAYMENT``, ``Individual``
accounts); business gifts coded to a drive (~$21k across all years) are excluded. The
fall-2025 drive's in-window figures reconcile with the appeal-response chapter.
"""
from __future__ import annotations

import re

import pandas as pd

_DRIVE_LABEL = re.compile(r"Annual Fund Drive - (\d{4})-(\d{4})")


def _clean_gifts(donations: pd.DataFrame) -> pd.DataFrame:
    return donations[
        donations["donation_status"].astype(str).eq("SUCCEEDED")
        & donations["donation_type"].isin(["DONATION", "PLEDGEPAYMENT"])
        & donations["account_type"].astype(str).eq("Individual")
    ]


def annual_drive_by_year(donations: pd.DataFrame) -> pd.DataFrame:
    """One row per annual-fund drive: window vs total-coded giving.

    ``drive`` is the fiscal year the drive belongs to (the label's ending year —
    ``Annual Fund Drive - 2025-2026`` -> 2026, the fall-2025 mailing). Columns:
    gifts, households, oct_jan / later / total dollars, and the median and largest
    in-window gift.
    """
    g = _clean_gifts(donations)
    afd = g[g["campaign"].astype("string").str.contains("Annual Fund Drive", na=False)].copy()
    labels = afd["campaign"].str.extract(_DRIVE_LABEL.pattern)
    afd["drive"] = labels[1].astype(float)  # ending year
    afd = afd[afd["drive"].notna()]
    afd["drive"] = afd["drive"].astype(int)
    afd["in_window"] = afd["donation_date"].between(
        pd.to_datetime((afd["drive"] - 1).astype(str) + "-10-01"),
        pd.to_datetime(afd["drive"].astype(str) + "-01-31"),
    )

    rows = []
    for drive, d in afd.groupby("drive"):
        win = d.loc[d["in_window"], "donation_amount"]
        rows.append(
            {
                "drive": drive,
                "gifts": len(d),
                "households": d["id"].nunique(),
                "oct_jan": win.sum(),
                "later": d.loc[~d["in_window"], "donation_amount"].sum(),
                "total": d["donation_amount"].sum(),
                "median_window_gift": win.median() if len(win) else float("nan"),
                "top_window_gift": win.max() if len(win) else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values("drive").set_index("drive")
