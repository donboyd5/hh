"""Household rollup: the canonical id/name/group pattern ported from R.

Every analytic table rolls a constituent up to its household when possible:

    id    = household_id if present, else account_id
    group = 'household' | 'account' | 'other'
    name  = first non-empty of (household_name, full_name, company_name, ...)

Mirrors R: ``id = ifelse(is.na(household_id), account_id, household_id)`` and the analogous
case_when for group/name.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_NAME_COLS = ("household_name", "full_name", "company_name", "account_name")


def coalesce(*series: pd.Series) -> pd.Series:
    """First non-null value across series, left to right."""
    out: pd.Series | None = None
    for s in series:
        out = s if out is None else out.where(out.notna(), s)
    return out


def add_rollup(
    df: pd.DataFrame,
    *,
    household_id: str = "household_id",
    account_id: str = "account_id",
    name_cols: tuple[str, ...] = DEFAULT_NAME_COLS,
) -> pd.DataFrame:
    """Return a copy of df with id, name, and group added (R household-rollup convention)."""
    out = df.copy()

    def col_or_na(name: str) -> pd.Series:
        if name in out.columns:
            return out[name]
        return pd.Series([pd.NA] * len(out), index=out.index)

    hid = col_or_na(household_id)
    aid = col_or_na(account_id)
    out["id"] = hid.where(hid.notna(), aid)
    out["group"] = np.where(
        hid.notna(), "household", np.where(aid.notna(), "account", "other")
    )
    available = [out[c] for c in name_cols if c in out.columns]
    if available:
        out["name"] = coalesce(*available)
    else:
        out["name"] = pd.Series([pd.NA] * len(out), index=out.index)
    return out
