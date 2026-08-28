"""Mailing-list assembly (synthetic frames; the real list is local-only PII)."""
import pandas as pd

from hh.analytics.mailing import (
    OUTPUT_COLUMNS,
    _new_codes,
    apply_exclusions,
    build_mailing_list,
    engagement_spend,
    fiscal_year,
    fst_candidates,
    fst_keep_mask,
    gifts_by_fy,
    pick_contact,
    predominant_engagement,
)

PLEDGE_PAYMENT = "PLEDGE" + "PAYMENT"  # built by concatenation (see test_analytics)


def _accounts():
    return pd.DataFrame(
        {
            "account_id": ["A1", "A2", "B1", "C1", "D1"],
            "id": ["H1", "H1", "H2", "H3", "H4"],
            "name": ["Ann & Bob Smith", "Ann & Bob Smith", "Carol Dane", "New Person",
                     "Class Family"],
            "first_name": ["Ann", "Bob", "Carol", "New", "Kim"],
            "last_name": ["Smith", "Smith", "Dane", "Person", "Family"],
            "household_salutation": ["Ann and Bob", None, "Carol", None, None],
            "household_name": ["Ann & Bob Smith", "Ann & Bob Smith", "Carol Dane", "New Person",
                               "Class Family"],
            "full_name": [None, None, None, "New Person", "Kim Family"],
            "company_name": [None] * 5,
            "account_type": ["Individual"] * 5,
            "contact_type": ["Individual"] * 5,
            "deceased": [False] * 5,
            "do_not_contact": [False, False, True, False, False],
            "address_line1": ["1 Main St", None, "2 Elm St", None, "9 School St"],
            "address_line2": [None, None, "Apt 2", None, None],
            "city": ["Cambridge", None, "Salem", None, "Cambridge"],
            "state_province": ["NY", None, "NY", None, "NY"],
            "zip_code": ["12816", None, "12865", None, "12816"],
            "phone_1": ["518-555-0100", None, None, None, None],
            "email_1": [None, "bob@x.org", None, None, "kim@x.org"],
            "household_salutation_": pd.NA,
            "account_created_at": ["2020-01-01", "2019-01-01", "2024-08-01", "2025-10-01",
                                   "2022-03-01"],
            "account_note_text": [None, None, "longtime volunteer", None, None],
            "distance_miles": [0.5, 0.5, 8.0, None, 1.0],
        }
    )


def _donations():
    return pd.DataFrame(
        {
            "donation_id": ["d1", "d2", "d3", "d4", "d5", "d6"],
            "id": ["H1", "H1", "H2", "H3", "H1", "H2"],
            "account_id": ["A1", "A1", "B1", "C1", "A2", "B1"],
            "account_type": ["Individual"] * 6,
            "donation_type": [
                "DONATION", PLEDGE_PAYMENT, "DONATION", "DONATION", "DONATION", "DONATION",
            ],
            "donation_status": ["SUCCEEDED"] * 6,
            "donation_amount": [5.0, 10.0, 500.0, 7.0, 2022.5, 3.0],
            # FY labels: 2024-06-30 -> FY24; 2024-07-01 -> FY25; 2020 -> FY21 (outside window)
            "donation_date": pd.to_datetime(
                ["2024-06-30", "2024-10-23", "2025-11-01", "2020-05-01", "2023-01-15", "2021-08-02"]
            ),
        }
    )


def _registrations():
    return pd.DataFrame(
        {
            "registration_id": ["r1", "r2", "r3", "r4", "r5", "r6"],
            "id": ["H1", "H1", "H2", "H3", "H4", "H4"],  # rollup id (NA household_id for singles)
            "starts_on": pd.to_datetime(
                ["2025-01-15", "2025-02-01", "2024-09-01", "2015-01-01", "2024-10-01", "2025-10-01"]
            ),
            "event_majorcat": ["performance", "class", "other", "performance", "class", "class"],
            "amount": [40.0, 120.0, 75.0, 30.0, 300.0, 250.0],
        }
    )


def test_fiscal_year_july_boundary():
    fy = fiscal_year(pd.to_datetime(["2024-06-30", "2024-07-01", "2024-12-31"]))
    assert fy.tolist() == [2024, 2025, 2025]


def test_gifts_by_fy_sums_and_fills_zero_years():
    out = gifts_by_fy(_donations(), (2022, 2023, 2024, 2025, 2026)).set_index("id")
    assert out.loc["H1", "don_fy2023"] == 2022.5
    assert out.loc["H1", "don_fy2024"] == 5.0
    assert out.loc["H1", "don_fy2025"] == 10.0  # pledge payment counts (regression)
    assert out.loc["H2", "don_fy2026"] == 500.0
    # H3's only gift predates the window, so it has no row here at all — build_mailing_list
    # re-adds listed households from the union of source ids (see the end-to-end test)
    assert "H3" not in out.index


