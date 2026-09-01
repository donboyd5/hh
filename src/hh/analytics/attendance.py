"""Attendance by fiscal year: true headcount and registration revenue by category.

The one source of truth for the FY × category table used by the attendance chapter and
``meta-docs/attendance.md`` (via ``scripts/attendance_doc.py``). Attendees are people —
each registration's nested ticket records with ``registrationStatus`` SUCCEEDED — not
registration counts (about 1.7 people per registration). Revenue is registration dollars
as recorded (gross; canceled sections keep their refunded amounts). Uncategorized (ERROR)
events are excluded; a real-data test fails the build if any exist.
"""
from __future__ import annotations

import pandas as pd

from ..analytics.mailing import fiscal_year
from ..analytics.productions import count_succeeded_attendees

CATEGORIES = ("classes", "performances_events", "community", "total")


def attendance_by_fy(regs: pd.DataFrame) -> pd.DataFrame:
    """Attendees and registration dollars by fiscal year and category.

    Input is the enriched registrations table; output has one row per fiscal year
    (labeled by ending year) with ``<category>_att`` and ``<category>_rev`` columns,
    where performances_events = performance + other (galas, fundraisers, films).
    """
    r = regs[regs["event_majorcat"].ne("ERROR")].copy()
    r["attendees"] = r["tickets"].apply(count_succeeded_attendees)
    r["fy"] = fiscal_year(r["starts_on"])
    r["cat"] = r["event_majorcat"].map(
        {"class": "classes", "performance": "performances_events",
         "other": "performances_events", "community": "community"}
    )
    att = r.pivot_table(index="fy", columns="cat", values="attendees",
                        aggfunc="sum", fill_value=0)
    rev = r.pivot_table(index="fy", columns="cat", values="amount",
                        aggfunc="sum", fill_value=0)
    out = pd.DataFrame(index=att.index)
    for cat in ("classes", "performances_events", "community"):
        out[f"{cat}_att"] = att[cat] if cat in att else 0
        out[f"{cat}_rev"] = rev[cat] if cat in rev else 0.0
    out["total_att"] = out[["classes_att", "performances_events_att",
                            "community_att"]].sum(axis=1)
    out["total_rev"] = out[["classes_rev", "performances_events_rev",
                            "community_rev"]].sum(axis=1)
    return out.sort_index()
