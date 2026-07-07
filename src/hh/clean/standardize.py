"""Column-name standardization: port of R ``vmap()`` plus the fieldmap override mapping.

R's pipeline renamed only the columns listed in its curated lookup (``variable_lookup.rds``). Here
we apply ``vmap`` to *every* unmapped column for consistent snake_case names, while honoring
explicit ``{neon_name: standard_name}`` overrides from ``config/fieldmap.yaml``. The important
analytic columns are explicitly mapped in both, so validation against R still aligns.
"""
from __future__ import annotations

import re

import pandas as pd

from .. import config

# "phone " before a digit -> "phone"  (mirrors R's vmap)
_PHONE_BEFORE_DIGIT = re.compile(r"phone (?=\d)")


def vmap(name) -> str:
    """Port of R ``vmap()``: Neon column name -> standardized snake_case name."""
    s = str(name).lower()
    s = s.replace("?", "").replace(".", "").replace("-", "")
    s = s.replace("(c)", "").replace("(f)", "")
    s = _PHONE_BEFORE_DIGIT.sub("phone", s)
    s = s.replace("line ", "line")
    s = re.sub(r"\s*/\s*", "_", s)
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"^_+|_+$", "", s)
    return s


def standardize_columns(df: pd.DataFrame, mapping: dict | None = None) -> pd.DataFrame:
    """Rename columns using explicit mapping first, then ``vmap`` for the rest."""
    if mapping is None:
        mapping = config.load_fieldmap().get("mapping", {})
    rename: dict[str, str] = {}
    for col in df.columns:
        if col in mapping:
            rename[col] = mapping[col]
        else:
            mapped = vmap(col)
            if mapped and mapped != col:
                rename[col] = mapped
    return df.rename(columns=rename)
