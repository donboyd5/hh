"""Parsers for the externally received lists (synthetic workbooks; real files are PII)."""
import pandas as pd

from hh.external import lists


def _write(path, rows, header=True):
    df = pd.DataFrame(rows)
    df.to_excel(path, index=False, header=header)
    return path


def test_mfs_donors_layout_and_placeholders(tmp_path):
    src = _write(
        tmp_path / "mfs.xlsx",
        [
            ["Music from Salem Donors", None, None, None, None, None],
            [None, None, None, None, None, None],
            ["Robert & Carolyn Akland", None, "327 McDougal Lake Rd.", "Cossayuna", "NY", "12823"],
            ["Caroline Ashton", None, "17 St. Luke's Place", "Cambridge", "NY", "12816"],
            ["Sophie Paul", None, "Address Unavailable", None, None, None],
            ["Anne Miller & Donald Minkel", None, "Duplicate (See Above)", "Greenwich", "NY", 12834],
        ],
        header=False,
    )
    df = lists.load_mfs_donors(src)
    assert list(df["name"]) == [
        "Robert & Carolyn Akland", "Caroline Ashton", "Sophie Paul",
        "Anne Miller & Donald Minkel",
    ]
    addressed = df.set_index("name")
    assert addressed.loc["Robert & Carolyn Akland", "street"] == "327 McDougal Lake Rd."
    assert pd.isna(addressed.loc["Sophie Paul", "street"])  # placeholder -> no address
    assert pd.isna(addressed.loc["Anne Miller & Donald Minkel", "street"])  # dup marker
    assert addressed.loc["Caroline Ashton", "zip_code"] == "12816"  # zip as string


def test_friends_keeps_couples_as_listed(tmp_path):
    src = _write(tmp_path / "friends.xlsx", [
        {"Name": "Bethany Moss Parks"},
        {"Name": "Teri Ptacek"},
        {"Name": "Anne Miller & Donald Minkel"},  # couple row stays one household
        {  # blank row dropped
            "Name": None
        },
    ])
    df = lists.load_friends(src)
    assert list(df["name"]) == [
        "Bethany Moss Parks", "Teri Ptacek", "Anne Miller & Donald Minkel",
    ]


def test_attendees_fragment_shapes(tmp_path):
    src = _write(
        tmp_path / "attendees.xlsx",
        [
            ["Music from Salem's Concerts attendees", None, None, None, None],
            ["Anderson", "Karen", "&/or", "Gurney", "Richard"],  # two alternates
            ["Avis", "Elizabeth & Walter", None, None, None],  # couple, shared surname
            ["Bachrach", "Eric", None, None, None],  # plain
            ["M Fortier", "Douglas", None, None, None],  # middle initial BEFORE surname
            ["Boorom", "Jimm", "&/or", "Mary", "Diane"],
        ],
        header=False,
    )
    df = lists.load_attendees(src)
    by_note = df.set_index("row_note")
    assert set(by_note.loc["Anderson | Karen | &/or | Gurney | Richard", "name"]) == {
        "Karen Anderson", "Richard Gurney",
    }
    assert by_note.loc["Avis | Elizabeth & Walter", "name"] == "Elizabeth & Walter Avis"
    assert by_note.loc["Bachrach | Eric", "name"] == "Eric Bachrach"
    assert by_note.loc["M Fortier | Douglas", "name"] == "Douglas M Fortier"
    # title banner row is skipped entirely
    assert not df["name"].str.contains("Music from Salem").any()


def test_appeal2025_ids_across_sheets(tmp_path):
    src = tmp_path / "appeal.xlsx"
    with pd.ExcelWriter(src, engine="openpyxl") as xw:
        pd.DataFrame(
            {"id": [44385.0, 512.0], "name": ["Kathleen Achor", "Gregory & Judith Aidala"],
             "hhid": [None, 512.0]}
        ).to_excel(xw, sheet_name="gen appeal", index=False)
        pd.DataFrame({"Account ID": [39671.0, 34560.0]}).to_excel(
            xw, sheet_name="theater appeal to artists", index=False
        )
        pd.DataFrame({"id": [7.0], "name": ["Top Person"], "hhid": [7.0]}).to_excel(
            xw, sheet_name="top for segments and personaliz", index=False
        )
    ids = lists.load_appeal2025_ids(src)
    assert set(ids["sheet"]) == {
        "gen appeal", "theater appeal to artists", "top for segments and personaliz",
    }
    gen = ids[ids["sheet"].eq("gen appeal")]
    # the account-level row (blank hhid) keeps its account id; the household row its hhid
    assert set(gen["neon_hh_id"].dropna()) == {"512"}
    assert set(gen["account_id"].dropna()) == {"44385"}
    artists = ids[ids["sheet"].eq("theater appeal to artists")]
    assert set(artists["account_id"]) == {"39671", "34560"}