def test_engagement_spend_groups_and_window():
    out = engagement_spend(_registrations(), (2024, 2025, 2026)).set_index("id")
    assert out.loc["H1", "arts_spend_3fy"] == 40.0
    assert out.loc["H1", "classes_spend_3fy"] == 120.0
    assert out.loc["H2", "arts_spend_3fy"] == 75.0  # 'other' (gala) is arts
    assert "H3" not in out.index  # 2015 registration outside the window
    assert out.loc["H1", "regs_3fy"] == 2


def test_predominant_engagement_labels():
    row = pd.Series({"arts_spend_3fy": 10.0, "classes_spend_3fy": 0.0})
    def spend(arts, classes):
        return pd.Series({"arts_spend_3fy": arts, "classes_spend_3fy": classes})

    assert predominant_engagement(row) == "arts"
    assert predominant_engagement(spend(0.0, 5.0)) == "classes"
    assert predominant_engagement(spend(1.0, 1.0)) == "both"
    assert predominant_engagement(spend(0.0, 0.0)) == "none"


def test_pick_contact_most_gifts_then_fallback():
    accounts = _accounts()
    accounts.loc[3, "deceased"] = True  # sole member deceased -> household deceased
    out = pick_contact(accounts, _donations()).set_index("id")
    # A1 has two gifts (d1 and the pledge payment d2) vs A2's one -> A1 (Ann) is the
    # contact; her missing email falls back to Bob's, other fields are her own
    row = out.loc["H1"]
    assert row["contact_account_id"] == "A1"
    assert row["contact_first_name"] == "Ann"
    assert row["salutation"] == "Ann and Bob"
    assert row["address"] == "1 Main St"
    assert row["email"] == "bob@x.org"  # contact's blank falls back across members
    assert bool(row["do_not_contact"]) is False  # ANY across members: H2's B1 is DNC
    assert bool(out.loc["H2", "do_not_contact"]) is True
    assert bool(out.loc["H3", "deceased"]) is True
    assert out.loc["H3", "deceased_members"] == "New Person"


def test_pick_contact_widow_keeps_household_and_becomes_contact():
    accounts = _accounts()
    # A1 (Ann) has the most gifts but has died, and carries Neon's do-not-contact flag as
    # deceased members do; Bob survives -> household lives, Bob is the contact, not DNC
    accounts.loc[0, "deceased"] = True
    accounts.loc[0, "do_not_contact"] = True
    out = pick_contact(accounts, _donations()).set_index("id")
    h1 = out.loc["H1"]
    assert bool(h1["deceased"]) is False
    assert bool(h1["do_not_contact"]) is False
    assert h1["contact_first_name"] == "Bob"
    # deceased_members is built from full_name, which the fixture leaves blank for A1
    assert h1["deceased_members"] in ("None", "nan")  # str() of the blank full_name
    assert pd.isna(out.loc["H2", "deceased_members"])
    # address lines concatenate
    assert out.loc["H2", "address"] == "2 Elm St Apt 2"
    assert out.loc["H2", "note_neon"] == "longtime volunteer"


def test_new_codes_in_name_order():
    codes = _new_codes(pd.Series(["Zed", "Able", "Mid"]))
    assert codes.tolist() == ["new3", "new1", "new2"]  # Able, Mid, Zed order


