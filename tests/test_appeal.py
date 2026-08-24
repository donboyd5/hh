"""FY26 appeal analytics: window boundaries, as-of features, household attribution, EoY match."""
import pandas as pd

from hh.analytics.appeal import (
    appeal_household_table,
    campaign_gifts,
    engagement_asof,
    prior_giving_features,
    reconcile_eoy_export,
)

ASOF = pd.Timestamp("2025-10-01")


def _donations(rows):
    """Frames shaped like clean_donations output: id is the household rollup."""
    return pd.DataFrame(
        {
            "donation_id": [r[0] for r in rows],
            "account_id": [r[1] for r in rows],
            "id": [r[2] for r in rows],
            "account_type": [r[3] for r in rows],
            "donation_date": pd.to_datetime([r[4] for r in rows]),
            "donation_amount": [r[5] for r in rows],
            "donation_status": [r[6] for r in rows],
            "donation_type": [r[7] for r in rows],
            "campaign": [r[8] for r in rows],
        }
    )

CAMPAIGN = "Annual Fund Drive - 2025-2026"


def test_campaign_gifts_window_and_status():
    d = _donations([
        ("D1", "A1", "H1", "Individual", "2025-10-01", 100, "SUCCEEDED", "DONATION", CAMPAIGN),
        ("D2", "A1", "H1", "Individual", "2026-01-31", 100, "SUCCEEDED", "DONATION", CAMPAIGN),
        # D3 after window; D4 not SUCCEEDED; D5 other campaign
        ("D3", "A1", "H1", "Individual", "2026-02-01", 100, "SUCCEEDED", "DONATION", CAMPAIGN),
        ("D4", "A1", "H1", "Individual", "2025-12-01", 100, "CANCELED", "DONATION", CAMPAIGN),
        ("D5", "A1", "H1", "Individual", "2025-12-01", 100, "SUCCEEDED", "DONATION", "Gala"),
    ])
    out = campaign_gifts(d)
    assert list(out["donation_id"]) == ["D1", "D2"]


def test_prior_giving_asof_excludes_appeal_window():
    d = _donations([
        # D1 FY25 prior; D2 prior but FY26; D3 inside the appeal window
        ("D1", "A1", "H1", "Individual", "2025-05-30", 100, "SUCCEEDED", "DONATION", "Other"),
        ("D2", "A1", "H1", "Individual", "2025-09-30", 60, "SUCCEEDED", "DONATION", "Other"),
        ("D3", "A1", "H1", "Individual", "2025-10-01", 500, "SUCCEEDED", "DONATION", CAMPAIGN),
    ])
    out = prior_giving_features(d, asof=ASOF)
    row = out.iloc[0]
    assert row["prior_lifetime_amount"] == 160  # both pre-appeal gifts count
    assert row["prior_donor"]
    assert row["prior_fy_amount"] == 100  # only the FY25 gift (window opened 2025-07-01)
    assert not row["lapsed_donor"]


def test_prior_giving_tier_and_lapsed():
    d = _donations([
        # H1: lifetime 1500, last gift 2023-09-01 (>24mo before appeal) -> lapsed, $1k tier
        ("D1", "A1", "H1", "Individual", "2023-09-01", 1500, "SUCCEEDED", "DONATION", "Other"),
        # H2: gave 2025-05-01 -> current donor, FY25 donor, $100–999 tier
        ("D2", "A2", "H2", "Individual", "2025-05-01", 120, "SUCCEEDED", "DONATION", "Other"),
    ])
    out = prior_giving_features(d, asof=ASOF).set_index("id")
    assert out.loc["H1", "prior_size_tier"] == "$1,000–4,999"
    assert bool(out.loc["H1", "lapsed_donor"])
    assert not bool(out.loc["H1", "prior_fy_donor"])  # 2023 gift predates FY25
    assert out.loc["H2", "prior_size_tier"] == "$100–999"
    assert not bool(out.loc["H2", "lapsed_donor"])
    assert bool(out.loc["H2", "prior_fy_donor"])


def test_engagement_asof_uses_event_start_not_registration_date():
    regs = pd.DataFrame(
        {
            "registration_id": ["R1", "R2", "R3"],
            "id": ["H1", "H2", "H3"],
            "event_majorcat": ["performance", "class", "performance"],
            "event_minorcat": ["theater", pd.NA, "music"],
            # R1: registered Sept for a November show -> NOT engaged as of Oct 1
            # R2: class that started before the appeal -> engaged
            # R3: show that started before the appeal -> engaged
            "starts_on": pd.to_datetime(["2025-11-01", "2025-06-01", "2025-09-30"]),
            "registered_at": pd.to_datetime(["2025-09-15", "2025-05-01", "2025-08-01"]),
        }
    )
    out = engagement_asof(regs, asof=ASOF).set_index("id")
    assert "H1" not in out.index  # attendance had not happened yet
    assert out.loc["H2", "eng_profile"] == "class"
    assert out.loc["H3", "eng_profile"] == "arts"
    assert out.loc["H3", "eng_perf_music"] == 1


def _accounts_geo(rows):
    return pd.DataFrame(
        {
            "account_id": [r[0] for r in rows],
            "household_id": [r[1] for r in rows],
            "id": [r[1] if r[1] is not None else r[0] for r in rows],
            "name": [r[2] for r in rows],
            "group": ["household" if r[1] is not None else "account" for r in rows],
            "distance_band": [None] * len(rows),
            "city": [None] * len(rows),
            "state_province": [None] * len(rows),
            "zip_code": [None] * len(rows),
            "address_line1": [r[3] for r in rows],
            "deceased": [False] * len(rows),
            "do_not_contact": [False] * len(rows),
        }
    )


