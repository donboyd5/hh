"""Real-data integration test: the legacy R events CSV loads and categorizes cleanly.

Runs only when the (gitignored) legacy R data is present locally. Originally this test
asserted the CSV pipeline reproduced R's category counts exactly — that proved the 2026-08
port. Since the 2026-08-31 rewrite the major categorization is our own scheme
(:mod:`hh.categorize.major`) and deliberately differs from R on that same CSV by
+10 class (youth-program showcases under any performance category), +3 performance /
-13 community (film screenings), so exact equality was retired. What still holds: the
CSV loader reads the same events R did, and our scheme categorizes every one of them.
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
def test_events_csv_pipeline_loads_and_categorizes():
    pyreadr = pytest.importorskip("pyreadr")

    from hh.categorize import add_major_minor
    from hh.neon.load_csv import load_neon_csv

    py_df = add_major_minor(load_neon_csv(EVENTS_CSV))
    r_df = list(pyreadr.read_r(str(EVENTS_RDS)).values())[0]

    # the loader reads exactly the events R read
    assert len(py_df) == len(r_df), f"CSV pipeline read {len(py_df)} events, R had {len(r_df)}"

    # and our own scheme categorizes every one of them (ERROR is a tripwire)
    errors = py_df.loc[py_df["event_majorcat"] == "ERROR", "event_name"].tolist()
    assert not errors, f"{len(errors)} uncategorized events; first: {errors[0]}"
