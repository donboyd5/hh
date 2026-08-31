"""Real-data checks against the local Neon pull (gitignored, PII; tests skip without it).

The original version of this file compared our categories to the legacy R output
(``R_hhfrc/data-raw/rds/events.rds``) — that proved the 2026-08 port was faithful. Since
2026-08-31 the major categorization is Hubbard Hall's own scheme
(:mod:`hh.categorize.major`) and intentionally diverges from R in three documented ways:
Bollywood-dance and fencing categories (ERROR under R), film screenings (performance
instead of community), and youth-program showcases under any performance category (R's
exception lists only ran inside specific categories). The R comparison was retired
accordingly. What still matters on real data: **every event must categorize** — ``ERROR``
is a tripwire for genuinely new event types, not a resting place, so this test fails the
moment Neon grows a category or naming pattern we do not know.
"""
from __future__ import annotations

import glob
import re

import pandas as pd
import pytest

from hh import config
from hh.categorize import assign_major

_PULL = sorted(glob.glob(str(config.project_root() / "data" / "00_raw" / "neon" / "*" / "events.jsonl")))
# names that may legitimately fail: test/staff records, not real programming
_JUNK_NAME = re.compile(r"\btest\b", re.I)


@pytest.mark.skipif(not _PULL, reason="no Neon pull present locally")
def test_every_event_in_latest_pull_categorizes():
    df = pd.read_json(_PULL[-1], lines=True).rename(
        columns={"Event Category Name": "category", "Event Name": "event_name"}
    )
    errors = [
        (c, n, assign_major(c, n))
        for c, n in zip(df["category"], df["event_name"], strict=True)
        if assign_major(c, n) == "ERROR" and not _JUNK_NAME.search(str(n))
    ]
    assert not errors, f"{len(errors)} uncategorized events; first: {errors[0]}"
