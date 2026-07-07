"""Real-data integration test: load the R events CSV, categorize, and compare to R's events.rds.

Runs only when the (gitignored) legacy R data is present locally.
"""
from __future__ import annotations

import pytest

from hh import config

EVENTS_CSV = config.project_root() / "R_hhfrc" / "data-raw" / "neon" / "events_2025-07-20.csv"
EVENTS_RDS = config.project_root() / "R_hhfrc" / "data-raw" / "rds" / "events.rds"


@pytest.mark.skipif(
    not (EVENTS_CSV.exists() and EVENTS_RDS.exists()),
    reason="R events CSV/RDS not present locally",
)
def test_events_csv_pipeline_matches_rds_counts():
    pyreadr = pytest.importorskip("pyreadr")

    from hh.categorize import add_major_minor
    from hh.neon.load_csv import load_neon_csv

    py_df = add_major_minor(load_neon_csv(EVENTS_CSV))
    py_counts = py_df["event_majorcat"].value_counts().to_dict()

    r_df = list(pyreadr.read_r(str(EVENTS_RDS)).values())[0]
    r_counts = r_df["event_majorcat"].astype(str).value_counts().to_dict()

    assert py_counts == r_counts, f"CSV pipeline {py_counts} != R {r_counts}"
