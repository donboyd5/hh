"""Campaign prospects + Judy's tracker reader (synthetic data; the real files are PII)."""
import pandas as pd
import pytest
from openpyxl import Workbook
from openpyxl.comments import Comment

from hh.analytics import prospects as pr
from hh.external.campaign_tracker import clean_comment, load_tracker

PLEDGE_PAYMENT = "PLEDGE" + "PAYMENT"  # built by concatenation (see test_analytics)
SEASON = "Donations Oct 1st, 2026 to Jan 31, 2027"


@pytest.fixture
def tracker_path(tmp_path):
    """Mimics full_prep: totals row, header row, list rows, Added block, summary rows."""
    wb = Workbook()
    ws = wb.active
    ws.title = "full_prep"
    ws.append([None, "=SUM(B3:B20)"])
    ws.append(["steward", SEASON, "TK Post Card Sent", "mailing_name", "neon_hh_id"])
    ws.append(["sue", 250.0, "yes", "Gave Already", "100"])        # yes
    ws.append(["don", None, None, "Not Yet Given", "200"])         # not yet
    ws.append([None, None, None, "Board Person", "53"])             # board: blank row
    ws.append(["kel", 0, None, "Zero Amount", "300.0"])            # float-ish id, zero -> not yet
    ws.append(["Added", None, None, None, None])
    ws.append([None, 25.0, None, "Pat  and Reilly", None])         # added, name-only
    ws.append([])
    ws.append(["Board Donations", 3868.0, None, None, None])
    ws["B3"].comment = Comment("======\nID#doco.abc\nJudy Pate    (2026-11-05 14:17:09)\n"
                               "Stock Gift.\n------\nID#doco.def\nDon Boyd (2026-11-05)\nOK", "J")
    p = tmp_path / "campaign-tracker_2026-11-17.xlsx"
    wb.save(p)
    return p


def test_clean_comment_drops_separators_so_excel_does_not_see_a_formula():
    out = clean_comment(
        "======\nID#doco.x\nJudy Pate (t)\nIn honor of Don\n------\nID#doco.y\nreply")
    assert out == "Judy Pate (t) In honor of Don reply"
    assert not out.startswith("=")
    assert clean_comment(None) is None


def test_load_tracker(tracker_path):
    people, lump = load_tracker(tracker_path)
    assert lump == 3868.0
    assert list(people["mailing_name"]) == ["Gave Already", "Not Yet Given", "Board Person",
                                            "Zero Amount", "Pat  and Reilly"]
    assert people["neon_hh_id"].tolist()[:4] == ["100", "200", "53", "300"]  # 300.0 -> 300
    assert pd.isna(people["neon_hh_id"].iloc[4])
    assert people.loc[4, "name_key"] == "pat & reilly"
    assert people.loc[0, "comments"].startswith("Judy Pate")
    assert "Stock Gift." in people.loc[0, "comments"]


def test_season_status_match_order(tracker_path):
    t, _ = load_tracker(tracker_path)
    assert pr.season_status("100", "x", t)["status"] == pr.YES
    assert pr.season_status("100", "x", t)["season_amount"] == 250.0
    assert pr.season_status("200", "x", t)["status"] == pr.NOT_YET
    assert pr.season_status("300", "x", t)["status"] == pr.NOT_YET       # zero is not a gift
    assert pr.season_status("53", "x", t)["status"] == pr.BOARD          # lumped, not "not yet"
    hit = pr.season_status("999", "Pat & Reilly", t)                      # name fallback
    assert (hit["status"], hit["matched_via"]) == (pr.YES, "exact name")
    assert pr.season_status("998", "Nobody", t)["status"] == pr.NOT_LISTED
    co = pr.season_status("C1", "Acme (Gave Already)", t, company_to_hh={"C1": "100"})
    assert (co["status"], co["matched_via"]) == (pr.YES, "company contact's household")


def test_month_periods_labels_partial_months():
    labels = [p[0] for p in pr.month_periods("2025-11-17", "2026-01-31")]
    assert labels == ["Nov 17-30 2025", "Dec 2025", "Jan 2026"]
    assert [p[0] for p in pr.month_periods("2025-12-01", "2025-12-15")] == ["Dec 1-15 2025"]


