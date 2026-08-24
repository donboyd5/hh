"""External workbook loaders: appeal mailing list, EoY export, provenance (synthetic fixtures)."""
import pandas as pd

from hh.external.appeal import appeal_load_qa, clean_appeal_recipients
from hh.external.eoy import clean_eoy_gifts
from hh.external.ids import coerce_id
from hh.external.provenance import external_source_entry


def _sheet(rows, columns, notes_col):
    """Build a raw sheet: the ``name``-length rows dict, padded to shape, plus a notes column."""
    n = len(rows.get("name", []))
    data = {header: rows.get(key, [None] * n) for key, header in columns.items()}
    base = pd.DataFrame(data)
    base[notes_col] = rows.get("notes", [None] * n)
    return base


def _top_sheet(rows):
    return _sheet(
        rows,
        {
            "name": "name",
            "accountid": "accountid",
            "hhid": "hhid",
            "group": "group",
            "appeal segment": "appeal segment",
            "Annual Appeal Donation": "Annual Appeal Donation",
        },
        "Unnamed: 31",
    )


def _gen_sheet(rows):
    return _sheet(
        rows,
        {
            "name": "name",
            "accountid": "accountid",
            "hhid": "hhid",
            "group": "group",
            "Annual Appeal Donation": "Annual Appeal Donation",
        },
        "Unnamed: 28",
    )


def _theater_sheet(rows):
    return _sheet(
        rows,
        {
            "name": "Household Name/Account Name",
            "accountid": "Account ID",
            "Annual Appeal Donation": "Annual Appeal Donation",
        },
        "Unnamed: 16",
    )


def _sheets(top=None, gen=None, theater=None):
    return {
        "top": _top_sheet(top or {}),
        "gen": _gen_sheet(gen or {}),
        "theater": _theater_sheet(theater or {}),
    }


def test_coerce_id_handles_floats_blanks_and_strings():
    out = coerce_id(pd.Series([40486.0, "35097", None, 43871, "junk"]))
    assert out.tolist() == ["40486", "35097", pd.NA, "43871", pd.NA]
    assert out.isna().tolist() == [False, False, True, False, True]


def test_load_appeal_sheets_reads_all_three_sheets(tmp_path):
    from hh.external.appeal import load_appeal_sheets

    path = tmp_path / "appeal.xlsx"
    with pd.ExcelWriter(path) as xl:
        _top_sheet({"name": ["A B"], "accountid": [40486.0], "hhid": [4123.0]}).to_excel(
            xl, sheet_name="top for segments and personaliz", index=False
        )
        _gen_sheet({"name": ["C D"], "accountid": [35097.0]}).to_excel(
            xl, sheet_name="gen appeal", index=False
        )
        _theater_sheet({"name": ["E F"], "Account ID": [39671.0]}).to_excel(
            xl, sheet_name="theater appeal to artists", index=False
        )
        pd.DataFrame({"x": [1]}).to_excel(xl, sheet_name="scratch", index=False)

    sheets = load_appeal_sheets(path)
    assert sorted(sheets) == ["gen", "theater", "top"]  # extra sheets ignored


def test_clean_appeal_recipients_drops_total_rows():
    # two flavors: nameless subtotal rows (top) and name == 'Total' (gen)
    sheets = _sheets(
        top={"name": ["A B", None], "accountid": [40486.0, None],
             "Annual Appeal Donation": [100.0, 29431.25]},
        gen={"name": ["C D", "Total"], "accountid": [35097.0, None]},
    )
    out = clean_appeal_recipients(sheets)
    names = list(out["workbook_name"])
    assert names == ["A B", "C D"]


def test_clean_appeal_recipients_drops_placeholder_and_blank_rows():
    sheets = _sheets(
        gen={"name": ["Not on List", None, "C D"], "accountid": [None, None, 35097.0]}
    )
    out = clean_appeal_recipients(sheets)
    assert list(out["workbook_name"]) == ["C D"]


def test_clean_appeal_recipients_dedupes_exact_duplicates():
    sheets = _sheets(
        gen={"name": ["C D", "C D"], "accountid": [35097.0, 35097.0], "hhid": [91.0, 91.0]}
    )
    out = clean_appeal_recipients(sheets)
    assert len(out) == 1
    qa = appeal_load_qa(sheets, out)
    assert qa["duplicate_rows"] == {"top": 0, "gen": 1, "theater": 0}


def test_clean_appeal_recipients_keeps_and_flags_missing_id_donor():
    # Neubohn-style: real donor, no id anywhere — must survive, flagged, never force-fitted
    sheets = _sheets(
        top={"name": ["N & A Neubohn"], "accountid": [None], "hhid": [None],
             "appeal segment": ["opera"], "Annual Appeal Donation": [3000.0]}
    )
    out = clean_appeal_recipients(sheets)
    assert len(out) == 1
    row = out.iloc[0]
    assert row["missing_account_id"]
    assert row["account_id"] is None or pd.isna(row["account_id"])
    assert row["appeal_gift_recorded"] == 3000.0
    qa = appeal_load_qa(sheets, out)
    assert qa["missing_id_with_recorded_gift"] == 1


