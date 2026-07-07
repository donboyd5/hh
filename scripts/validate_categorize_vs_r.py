"""Validate the Python event categorizer against the R project's events.rds.

Reads ``R_hhfrc/data-raw/rds/events.rds`` (R's already-categorized events), recomputes the major
category with ``hh.categorize.assign_major``, and reports the agreement rate plus any mismatches.

This is the R cross-check from the plan: it confirms the categorizer port is faithful on real
Hubbard Hall data (not just synthetic tests). Event names are public performance/class titles, so
they are safe to print for debugging.
"""
from __future__ import annotations

import pandas as pd
import pyreadr

from hh import config
from hh.categorize import assign_major


def main() -> None:
    rds = config.project_root() / "R_hhfrc" / "data-raw" / "rds" / "events.rds"
    df = list(pyreadr.read_r(str(rds)).values())[0]
    n = len(df)

    py_major = [
        assign_major(category, name)
        for category, name in zip(df["category"], df["event_name"], strict=True)
    ]
    r_major = df["event_majorcat"].astype(str).tolist()

    matches = sum(p == r for p, r in zip(py_major, r_major, strict=True))
    print(f"events: {n}")
    print(f"major agreement: {matches}/{n} ({100 * matches / n:.2f}%)")
    print("Python major counts:", pd.Series(py_major).value_counts().to_dict())
    print("R       major counts:", pd.Series(r_major).value_counts().to_dict())

    mismatches = [
        (category, name, r, p)
        for category, name, r, p in zip(
            df["category"], df["event_name"], r_major, py_major, strict=True
        )
        if r != p
    ]
    print(f"\nmismatches: {len(mismatches)}")
    for category, name, r, p in mismatches[:30]:
        print(f"  cat={category!r} name={name!r} | R={r} py={p}")


if __name__ == "__main__":
    main()
