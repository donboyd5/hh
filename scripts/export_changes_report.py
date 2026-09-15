"""Diff the current mailing-list workbook against the version sent out on 2026-09-11.

Don sent Sue, Alix and Judy `final-mailing-list-draft_2026-09-11_1048am.xlsx` and asks for
"a list of changes since the lists I sent" after each round of rulings. The lists keep
moving, so the report is generated rather than hand-written.

Households are matched on neon_hh_id, falling back to "name:<normalized mailing name>" for
rows with no Neon record - never on the sheet's `id` column, which is sort position and
renumbers whenever a household is added or removed.

Writes data/20_processed/changes-since-2026-09-11.md.

Usage:
    python scripts/export_changes_report.py [suffix]   # suffix as passed to export_donor_list.py
"""
from __future__ import annotations

import re
import sys

import pandas as pd

from hh import config

BASELINE = config.layer_dir("raw") / "external" / "final-mailing-list-draft_2026-09-11_1048am.xlsx"
BASELINE_LABEL = "2026-09-11 10:48 am"
OUT = config.layer_dir("processed") / "changes-since-2026-09-11.md"

# Why a household came off a list. The baseline's notes say why it qualified, never why
# it was later dropped, so each ruling is recorded here, keyed the same way as the rows.
REMOVED_BECAUSE = {
    "69": "Judy - moved to VA",
    "543": "Don 9/13 - Stephen Schatz deceased",
    "2344": "Don 9/13 - believed moved",
    "3945": "Don 9/13",
    "205": "Don 9/15 - Alix's father; not to be mailed",
    "2457": "Don 9/14 - DNC, drop from reception",
    "4356": "Don 9/14 - minimal local connection; off reception per Judy",
    "53": "Don 9/14 - unable to attend",
    "7": "removed from the list 9/10",
    "name:rich & dari norman": "Judy - moved to NJ",
}

_JUNK = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _JUNK.sub(" ", str(s or "").strip().lower())


def _key(df: pd.DataFrame) -> pd.Series:
    """neon_hh_id where present, else "name:<normalized mailing name>"."""
    hh = df.get("neon_hh_id", pd.Series("", index=df.index)).astype(str).str.strip()
    hh = hh.replace({"nan": "", "None": ""})
    return hh.where(hh != "", "name:" + df["mailing_name"].map(_norm))


def _load(path, sheet: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=sheet, dtype=str).fillna("")
    df = df.set_index(_key(df))
    return df[~df.index.duplicated()]


def _where(row) -> str:
    city, state = row.get("city", ""), row.get("state", "")
    return f" ({city}, {state})" if city else ""


def _reason(key: str, row, *, was: bool = False) -> str:
    """Why the row is on (category, hand note, steward) or off (the recorded ruling)."""
    if was:
        cat = row.get("category", "")
        because = REMOVED_BECAUSE.get(key, "")
        return "; ".join(b for b in (f"was {cat}" if cat else "", because) if b)
    bits = [row.get("category", ""), row.get("notes", "")]
    if row.get("steward", "").strip():
        bits.append(f"steward: {row['steward'].strip()}")
    return "; ".join(b for b in bits if b)


def _section(base: pd.DataFrame, cur: pd.DataFrame, title: str) -> list[str]:
    added = [k for k in cur.index if k not in base.index]
    removed = [k for k in base.index if k not in cur.index]
    out = [
        f"## {title}: {len(base)} → {len(cur)} households "
        f"(+{len(added)} / −{len(removed)})",
        "",
    ]
    for label, keys, src, was in (
        ("Added", added, cur, False),
        ("Removed", removed, base, True),
    ):
        if not keys:
            continue
        rows = src.loc[keys].sort_values("mailing_name")
        out += [f"**{label} ({len(keys)})**", ""]
        for k, r in rows.iterrows():
            reason = _reason(k, r, was=was)
            out.append(f"- {r['mailing_name']}{_where(r)}" + (f" — {reason}" if reason else ""))
        out.append("")
    # category moves for households on both versions
    both = [k for k in cur.index if k in base.index]
    moved = [
        (cur.at[k, "mailing_name"], base.at[k, "category"], cur.at[k, "category"])
        for k in both
        if base.at[k, "category"] != cur.at[k, "category"]
    ]
    if moved:
        out += [f"**Category changed ({len(moved)})**", ""]
        out += [f"- {n}: {a} → {b}" for n, a, b in sorted(moved)]
        out.append("")
    return out


def _stewards(base: pd.DataFrame, cur: pd.DataFrame) -> list[str]:
    both = [k for k in cur.index if k in base.index]
    changed: dict[str, list[str]] = {}
    for k in both:
        a, b = base.at[k, "steward"].strip(), cur.at[k, "steward"].strip()
        if b and a != b:
            changed.setdefault(b, []).append(cur.at[k, "mailing_name"])
    n = sum(len(v) for v in changed.values())
    if not n:
        return []
    out = [f"**Steward assigned or changed ({n})** — from your colleague's and Judy's edit passes", ""]
    for steward in sorted(changed):
        names = ", ".join(sorted(changed[steward]))
        out.append(f"- **{steward}** ({len(changed[steward])}): {names}")
    out.append("")
    return out


def main() -> None:
    suffix = sys.argv[1] if len(sys.argv) > 1 else ""
    cur_path = config.layer_dir("processed") / f"final-mailing-list-draft{suffix}.xlsx"
    label = suffix.lstrip("-") or "current draft"

    lines = [
        f"# Changes to the appeal and reception lists since {BASELINE_LABEL}",
        "",
        f"*Baseline: `{BASELINE.name}` (the version sent to Sue, Alix and Judy). "
        f"Current: {label}, {pd.Timestamp.today():%Y-%m-%d}.*",
        "",
    ]
    board_b, board_c = _load(BASELINE, "board"), _load(cur_path, "board")
    lines += _section(board_b, board_c, "Appeal list (board sheet)")
    lines += _stewards(board_b, board_c)
    lines += _section(_load(BASELINE, "reception_draft"), _load(cur_path, "reception_draft"), "Reception list")

    dnc_b, dnc_c = _load(BASELINE, "do_not_contact"), _load(cur_path, "do_not_contact")
    lines += [
        "## Also since 9/11",
        "",
        "- New columns: `salutation` (from Neon; constructed + highlighted where Neon has none) "
        "and `jp_notes` (Judy's comments) on every sheet but printer; board sheet sorted by "
        "steward then surname.",
        "- ZIPs are 5-digit only; contact research added phones/emails for not-in-Neon rows; "
        "four source-address defects fixed (Welther zip, Putney/Wilbur/Mangsen cities).",
        f"- do_not_contact review sheet: {len(dnc_b)} → {len(dnc_c)} (DNC overrides moved to the appeal list).",
        "- Reception categories now: FST sponsors, top 50 5-yr donors (was 30), ED fund donors "
        "2013-17, HH board members (invited alone, without spouses), hand-picked adds.",
        "",
    ]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT} written ({len(lines)} lines)")


if __name__ == "__main__":
    main()
