"""Fort Salem match decisions: harvest, merge, and the conflict rule (synthetic)."""
import pandas as pd

from hh.external.fst_confirmations import (
    load_confirmations,
    merge_decisions,
    read_review_marks,
    resolve,
    write_confirmations,
)


def _review_xlsx(path):
    pd.DataFrame(
        {
            "confirm": ["y", "N", None, None],
            "boyd_note": [None, None, "not sure", None],
            "fst_name": ["Kyle & Jared West", "Kyle & Jared West", "Jennie Shaw", "Nobody"],
            "neon_hh_id": ["H1", "H9", "H2", "H3"],
            "neon_household": ["Jared and Kyle West", "K West", "Jennifer Shaw", "N Body"],
        }
    ).to_excel(path, sheet_name="fst-candidates", index=False)


def test_read_review_marks_normalizes_and_skips_blank_rows(tmp_path):
    p = tmp_path / "wb.xlsx"
    _review_xlsx(p)
    marks = read_review_marks(p)
    assert marks["fst_name"].tolist() == ["Kyle & Jared West", "Kyle & Jared West", "Jennie Shaw"]
    assert marks["confirm"].tolist() == ["Y", "N", pd.NA]  # note-only row kept, undecided
    assert marks.iloc[2]["boyd_note"] == "not sure"


def test_merge_and_roundtrip_reports_changes(tmp_path):
    p = tmp_path / "wb.xlsx"
    _review_xlsx(p)
    marks = read_review_marks(p)
    first, changes = merge_decisions(load_confirmations(tmp_path / "none.yaml"), marks, today="2026-08-27")
    assert changes == [] and first["decided"].eq("2026-08-27").all()
    yaml_path = write_confirmations(first, tmp_path / "c.yaml")
    reloaded = load_confirmations(yaml_path)
    assert len(reloaded) == 3
    # Don flips West/H9 to Y later: change is reported, other dates untouched
    marks.loc[1, "confirm"] = "Y"
    second, changes = merge_decisions(reloaded, marks, today="2026-09-01")
    assert changes == ["Kyle & Jared West -> H9: N -> Y"]
    assert second.set_index(["fst_name", "neon_hh_id"]).loc[("Kyle & Jared West", "H1"), "decided"] == "2026-08-27"


def test_resolve_conflicts_vs_duplicate_records():
    households = pd.DataFrame(
        {
            "id": ["H1", "H9", "D1", "D2", "C1", "C2"],
            "name": ["Jared and Kyle West", "K West", "Michael Hatzel", "Michael Hatzel",
                     "Katherine Clark", "Michael & Kathryn Clarke"],
        }
    )
    decisions = pd.DataFrame(
        {
            "fst_name": ["Kyle & Jared West", "Kyle & Jared West", "Margo & Michael Hatzel",
                         "Margo & Michael Hatzel", "Kathy Clarke", "Kathy Clarke"],
            "neon_hh_id": ["H1", "H9", "D1", "D2", "C1", "C2"],
            "confirm": ["Y", "N", "Y", "Y", "Y", "Y"],
            "boyd_note": [None] * 6,
            "decided": ["2026-08-27"] * 6,
        }
    )
    confirmed, duplicates, conflicts = resolve(decisions, households)
    assert confirmed == {"Kyle & Jared West": "H1", "Margo & Michael Hatzel": "D1"}
    assert duplicates == {"D1": ["D2"]}  # same-name duplicate records: fold to one, report both
    assert conflicts == ["Kathy Clarke"]  # different households: held for Don
