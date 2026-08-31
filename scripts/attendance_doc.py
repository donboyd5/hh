"""Regenerate meta-docs/attendance.md — FY attendance trends + latest-complete-FY breakdown.

Run after ``scripts/build.py`` (the tables read ``registrations_enriched.parquet``):

    python scripts/attendance_doc.py

Everything is aggregate — event titles and counts only, no people — so the doc is safe to
commit. Categories follow whatever scheme is in ``src/hh/categorize/major.py``; the class
"families" in the breakdown are keyword buckets defined below and are meant to be edited
as programs change. The breakdown always covers the latest *complete* fiscal year (the
current FY is partial and appears only in the trends table, flagged).
"""
from __future__ import annotations

import re

import pandas as pd

from hh import io
from hh.analytics.mailing import fiscal_year
from hh.analytics.productions import count_succeeded_attendees, match_production

DOC_PATH = "meta-docs/attendance.md"

# ---- class families: (label, regex on the event name) — first match wins ------------
CLASS_FAMILIES: list[tuple[str, str]] = [
    ("Youth-theatre showcases (ticketed performances of the camps)",
     r"performance\s*-"),
    ("Summer camps & children's theatre",
     r"camp|afternoon arts|children'?s theatre|children'?s theater|teen theat(re|er)|youth theat(re|er)"),
    ("Yoga, wellness & fitness",
     r"yoga|gyrokinesis|wellness|strength|balance|fitness|pilates"),
    ("Dance (ballet, tap, jazz)", r"ballet|tap|jazz"),
    ("Visual arts", r"draw|art|paint|clay|craft|visual|photograph|pottery"),
    ("Hip hop", r"hip hop"),
    ("Irish dance", r"irish|ceili"),
    ("Bollywood dance & fencing", r"bollywood|bolly-?x|indian dance|fencing"),
    ("Acting & improv", r"acting|improv|drama club|theater games"),
    ("Music instruction", r"music|musicianship|voice|sing|piano|guitar|fiddle|violin"),
]

_WEEKDAY = r"(?:mon|tues|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)days?"
_MONTH = (r"(?:january|february|march|april|may|june|july|august|september|october|"
          r"november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)\.?")
_DATEISH = re.compile(rf"\s*,?\s*\b(?:{_WEEKDAY}|{_MONTH})\b|\b\d{{4}}\b", re.I)


def series_name(name: str) -> str:
    """Collapse an event's sections into a series title (drop ages, dates, weekdays)."""
    s = re.split(r"\s*\(", name)[0]  # "(Ages …)" and everything after
    s = re.split(r"\s+-\s+Week\s+\d", s)[0]  # Afternoon Arts weeks
    s = re.split(_DATEISH, s)[0]  # first date/weekday token
    s = re.sub(r"\s*\*?\*?(Cancelled|CANCELED|Class is Full|SOLD OUT).*", "", s, flags=re.I)
    return s.strip(" .-*—-,") or name


def class_family(name: str) -> str:
    for label, pattern in CLASS_FAMILIES:
        if re.search(pattern, name, re.I):
            return label
    return "Other classes"


def fmt(x: float) -> str:
    return f"${x:,.0f}"