def test_apply_exclusions_deceased_notes_and_donor_floor():
    table = pd.DataFrame(
        {
            "household_name": [
                "Neon Gone",          # Neon deceased flag
                "Note Gone",          # hand note says died
                "Survivor",           # note says died AND a partner survives -> kept
                "Neon Note Only",     # death only in a NEON staff note -> kept
                "Small Donor",        # donor-rule only, under $200 -> dropped
                "Small Judy Note",    # under $200 with a hand note -> kept
                "Small Stewarded",    # under $200 with a steward -> kept
                "Small Responder",    # under $200 but responded to the appeal -> kept
                "Small Silent",       # under $200 but on the bolded keep-list -> kept
                "Small Judy Bare",    # under $200, Judy's list, no note/steward -> dropped
                "Big Donor",          # donor-rule only, over $200 -> kept
                "Zero Prospect",      # never donated, not donor-rule -> kept (new account)
                "Do Not Contact",     # Neon do-not-contact flag -> kept, listed in QA
            ],
            "id": [str(i) for i in range(1, 14)],
            "deceased": [True] + [False] * 12,
            "do_not_contact": [False] * 12 + [True],
            "note_donor3": [None, "died 2024", "Tim has died; wife/gf still around",
                            None, None, "friend of the house", None, None, None,
                            None, None, None, None],
            "note_neon": [None, None, None, "my uncle passed away; we still attend"]
                        + [None] * 9,
            "steward": [None] * 6 + ["don"] + [None] * 6,  # Small Stewarded has one
            "src_donor_5yr": [True] * 4 + [True] * 6 + [True, False, True],
            "src_donor3": [False] * 5 + [False, False, False, False, True, False, False, False],
            "src_new_accounts": [False] * 11 + [True, False],
            "src_appeal_responded": [False] * 7 + [True] + [False] * 5,
            "src_appeal_gift": [False] * 13,
            "src_engaged_nondonor": [False] * 13,
            "src_silent_selected": [False] * 8 + [True] + [False] * 4,
            "fst": [False] * 13,
            "don_5yr_total": [500.0] * 4 + [100.0] * 6 + [500.0, 0.0, 900.0],
        }
    )
    out, qa = apply_exclusions(table)
    assert out["household_name"].tolist() == [
        "Survivor", "Neon Note Only", "Small Judy Note", "Small Stewarded",
        "Small Responder", "Small Silent", "Big Donor", "Zero Prospect", "Do Not Contact",
    ]
    assert qa["dropped_deceased_neon"] == ["Neon Gone"]
    assert qa["dropped_deceased_note"] == ["Note Gone"]
    assert qa["kept_deceased_note_survivor"] == ["Survivor"]
    assert qa["dropped_small_donor"] == ["Small Donor", "Small Judy Bare"]
    assert qa["do_not_contact"] == ["Do Not Contact"]  # flagged, still in the table
    assert "Do Not Contact" in out["household_name"].tolist()
    out2, qa2 = apply_exclusions(table, drop_do_not_contact=True)
    assert "Do Not Contact" not in out2["household_name"].tolist()
    assert qa2["dropped_do_not_contact"] == ["Do Not Contact"]


def test_fst_candidates_unique_ambiguous_and_none():
    accounts = pd.DataFrame(
        {
            "id": ["H1", "H2", "H3", "H4"],
            "name": ["Jared and Kyle West", "Rich Butler", "Pat Doe", "Ann Lee"],
            "full_name": ["Jared West", None, "Pat Doe", "Ann Lee"],
            "contact_type": ["Individual"] * 4,
        }
    )
    fst_summary = pd.DataFrame(
        {
            "name": ["Kyle & Jared West", "Richard Butler", "Ann Lee",
                     "Sue Doe", "Chris Doe"],
            "in_neon": [False, False, True, False, False],
        }
    )
    out = fst_candidates(fst_summary, accounts).set_index("name")
    # partner-order flip still finds the household
    assert out.loc["Kyle & Jared West", "fst_candidate_id"] == "H1"
    assert out.loc["Kyle & Jared West", "fst_candidate_name"] == "Jared and Kyle West"
    # nickname (rich/richard) finds it via the member account name
    assert out.loc["Richard Butler", "fst_candidate_id"] == "H2"
    assert "Ann Lee" not in out.index  # exact match already -> no candidate needed
    assert "Sue Doe" not in out.index  # no compatible given name anywhere
    assert "Chris Doe" not in out.index  # 'chris' is compatible with no pool given name


def _externals():
    donor3 = pd.DataFrame(
        {
            "household_name": ["Carol Dane"],
            "steward": ["don"],
            "steward_raw": ["Don - know a little"],
            "note_hand": ["friend"],
            "id": ["H2"],
        }
    )
    new_accounts = pd.DataFrame(
        {"household_name": ["New Person"], "note_hand": ["came to gala"], "id": ["H3"]}
    )
    silent = pd.DataFrame(
        {"household_name": ["Carol Dane"], "note_hand": ["letter"], "id": ["H2"]}
    )
    responded = pd.DataFrame(
        {"household_name": ["Ann & Bob Smith"], "note_hand": [None], "id": ["H1"]}
    )
    fst = pd.DataFrame(
        {
            "name": ["Carol Dane", "Zed Sponsor"],
            "n_years": [2, 1],
            "years": ["2024,2025", "2025"],
            "best_tier": ["gold", "inner circle"],  # Zed: $100+ tier -> kept by rule B
            "anonymous": [False, False],
            "org": [False, False],
            "id": ["H2", pd.NA],
            "in_neon": [True, False],
        }
    )
    return donor3, new_accounts, silent, responded, fst