def _recipients(rows):
    return pd.DataFrame(
        {
            "source_sheet": [r[0] for r in rows],
            "excel_row": [2] * len(rows),
            "account_id": [r[1] for r in rows],
            "workbook_hhid": [r[2] for r in rows],
            "workbook_name": [r[3] for r in rows],
            "group": [None] * len(rows),
            "appeal_segment": [r[4] for r in rows],
            "appeal_gift_recorded": [None] * len(rows),
            "staff_notes": [None] * len(rows),
            "missing_account_id": [r[1] is None for r in rows],
        }
    )


def test_appeal_household_table_attributes_spouse_gift():
    # household H1: spouse A1 was appealed; the gift arrived on A2's account (same household)
    acct = _accounts_geo([("A1", "H1", "Doe House", "1 Main St"), ("A2", "H1", None, None)])
    rec = _recipients([("top", "A1", "H1", "Doe House", "music")])
    don = _donations([
        ("D1", "A2", "H1", "Individual", "2025-12-26", 1000, "SUCCEEDED", "DONATION", CAMPAIGN),
    ])
    regs = pd.DataFrame(columns=["registration_id", "id", "event_majorcat", "starts_on"])
    out = appeal_household_table(rec, acct, don, regs).set_index("id")
    assert bool(out.loc["H1", "appealed"])
    assert bool(out.loc["H1", "responded"])  # gift via the non-appealed spouse counts
    assert out.loc["H1", "afd_amount"] == 1000


def test_appeal_household_table_universe_includes_not_appealed():
    acct = _accounts_geo([("A1", "H1", "Doe House", "1 Main St"), ("A9", None, "Jane Solo", None)])
    rec = _recipients([("top", "A1", "H1", "Doe House", "music")])
    don = _donations([])
    regs = pd.DataFrame(columns=["registration_id", "id", "event_majorcat", "starts_on"])
    out = appeal_household_table(rec, acct, don, regs).set_index("id")
    assert bool(out.loc["H1", "appealed"])
    assert not bool(out.loc["A9", "appealed"])  # never-appealed account stays in the universe
    assert not bool(out.loc["A9", "responded"])
    assert out.loc["A9", "eng_profile"] == "none"
    assert not bool(out.loc["A9", "has_mail"])


def test_appeal_household_table_flags_company_gift():
    acct = _accounts_geo([("C1", None, "Acme Corp", "5 Mill Rd")])
    rec = _recipients([("gen", "C1", None, "Acme Corp", "general")])
    don = _donations([
        ("D1", "C1", "C1", "Company", "2025-11-15", 400, "SUCCEEDED", "DONATION", CAMPAIGN),
    ])
    regs = pd.DataFrame(columns=["registration_id", "id", "event_majorcat", "starts_on"])
    out = appeal_household_table(rec, acct, don, regs).set_index("id")
    assert bool(out.loc["C1", "responded"])
    assert bool(out.loc["C1", "afd_company_gift"])
    assert out.loc["C1", "prior_n_gifts"] == 0  # company gifts are not "prior giving" here


def test_appeal_household_table_unmatched_recipient_falls_back_to_workbook_hhid():
    # account 40486 no longer exists in Neon; the workbook's hhid still names the household
    acct = _accounts_geo([("A1", "H1", "Doe House", "1 Main St")])
    rec = _recipients([("gen", "40486", "H1", "Doe House", "general")])
    don = _donations([])
    regs = pd.DataFrame(columns=["registration_id", "id", "event_majorcat", "starts_on"])
    out = appeal_household_table(rec, acct, don, regs).set_index("id")
    assert bool(out.loc["H1", "appealed"])
    assert not bool(out.loc["H1", "appeal_matched_in_neon"])


def test_reconcile_eoy_matches_by_email_then_name_zip():
    eoy = pd.DataFrame(
        {
            "donor_first": ["Ann", "Bob", "Zed"],
            "donor_last": ["Lee", "Ng", "Nobody"],
            "household_name": [None, None, None],
            "email": pd.Series(["ann@example.com", None, "zed@example.com"], dtype="string"),
            "zip5": pd.Series(["12816", "05201", "99999"], dtype="string"),
        }
    )
    accounts = pd.DataFrame(
        {
            "account_id": ["A1", "A2", "A3"],
            "id": ["H1", "A2", "H3"],
            "email_1": ["Ann@Example.com", None, "other@example.com"],
            "first_name": ["Ann", "Bob", "Real"],
            "last_name": ["Lee", "Ng", "Person"],
            "zip_code": ["12816", 5201.0, "99999"],
        }
    )
    don = _donations([
        ("D1", "A1", "H1", "Individual", "2025-12-01", 100, "SUCCEEDED", "DONATION", CAMPAIGN),
    ])
    out = reconcile_eoy_export(eoy, don, accounts)
    by_name = out.set_index(out["donor_last"])
    assert by_name.loc["Lee", "match_method"] == "email"
    assert by_name.loc["Lee", "matched_rollup_id"] == "H1"
    assert by_name.loc["Ng", "match_method"] == "name-zip"  # no email, matched on name+zip
    assert by_name.loc["Nobody", "match_method"] == "unmatched"
    assert by_name.loc["Lee", "neon_afd_n_gifts"] == 1
