"""MfS concert attendees at Hubbard Hall: best-effort address match (local-only, PII).

Don, 2026-09-11: separate from the donor-mailing-list work - "did you match any [of the
attendees] against Neon? What did you do with the ones that didn't match? ... an
additional sheet that matches all 41 (as best you can) using assessment roll and other
web info."

One row per attendee (41 total). Sources, in precedence order:
  1. neon            - the automated attendee-vs-Neon match (23 hits) plus 2 more found
                        by a manual surname cross-check the automated matcher missed
                        (nickname/partial-name variants)
  2. assessment-roll  - Washington/Rensselaer Co. property roll, matched by hand
  3. web-research     - people-search research, see data/30_external/mfs-attendee-research.yaml
  4. none             - no address found by any source

Output: data/20_processed/mfs-attendee-match.xlsx (single sheet)

Usage:
    python scripts/export_mfs_attendee_match.py
"""
from __future__ import annotations

import re

import pandas as pd
import yaml
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from hh import config, io

RESEARCH_FILE = config.layer_dir("external") / "mfs-attendee-research.yaml"
XLSX_FILENAME = "mfs-attendee-match.xlsx"

# Assessment-roll matches (Don, 2026-09-11): hand-matched by name against
# data/10_interim/assessment_rolls_2026.parquet; see the yaml for full sourcing detail.
ROLL_ADDRESS = {
    "elizabeth finkelstein": ("6 Church St", "Greenwich", "NY", "12834"),
    "katherine danforth": ("5 Saratoga St Apt A", "Hoosick Falls", "NY", "12090"),
    "patricia gardner": ("21993 Route 22 Apt F", "Hoosick Falls", "NY", "12090"),
    "michele & erik graham": ("153 Main St", "Greenwich", "NY", "12834"),
}

# Manual cross-check hits the automated attendee-vs-Neon matcher missed (nickname /
# partial-name variants) - Don, 2026-09-11.
MANUAL_NEON_MATCH = {
    "lisa chang": "296",
    "marti & ray ellermann": "3704",
}
MANUAL_NEON_NOTE = (
    "matched by hand - the automated matcher missed this on a nickname/partial-name "
    "variant (attendee list name vs Neon household name)"
)


_ROLL_JUNK = re.compile(r"\b(?:mr|mrs|ms|dr|and|the|family)\b|[.,&]", re.I)


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", str(name)).strip().lower()


def _norm_street(s) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _research() -> dict:
    if not RESEARCH_FILE.exists():
        return {}
    return (yaml.safe_load(RESEARCH_FILE.read_text()) or {}).get("notes") or {}


def _roll_corroborates(name: str, address, roll: pd.DataFrame) -> bool:
    """True if the assessment roll independently has an owner-name hit for `name`
    whose street matches `address` (guards against common-name false positives on a
    39k-row multi-county roll - a name hit alone isn't enough, the street must agree)."""
    if not address:
        return False
    s = re.sub(r"\(.*?\)", "", str(name))
    s = re.sub(r"\s+", " ", _ROLL_JUNK.sub(" ", s)).strip()
    toks = s.split()
    if len(toks) < 2:
        return False
    last, first = toks[-1], toks[0]
    hits = roll[
        roll["owners"].str.contains(re.escape(last), case=False, na=False)
        & roll["owners"].str.contains(re.escape(first), case=False, na=False)
    ]
    target = _norm_street(address)[:8]
    return any(target and (target in _norm_street(h) or _norm_street(h)[:8] in target) for h in hits["street"])


def build() -> pd.DataFrame:
    book = io.read_parquet("processed", "address_book.parquet")
    att = book[book["mfs_attendee"].fillna(False)].copy()
    research = _research()

    rows = []
    for r in att.itertuples(index=False):
        key = _norm(r.name)
        if r.in_neon:
            no_addr = not str(r.address or "").strip()
            rows.append({
                "name": r.name, "matched_to_neon": True, "neon_hh_id": r.neon_hh_id,
                "address": r.address or None, "city": r.city or None,
                "state": r.state_province or None, "zip": r.zip_code or None,
                "source": "neon", "confidence": "confirmed",
                "notes": "matched to Neon, but no address on file there" if no_addr else None,
            })
            continue
        if key in MANUAL_NEON_MATCH:
            hh_id = MANUAL_NEON_MATCH[key]
            bk = book.loc[book["neon_hh_id"].eq(hh_id)].iloc[0]
            rows.append({
                "name": r.name, "matched_to_neon": True, "neon_hh_id": hh_id,
                "address": bk["address"], "city": bk["city"], "state": bk["state_province"],
                "zip": bk["zip_code"], "source": "neon", "confidence": "confirmed",
                "notes": MANUAL_NEON_NOTE,
            })
            continue
        rec = research.get(r.name, {})
        if key in ROLL_ADDRESS:
            street, city, state, zip_ = ROLL_ADDRESS[key]
            rows.append({
                "name": r.name, "matched_to_neon": False, "neon_hh_id": None,
                "address": street, "city": city, "state": state, "zip": zip_,
                "source": "assessment-roll", "confidence": "probable",
                "notes": str(rec.get("finding", "")).strip() or None,
            })
            continue
        addr_conf = rec.get("address_confidence")
        rows.append({
            "name": r.name, "matched_to_neon": False, "neon_hh_id": None,
            "address": rec.get("address"), "city": rec.get("city"),
            "state": rec.get("state"), "zip": rec.get("zip"),
            "source": "web-research" if rec else "none",
            "confidence": addr_conf or ("hint" if rec else "none"),
            "notes": str(rec.get("finding", "")).strip() or None,
        })

    df = pd.DataFrame(rows)

    # independent public-source (assessment-roll) corroboration - meaningful mainly for
    # the Neon-matched rows (Don, 2026-09-11: "which of those are in neon and have good
    # addresses not just from neon but from public sources"); also checked for the
    # roll/web rows themselves as a sanity cross-check, though those already cite the
    # roll as their source
    roll = io.read_parquet("interim", "assessment_rolls_2026.parquet")
    df["roll_corroborated"] = [
        _roll_corroborates(n, a, roll) for n, a in zip(df["name"], df["address"])
    ]
    df.loc[df["source"] == "assessment-roll", "roll_corroborated"] = True

    df["good_address"] = df["confidence"].isin(["confirmed", "probable"])

    df["__key"] = df["name"].map(_norm)
    df = df.sort_values("__key").drop(columns="__key").reset_index(drop=True)
    df.insert(0, "id", range(1, len(df) + 1))
    return df


def main() -> None:
    df = build()
    xlsx = config.layer_dir("processed") / XLSX_FILENAME
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        df.to_excel(xw, sheet_name="mfs_attendees", index=False)
        sheet = xw.sheets["mfs_attendees"]
        sheet.freeze_panes = "B2"  # house style: header row + first column frozen
        widths = {"name": 26, "address": 24, "city": 14, "notes": 60}
        for i, col in enumerate(df.columns, start=1):
            sheet.column_dimensions[get_column_letter(i)].width = widths.get(col, 12)
        for cell in sheet[1]:
            cell.font = Font(bold=True)
    print(df["source"].value_counts().to_string())
    print(df["confidence"].value_counts().to_string())
    print(f"\n{len(df)} attendees -> {xlsx.name}")


if __name__ == "__main__":
    main()