def test_build_mailing_list_end_to_end():
    donor3, new_accounts, silent, responded, fst = _externals()
    table = build_mailing_list(
        _accounts(),
        _donations(),
        _registrations(),
        donor3=donor3,
        new_accounts=new_accounts,
        silent_selected=silent,
        appeal_responded=responded,
        fst_summary=fst,
    ).set_index("household_name")

    assert set(table.columns) == set(OUTPUT_COLUMNS) - {"household_name"}

    # H1: qualifies via the 5-year donor rule AND the appeal-responder list
    h1 = table.loc["Ann & Bob Smith"]
    assert h1["src_appeal_responded"]
    assert h1["src_donor_5yr"]  # 5yr total $2,037.50 >= $10
    # H2's $500 gift on 2025-11-01 falls in the Oct 2025-Jan 2026 campaign window
    h2w = table.loc["Carol Dane"]
    assert h2w["don_appeal_window"] == 500.0 and h2w["src_appeal_gift"]
    assert h1["don_appeal_window"] == 0.0 and not h1["src_appeal_gift"]
    assert h1["don_lifetime"] == 5.0 + 10.0 + 2022.5  # H1's own lifetime gifts only
    assert h1["predominant_engagement"] == "both"
    assert h1["neon_account_ids"] == "A1,A2"
    assert table.attrs["exclusion_qa"] is not None

    # H2: donor3 steward/notes + silent note merged; fst flag set via Neon match
    h2 = table.loc["Carol Dane"]
    assert h2["steward"] == "don" and h2["steward_detail"] == "Don - know a little"
    assert h2["note_donor3"] == "friend" and h2["note_silent"] == "letter"
    assert h2["fst"] and not h2["needs_review"]
    assert h2["fst_years"] == 2 and h2["fst_best_tier"] == "gold"
    assert h2["gave_fy26"] and not h2["gave_fy25"]

    # H3: lapsed donor (gave FY21 only) + new-account flag; never in 5yr window
    h3 = table.loc["New Person"]
    assert h3["no_gift_last_5yrs"] and not h3["never_donated"]
    assert h3["src_new_accounts"] and h3["note_new"] == "came to gala"

    # H4: never gave, but $550 of classes in FY25-26 -> engaged non-donor, exempt from floor
    # (window is FY22-26; these dates fall inside both the 3- and 5-year windows)
    h4 = table.loc["Class Family"]
    assert h4["src_engaged_nondonor"] and h4["never_donated"]
    assert h4["predominant_engagement"] == "classes" and h4["classes_spend_3fy"] == 550.0
    assert h4["classes_spend_5fy"] == 550.0

    # Zed Sponsor: Fort Salem only, not in Neon -> new code, needs review, zeros
    zed = table.loc["Zed Sponsor"]
    assert zed["new_code"] == "new1" and zed["needs_review"] and zed["fst"]
    assert zed["never_donated"] and zed["predominant_engagement"] == "none"
    assert zed["fst_best_tier"] == "inner circle"

    # letter template per row
    assert table.loc["Ann & Bob Smith", "letter"] == "donor"
    assert table.loc["Carol Dane", "letter"] == "donor"
    assert table.loc["Class Family", "letter"] == "class-family"
    assert table.loc["New Person", "letter"] == "new-attender"  # no 5-yr gift + new-accounts list
    assert table.loc["Zed Sponsor", "letter"] == "fst-personal"

    # one row per household; sorted campaign gift desc, 5-yr giving desc, class spend desc
    assert table.index.is_unique
    order = table.index.tolist()
    assert order[0] == "Carol Dane"  # the only campaign-window giver
    assert order[1] == "Ann & Bob Smith"  # then largest 5-yr giving
    assert order[-1] == "Zed Sponsor"  # Fort Salem: no gifts, no spend


def test_fst_keep_mask_rule_b():
    fst = pd.DataFrame(
        {
            "name": ["Friend Once", "Friend Twice", "Inner Once", "Angel 2020", "Angel Back", "Gold"],
            "best_tier": ["friends of fort salem", "friends of fort salem", "inner circle",
                          "opening angels", "opening angels", "gold"],
            "n_years": [1, 2, 1, 1, 2, 1],
            "years": ["2024", "2023,2025", "2022", "2020", "2020,2023", "2021"],
        }
    )
    assert fst_keep_mask(fst).tolist() == [False, True, True, False, True, True]
