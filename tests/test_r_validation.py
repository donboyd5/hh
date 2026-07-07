"""Real-data validation against the legacy R outputs (R_hhfrc/data-raw/rds/*.rds).

These tests run only when the (gitignored, PII) R data files are present locally. They recompute
values with the Python pipeline and compare to what R produced, exactly as the plan's "R
cross-check" requires. On a fresh clone without the R data, they skip.
"""
from __future__ import annotations

import pytest

from hh import config
from hh.categorize import assign_major

EVENTS_RDS = config.project_root() / "R_hhfrc" / "data-raw" / "rds" / "events.rds"


@pytest.mark.skipif(not EVENTS_RDS.exists(), reason="R events.rds not present locally")
def test_major_matches_r_on_real_events():
    pyreadr = pytest.importorskip("pyreadr")
    df = list(pyreadr.read_r(str(EVENTS_RDS)).values())[0]
    py_major = [
        assign_major(c, n)
        for c, n in zip(df["category"], df["event_name"], strict=True)
    ]
    r_major = df["event_majorcat"].astype(str).tolist()
    mismatches = [
        (p, r) for p, r in zip(py_major, r_major, strict=True) if p != r
    ]
    assert not mismatches, f"{len(mismatches)} mismatches vs R; first: {mismatches[0]}"