def main() -> None:
    r = io.read_parquet("processed", "registrations_enriched.parquet")
    r["attendees"] = r["tickets"].apply(count_succeeded_attendees)
    r["fy"] = fiscal_year(r["starts_on"])
    r["name"] = r["event_name"].astype("string").str.strip()
    today = pd.Timestamp.now().normalize()
    current_fy = int(fiscal_year(pd.Series([today]))[0])
    latest_complete = current_fy - 1

    errors = r[r["event_majorcat"] == "ERROR"]
    ok = r[r["event_majorcat"] != "ERROR"]

    # ---- trends table ----------------------------------------------------------
    t = (
        ok.pivot_table(index="fy", columns="event_majorcat", values="attendees",
                       aggfunc="sum", fill_value=0)
        .rename(columns={"class": "classes", "performance": "perf"})
        .reindex(columns=["classes", "perf", "other", "community"], fill_value=0)
    )
    t["performances_events"] = t.pop("perf") + t.pop("other")
    t["total"] = t["classes"] + t["performances_events"] + t["community"]
    trends = t[["classes", "performances_events", "community", "total"]].astype(int)

    lines = [
        "# Attendance — trends and current-year breakdown",
        "",
        "*Regenerate after a pull with `python scripts/attendance_doc.py` (runs on the processed",
        "tables, so `scripts/build.py` first). Event categories follow the current scheme in",
        "`src/hh/categorize/major.py` — see the book's Methodology appendix for the principles.",
        "Aggregate numbers only.*",
        "",
        "## Attendance by fiscal year",
        "",
        "| FY (Jul–Jun) | Classes | Performances & events | Community | Total |",
        "|---|---:|---:|---:|---:|",
    ]
    for fy, row in trends.iterrows():
        label = f"FY{fy - 2000}" + (" (partial)" if fy == current_fy else "")
        lines.append(f"| {label} | {row['classes']:,} | {row['performances_events']:,} "
                     f"| {row['community']:,} | {row['total']:,} |")
    lines += [
        "",
        "*Attendees = people (each registration's ticket records, `registrationStatus`",
        "SUCCEEDED), not registration counts — about 1.7 people per registration. Fiscal year",
        f"by event start date; FY{current_fy - 2000} is year-to-date as of the latest pull.",
    ]
    if len(errors):
        lines.append(f"* **{len(errors)} registrations ({errors['attendees'].sum():,.0f} attendees) "
                     "are in the ERROR category and excluded — new event types the rules don't "
                     "know; categorize them before trusting these rows.**")
    else:
        lines.append("* No uncategorized (ERROR) events in this pull — every event has a rule.")

    # ---- breakdown of the latest complete FY ------------------------------------
    fy = ok[ok["fy"] == latest_complete].copy()
    fy = fy[~fy["name"].str.contains(r"\btest\b", case=False, regex=True)]
    ev = (fy.groupby(["event_majorcat", "event_id"], as_index=False)
          .agg(name=("name", "first"), minor=("event_minorcat", "first"),
               att=("attendees", "sum"), dol=("amount", "sum")))
    lines += [
        "",
        f"## FY{latest_complete - 2000} breakdown — latest complete year",
        "",
        f"*{ev['att'].sum():,.0f} attendees across {len(ev)} events. Dollars are registration",
        "amounts as recorded (gross — see the canceled-class note at the end).*",
    ]

    # classes by family / series
    cls = ev[ev["event_majorcat"] == "class"].copy()
    cls["fam"] = cls["name"].map(class_family)
    cls["s"] = cls["name"].map(series_name)
    lines += [
        "",
        f"### Classes — {cls['att'].sum():,.0f} attendees, {fmt(cls['dol'].sum())}",
        "",
        "| Family / series | Sections | Attendees | $ |",
        "|---|---:|---:|---:|",
    ]
    fam_order = [label for label, _ in CLASS_FAMILIES] + ["Other classes"]
    for fam in fam_order:
        sub = cls[cls["fam"] == fam]
        if sub.empty:
            continue
        g = sub.groupby("s").agg(sec=("event_id", "count"), att=("att", "sum"), dol=("dol", "sum"))
        lines.append(f"| **{fam}** | | **{sub['att'].sum():,.0f}** | **{fmt(sub['dol'].sum())}** |")
        for s, row in g.sort_values("att", ascending=False).iterrows():
            lines.append(f"| — {s} | {row['sec']:.0f} | {row['att']:.0f} | {fmt(row['dol'])} |")
    canceled = cls[cls["att"] == 0]
    lines += [
        f"| **TOTAL CLASSES** | **{len(cls)}** | **{cls['att'].sum():,.0f}** | **{fmt(cls['dol'].sum())}** |",
    ]
    if len(canceled):
        lines.append(
            f"\n*Canceled sections: {len(canceled)} events, 0 attendees, "
            f"{fmt(canceled['dol'].sum())} of refunded registration dollars — people paid, then "
            "the class was canceled and Neon marked the attendees REFUNDED or CANCELED; "
            "attendance correctly counts none of them.*"
        )

    # performances + other
    perf = ev[ev["event_majorcat"] == "performance"].copy()
    perf["prod"] = [
        "Music From Salem (co-presented series)" if "Music From Salem" in n
        else (match_production(n) or n)
        for n in perf["name"]
    ]
    other = ev[ev["event_majorcat"] == "other"]
    lines += [
        "",
        f"### Performances & events — {perf['att'].sum() + other['att'].sum():,.0f} attendees, "
        f"{fmt(perf['dol'].sum() + other['dol'].sum())}",
        "",
        "| Series / event | Events | Attendees | $ |",
        "|---|---:|---:|---:|",
    ]
    minor_labels = {"theater": "Theater productions", "music": "Concerts",
                    "opera": "Opera", "other": "Film & other performances"}
    for minor, label in minor_labels.items():
        sub = perf[perf["minor"] == minor]
        if sub.empty:
            continue
        g = sub.groupby("prod").agg(n=("event_id", "count"), att=("att", "sum"), dol=("dol", "sum"))
        lines.append(f"| **{label}** | | **{sub['att'].sum():,.0f}** | **{fmt(sub['dol'].sum())}** |")
        for p, row in g.sort_values("att", ascending=False).iterrows():
            lines.append(f"| — {p} | {row['n']:.0f} | {row['att']:.0f} | {fmt(row['dol'])} |")
    if len(other):
        lines.append(f"| **Galas, fundraisers, previews** | | **{other['att'].sum():,.0f}** "
                     f"| **{fmt(other['dol'].sum())}** |")
        for _, row in other.sort_values("att", ascending=False).iterrows():
            lines.append(f"| — {row['name']} | 1 | {row['att']:.0f} | {fmt(row['dol'])} |")
    lines += [
        f"| **TOTAL PERFORMANCES & EVENTS** | **{len(perf) + len(other)}** | "
        f"**{perf['att'].sum() + other['att'].sum():,.0f}** | "
        f"**{fmt(perf['dol'].sum() + other['dol'].sum())}** |",
    ]

    # community
    com = ev[ev["event_majorcat"] == "community"]
    lines += [
        "",
        f"### Community — {com['att'].sum():,.0f} attendees, {fmt(com['dol'].sum())}",
        "",
        "| Event | Attendees | $ |",
        "|---|---:|---:|",
    ]
    for _, row in com.sort_values("att", ascending=False).iterrows():
        lines.append(f"| — {row['name']} | {row['att']:.0f} | {fmt(row['dol'])} |")
    lines += [f"| **TOTAL COMMUNITY** | **{com['att'].sum():,.0f}** | **{fmt(com['dol'].sum())}** |"]

    lines += [
        "",
        "*Notes: a *series* collapses an event's sections (same title across terms); the",
        "family buckets are keyword rules in `scripts/attendance_doc.py` — edit them as",
        "programs change. Film screenings count as performances under the current scheme;",
        "youth-program showcases count as classes.*",
        "",
    ]
    io_path = __import__("pathlib").Path(DOC_PATH)
    io_path.write_text("\n".join(lines))
    print(f"wrote {DOC_PATH}: {len(trends)} fiscal years, FY{latest_complete - 2000} breakdown "
          f"({len(ev)} events, {ev['att'].sum():,.0f} attendees)")


if __name__ == "__main__":
    main()
