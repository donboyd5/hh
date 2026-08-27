"""Don's Fort Salem -> Neon match decisions: harvest from the workbook, keep in YAML.

The review sheet (``fst-candidates`` in the mailing-list workbook) is an *output*; Don's
Y/N marks and notes on it are harvested into ``data/30_external/fst-confirmations.yaml``,
keyed by the pair (Fort Salem name, Neon household id) so a decision survives changes in
scores, ranks, or row order. The export reads the YAML, folds confirmed names into their
Neon households, and re-emits the review sheet with the marks pre-filled — so the
workbook can be regenerated freely and the decisions live in one versioned input.

Conflict rule: a Fort Salem name confirmed against two Neon households with *different*
names (Kathy Clarke -> Katherine Clark, Astoria AND Michael & Kathryn Clarke, Boiceville)
cannot both be right; such names are held as ``conflict`` and not applied until one Y
remains. Two Y's on households with the *same* name (Michael Hatzel twice — a duplicate
person record in Neon) are allowed: the name folds into the lowest id and both ids are
reported for Judy.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from .. import config
from .mailing import norm_name

CONFIRMATIONS_FILENAME = "fst-confirmations.yaml"
REVIEW_SHEET = "fst-candidates"

# header variants the review sheet has carried (Don renamed the shouting version)
_CONFIRM_HEADERS = ("confirm", "CONFIRM (Y/N)")
_NOTE_HEADERS = ("boyd_note", "boyd_notes", "note_boyd")


def confirmations_path() -> Path:
    return config.layer_dir("external") / CONFIRMATIONS_FILENAME


def load_confirmations(path: Path | None = None) -> pd.DataFrame:
    """All decisions as rows ``[fst_name, neon_hh_id, confirm, boyd_note, decided]``."""
    src = Path(path) if path is not None else confirmations_path()
    cols = ["fst_name", "neon_hh_id", "confirm", "boyd_note", "decided"]
    if not src.exists():
        return pd.DataFrame(columns=cols)
    loaded = yaml.safe_load(src.read_text()) or {}
    rows = [
        {
            "fst_name": str(e.get("fst_name")),
            "neon_hh_id": str(e.get("neon_hh_id")),
            "confirm": str(e.get("confirm", "")).strip().upper(),
            "boyd_note": e.get("boyd_note"),
            "decided": str(e.get("decided", "")),
        }
        for e in loaded.get("decisions") or []
    ]
    return pd.DataFrame(rows, columns=cols)


def read_review_marks(workbook: Path) -> pd.DataFrame:
    """Don's marks from a saved copy of the workbook's review sheet.

    Returns ``[fst_name, neon_hh_id, neon_household, confirm, boyd_note]`` for rows that
    carry a mark or a note (blank rows are undecided, not "N").
    """
    df = pd.read_excel(workbook, sheet_name=REVIEW_SHEET)
    confirm_col = next((c for c in _CONFIRM_HEADERS if c in df.columns), None)
    if confirm_col is None:
        raise ValueError(f"{workbook.name}: no confirm column on sheet {REVIEW_SHEET!r}")
    note_col = next((c for c in _NOTE_HEADERS if c in df.columns), None)
    out = pd.DataFrame(
        {
            "fst_name": df["fst_name"].astype(str).str.strip(),
            "neon_hh_id": df["neon_hh_id"].astype(str).str.strip(),
            "neon_household": df["neon_household"],
            "confirm": df[confirm_col].astype("string").str.strip().str.upper(),
            "boyd_note": df[note_col].astype("string").str.strip() if note_col else pd.NA,
        }
    )
    out["confirm"] = out["confirm"].where(out["confirm"].isin(["Y", "N"]), pd.NA)
    return out[out["confirm"].notna() | out["boyd_note"].notna()].reset_index(drop=True)


def merge_decisions(existing: pd.DataFrame, marks: pd.DataFrame, *, today: str | None = None
                    ) -> tuple[pd.DataFrame, list[str]]:
    """Fold new marks into the decision table (pair-keyed). A changed decision replaces
    the old one and is reported; unchanged pairs keep their original ``decided`` date."""
    today = today or date.today().isoformat()
    key = ["fst_name", "neon_hh_id"]
    changes: list[str] = []
    ex = existing.set_index(key) if len(existing) else existing
    rows = []
    for m in marks.itertuples(index=False):
        k = (m.fst_name, m.neon_hh_id)
        prior = ex.loc[k] if len(existing) and k in ex.index else None
        confirm = m.confirm if pd.notna(m.confirm) else (prior["confirm"] if prior is not None else "")
        note = m.boyd_note if pd.notna(m.boyd_note) else (prior["boyd_note"] if prior is not None else None)
        decided = prior["decided"] if prior is not None and prior["confirm"] == confirm else today
        if prior is not None and prior["confirm"] != confirm and confirm:
            changes.append(f"{m.fst_name} -> {m.neon_hh_id}: {prior['confirm']} -> {confirm}")
        rows.append({"fst_name": m.fst_name, "neon_hh_id": m.neon_hh_id, "confirm": confirm,
                     "boyd_note": note, "decided": decided})
    new = pd.DataFrame(rows, columns=["fst_name", "neon_hh_id", "confirm", "boyd_note", "decided"])
    if len(existing):
        untouched = existing[~existing.set_index(key).index.isin(new.set_index(key).index)]
        new = pd.concat([untouched, new], ignore_index=True)
    return new.sort_values(key).reset_index(drop=True), changes


def write_confirmations(decisions: pd.DataFrame, path: Path | None = None) -> Path:
    dest = Path(path) if path is not None else confirmations_path()
    entries = []
    for r in decisions.itertuples(index=False):
        e = {"fst_name": r.fst_name, "neon_hh_id": r.neon_hh_id, "confirm": r.confirm,
             "decided": r.decided}
        if pd.notna(r.boyd_note) and r.boyd_note:
            e["boyd_note"] = str(r.boyd_note)
        entries.append(e)
    header = (
        "# Don's Fort Salem -> Neon match decisions, harvested from the review sheet by\n"
        "# scripts/harvest_fst_confirmations.py. LOCAL ONLY (names people). Keyed by\n"
        "# (fst_name, neon_hh_id); edit here or re-mark the workbook and re-harvest.\n"
    )
    dest.write_text(header + yaml.safe_dump({"decisions": entries}, sort_keys=False,
                                            allow_unicode=True))
    return dest


def resolve(decisions: pd.DataFrame, households: pd.DataFrame
            ) -> tuple[dict[str, str], dict[str, list[str]], list[str]]:
    """Apply the conflict rule.

    Returns ``(confirmed, duplicates, conflicts)``: ``confirmed`` maps each Fort Salem
    name to the Neon household it folds into; ``duplicates`` maps a folded id to the
    other same-name ids also confirmed (duplicate person records, for Judy);
    ``conflicts`` lists names held back because their Y's name different households.
    """
    label = dict(zip(households["id"].astype(str), norm_name(households["name"]), strict=True))
    confirmed: dict[str, str] = {}
    duplicates: dict[str, list[str]] = {}
    conflicts: list[str] = []
    ys = decisions[decisions["confirm"] == "Y"]
    for name, grp in ys.groupby("fst_name"):
        ids = sorted(set(grp["neon_hh_id"]))
        names = {label.get(i) for i in ids}
        if len(names) > 1:
            conflicts.append(name)
            continue
        confirmed[name] = ids[0]
        if len(ids) > 1:
            duplicates[ids[0]] = ids[1:]
    return confirmed, duplicates, conflicts
