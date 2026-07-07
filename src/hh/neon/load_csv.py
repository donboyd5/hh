"""Load Neon report CSV exports into standardized DataFrames.

This is the ingestion path for the legacy CSV report exports (the same files the R project used).
It exists so the cleaning pipeline can be built and validated against the R outputs *before* the
API key is available. When the key arrives, the API extractor (``hh.neon.extract``) becomes the
primary ingestion path; downstream cleaning is identical because both yield standardized records.

All columns are read as strings, mirroring R's ``col_types = cols(.default = col_character())``.
"""
from __future__ import annotations

import pandas as pd

from ..clean.standardize import standardize_columns


def load_neon_csv(path, *, mapping: dict | None = None, dtype=str) -> pd.DataFrame:
    """Read a Neon report CSV (all strings) and standardize its column names."""
    df = pd.read_csv(path, dtype=dtype)
    return standardize_columns(df, mapping=mapping)