def _donations():
    rows = [  # account, rollup id, name, amount, date, type, status, account type
        ("a1", "100", "Gave Already", 500, "2025-12-05", "DONATION", "SUCCEEDED", "Individual"),
        ("a2", "200", "Not Yet Given", 300, "2025-11-20", "DONATION", "SUCCEEDED", "Individual"),
        ("a2", "200", "Not Yet Given", 50, "2026-01-31", PLEDGE_PAYMENT, "SUCCEEDED", "Individual"),
        ("c1", "c1", "Contact Person", 1000, "2026-01-10", "DONATION", "SUCCEEDED", "Company"),
        ("b1", "53", "Board Person", 900, "2025-12-20", "DONATION", "SUCCEEDED", "Individual"),
        ("u1", "777", "Unlisted", 5, "2025-12-02", "DONATION", "SUCCEEDED", "Individual"),
        ("a2", "200", "Not Yet Given", 70, "2025-12-03", "DONATION", "CANCELED", "Individual"),
        ("a2", "200", "Not Yet Given", 80, "2025-11-16", "DONATION", "SUCCEEDED", "Individual"),
        ("a2", "200", "Not Yet Given", 90, "2026-02-01", "DONATION", "SUCCEEDED", "Individual"),
        ("36805", "36805", "House", 4, "2025-12-02", "DONATION", "SUCCEEDED", "Individual"),
    ]
    df = pd.DataFrame(rows, columns=["account_id", "id", "name", "donation_amount",
                                     "donation_date", "donation_type", "donation_status",
                                     "account_type"])
    df["donation_date"] = pd.to_datetime(df["donation_date"])
    df["campaign"] = "Annual Fund"
    return df


def test_window_gifts_inclusive_and_clean():
    g = pr.window_gifts(_donations(), "2025-11-17", "2026-01-31")
    assert g["donation_amount"].tolist() == [500, 300, 50, 1000, 900, 5]  # Jan 31 kept
    assert set(g["account_type"]) == {"Individual", "Company"}            # companies count


def test_prospect_tables_drop_only_gave_and_board(tracker_path):
    co = {"c1": "200"}  # company -> Not Yet Given household
    t, _ = load_tracker(tracker_path)
    g = pr.window_gifts(_donations(), "2025-11-17", "2026-01-31", company_to_hh=co)
    g["donor"] = g["name"]
    g = pr.add_status(g, t, company_to_hh=co, notes={"777": "believed moved"})
    tabs = pr.prospect_tables(g, "2025-11-17", "2026-01-31")
    assert list(tabs) == ["combined", "Nov 17-30 2025", "Dec 2025", "Jan 2026", "excluded"]

    comb = tabs["combined"]
    assert comb["neon_hh_id"].tolist() == ["200", "777"]     # sorted large to small
    nyg = comb.iloc[0]
    assert (nyg["total"], nyg["Nov 17-30 2025"], nyg["Jan 2026"]) == (1350, 300, 1050)
    assert nyg["status"] == pr.NOT_YET
    assert comb.iloc[1]["status"] == pr.NOT_LISTED            # kept, status unknown
    assert comb.iloc[1]["neon_note"] == "believed moved"

    assert tabs["Jan 2026"]["neon_hh_id"].tolist() == ["c1", "200"]  # month tabs: unfolded
    ex = tabs["excluded"].set_index("neon_hh_id")["reason"].to_dict()
    assert ex == {"53": "board member", "100": "already gave this season (Judy's sheet)"}

    s = pr.summary_table(g, tabs).set_index("group")["amount"]
    assert s["all households in window"] == s["check: sum of every gift in window"] == 2755


def test_deceased_households_needs_every_member():
    a = pd.DataFrame({"account_id": ["1", "2", "3"], "household_id": ["H", "H", None],
                      "deceased": [True, False, True]})
    assert pr.deceased_households(a) == {"3"}


def test_load_crosswalk(tmp_path):
    p = tmp_path / "x.yaml"
    p.write_text('company_households:\n  "c1": {household: "200", name: x}\n'
                 'notes:\n  "777": {name: y, note: believed moved}\n')
    assert pr.load_crosswalk(p) == ({"c1": "200"}, {"777": "believed moved"})
    assert pr.load_crosswalk(tmp_path / "missing.yaml") == ({}, {})