def test_clean_appeal_recipients_derives_segments():
    sheets = _sheets(
        top={"name": ["A B"], "accountid": [40486.0], "appeal segment": ["music"]},
        gen={"name": ["C D"], "accountid": [35097.0]},
        theater={"name": ["E F"], "Account ID": [39671.0]},
    )
    out = clean_appeal_recipients(sheets)
    seg = dict(zip(out["workbook_name"], out["appeal_segment"], strict=True))
    assert seg == {"A B": "music", "C D": "general", "E F": "theater-artists"}


def test_clean_appeal_recipients_captures_staff_notes():
    sheets = _sheets(
        top={"name": ["A B"], "accountid": [40486.0], "notes": ["Sustaining Donor"]},
        gen={"name": ["C D"], "accountid": [35097.0], "notes": ["Ron is deceased"]},
    )
    out = clean_appeal_recipients(sheets)
    notes = dict(zip(out["workbook_name"], out["staff_notes"], strict=True))
    assert notes["A B"] == "Sustaining Donor"
    assert notes["C D"] == "Ron is deceased"


def test_clean_appeal_recipients_keeps_excel_row_for_traceability():
    sheets = _sheets(
        gen={"name": [None, "C D", "Total"], "accountid": [None, 35097.0, None]}
    )
    out = clean_appeal_recipients(sheets)
    # header is Excel row 1, so the kept row (2nd data row) is workbook row 3
    assert list(out["excel_row"]) == [3]


def test_clean_eoy_gifts_drops_total_row_and_converts_serial_dates():
    raw = pd.DataFrame(
        {
            "First Name": ["Ann", "Bob", None],
            "Last Name": ["Lee", "Ng", None],
            "Household Name": ["Lee", None, None],
            "Email 1": ["Ann@Example.com ", None, None],
            "Zip Code": [12816.0, "05201", None],
            "Donation Date": [46029, 46000, 46029],  # Excel serials (2026-01-07, 2025-12-09)
            "Donation Amount": [100.0, 50.0, 29354.69],
            "Anonymous Donation": ["No", "Donor Name Anonymous", None],
        }
    )
    out = clean_eoy_gifts(raw)
    assert len(out) == 2  # TOTAL row (no donor identity) dropped
    assert list(out["donation_date"].dt.strftime("%Y-%m-%d")) == [
        "2026-01-07",
        "2025-12-09",
    ]
    assert out["email"].tolist() == ["ann@example.com", pd.NA]
    assert out["zip5"].tolist() == ["12816", "05201"]
    assert list(out["anonymous"]) == [False, True]


def test_clean_eoy_gifts_handles_datetime_dates():
    # openpyxl usually hands us real datetimes; those must pass through unchanged
    raw = pd.DataFrame(
        {
            "First Name": ["Ann"],
            "Last Name": ["Lee"],
            "Household Name": [None],
            "Donation Date": pd.to_datetime(["2025-12-01"]),
            "Donation Amount": [25.0],
        }
    )
    out = clean_eoy_gifts(raw)
    assert out["donation_date"].iloc[0] == pd.Timestamp("2025-12-01")


def test_load_boyd_notes_reads_ids_and_skips_incomplete(tmp_path):
    from hh.external.notes import load_boyd_notes

    f = tmp_path / "boyd-notes.yaml"
    f.write_text(
        "notes:\n"
        '  "64": {name: Evelyn Estey, note: did not respond to texts}\n'
        '  "87": {name: Charles & Marcia Reiss, note: ""}\n'  # empty note -> skipped
        "  205:\n"  # missing note entirely -> skipped
        "    name: Thom Jones\n"
    )
    notes = load_boyd_notes(f)
    assert notes == {"64": "did not respond to texts"}


def test_load_boyd_notes_missing_file_is_empty(tmp_path):
    from hh.external.notes import load_boyd_notes

    assert load_boyd_notes(tmp_path / "absent.yaml") == {}


def test_external_source_entry_records_sha256(tmp_path, monkeypatch):
    import yaml

    from hh.external import provenance
    from hh.external.provenance import append_external_manifest

    # keep the test out of the real data/manifest/ layer
    monkeypatch.setattr(provenance.config, "layer_dir", lambda _key: tmp_path)

    f = tmp_path / "source.xlsx"
    f.write_bytes(b"fake workbook")
    entry = external_source_entry(f, note="test source")
    assert len(entry["sha256"]) == 64
    assert entry["note"] == "test source"

    path = append_external_manifest(entry, slug="test")
    loaded = yaml.safe_load(path.read_text())
    assert len(loaded["sources"]) == 1
    # re-recording the same file (same sha256) does not duplicate history
    append_external_manifest(external_source_entry(f, note="again"), slug="test")
    loaded = yaml.safe_load(path.read_text())
    assert len(loaded["sources"]) == 1
    assert loaded["sources"][0]["note"] == "again"
