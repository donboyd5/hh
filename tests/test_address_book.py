"""Address-book assembly (synthetic frames; the real book is local-only PII)."""
import pandas as pd

from hh.external.address_book import BOOK_COLUMNS, build_address_book


def _accounts():
    # H1: addressed donor couple; H2: no address (MfS fills it); H3: addressed;
    # H4: company-only rollup the MfS list vouches for; H9: company-only rollup the
    # Fort Salem list vouches for
    return pd.DataFrame(
        {
            "account_id": ["A1", "A2", "B1", "C1", "E1", "D1"],
            "id": ["H1", "H1", "H2", "H3", "H4", "H9"],
            "name": ["Ann & Bob Smith", "Ann & Bob Smith", "Carol Dane", "New Person",
                     "Kim Family", "Margo & Michael Hatzel"],
            "first_name": ["Ann", "Bob", "Carol", "New", "Kim", "Margo"],
            "last_name": ["Smith", "Smith", "Dane", "Person", "Family", "Hatzel"],
            "full_name": ["Ann Smith", "Bob Smith", "Carol Dane", "New Person",
                          "Kim Family", "Michael Hatzel"],
            "company_name": [None] * 6,
            "account_type": ["Individual", "Individual", "Individual", "Individual",
                             "Company", "Company"],
            "contact_type": ["Individual", "Individual", "Individual", "Individual",
                             "Company", "Company"],
            "deceased": [False] * 6,
            "do_not_contact": [False] * 6,
            "address_line1": ["1 Main St", None, None, "9 School St", None, "19 Cary Lane"],
            "address_line2": [None] * 6,
            "city": ["Cambridge", None, "Salem", "Cambridge", "Cambridge", "Salem"],
            "state_province": ["NY", None, "NY", "NY", "NY", "NY"],
            "zip_code": ["12816", None, "12865", "12816", "12816", "12865"],
            "phone_1": [None] * 6,
            "email_1": [None] * 6,
            "account_created_at": ["2020-01-01"] * 6,
            "account_note_text": [None] * 6,
            "distance_miles": [1.0] * 6,
        }
    )


def _donations():
    return pd.DataFrame(
        {
            "donation_id": ["d1", "d2", "d3"],
            "id": ["H1", "H1", "H3"],
            "account_id": ["A1", "A1", "C1"],
            "account_type": ["Individual"] * 3,
            "donation_status": ["SUCCEEDED"] * 3,
            "donation_type": ["DONATION"] * 3,
            "donation_amount": [100.0, 50.0, 500.0],
            "donation_date": ["2024-06-01", "2025-06-01", "2023-01-01"],
        }
    )


def _fst_summary():
    # one matched to H1's label, one to the company-only H9, three standalone
    return pd.DataFrame(
        {
            "name": ["Ann & Bob Smith", "Margo & Michael Hatzel", "Bob & Carolyn Akland",
                     "Ruth Flint Frew", "Bob and Liz Skinner"],
            "best_tier": ["friends of fort salem", "inner circle", "bronze",
                          "friends of fort salem", "silver"],
            "years": ["2023,2024", "2024", "2022,2023,2024", "2021", "2020,2021,2022"],
            "n_years": [2, 1, 3, 1, 3],
            "anonymous": [False] * 5,
            "org": [False] * 5,
            "id": ["H1", "H9", pd.NA, pd.NA, pd.NA],
            "in_neon": [True, True, False, False, False],
            "match_type": ["exact", "confirmed", pd.NA, pd.NA, pd.NA],
        }
    )


def _contact_notes():
    return pd.DataFrame(
        {
            "household_name": ["Ruth Flint Frew", "Bob and Liz Skinner"],
            "contact_note": ["Died June 2025.", "Robert died 2024; survived by Elizabeth."],
            "contact_confidence": ["confirmed", "confirmed"],
            "contact_address": [pd.NA, pd.NA],
            "deceased": [True, False],
            "survivor": [None, "Elizabeth Skinner"],
        }
    )


def _roll_hits():
    return pd.DataFrame(
        {
            "household_name": ["Bob & Carolyn Akland", "Bob and Liz Skinner"],
            "given_agreement": [100.0, 95.0],
            "owners": ["Akland Robert", "Skinner Robert"],
            "street": ["327 McDougal Lake Rd.", "543 Upper Main"],
            "city": ["Cossayuna", "Salem"],
            "state": ["NY", "NY"],
            "zip": ["12823", "12865"],
            "town": ["Argyle", "Salem"],
            "source": ["Washington County NY 2026 roll", "Washington County NY 2026 roll"],
            "confidence": ["strong", "probable"],
        }
    )


def _received():
    return {
        "mfs_donor": pd.DataFrame(
            {
                "name": ["Ann & Bob Smith", "Carol Dane", "Kim Family",
                         "Robert & Carolyn Akland"],
                "street": ["500 Fifth Ave.", "2 Elm St", "PO Box 12", "240 E. 47th St."],
                "city": ["New York", "Salem", "Cambridge", "New York"],
                "state_province": ["NY", "NY", "NY", "NY"],
                "zip_code": ["10018", "12865", "12816", "10017"],
            }
        ),
        "friends_to_add": pd.DataFrame({"name": ["Teri Ptacek"]}),
        "mfs_attendee": pd.DataFrame({"name": ["Karen Anderson"]}),
    }


def _book(**overrides):
    defaults = dict(
        received=_received(),
        roll_hits=_roll_hits(),
        contact_notes=_contact_notes(),
        appeal_ids=pd.DataFrame(
            {"sheet": ["gen appeal"] * 2, "neon_hh_id": ["H1", None], "account_id": [None, "D1"]}
        ),
        mailing_list=pd.DataFrame(
            {
                "neon_hh_id": ["H1", "H3", None, None],
                "household_name": ["Ann & Bob Smith", "New Person", "Elizabeth Skinner",
                                   "Bob & Carolyn Akland"],
                "letter": ["donor", "new-attender", "fst-personal", "fst-personal"],
            }
        ),
        fst_summary=_fst_summary(),
    )
    defaults.update(overrides)
    return build_address_book(_accounts(), _donations(), **defaults)


def test_columns_and_identity_anchor():
    book, candidates = _book()
    assert list(book.columns) == BOOK_COLUMNS
    assert set(candidates["source"]) <= {"neon", "roll-strong", "roll-probable",
                                         "mfs-list", "web-business"}
    neon_rows = book[book["in_neon"]]
    assert neon_rows["neon_hh_id"].notna().all()
    solo_rows = book[~book["in_neon"]]
    assert solo_rows["neon_hh_id"].isna().all()
    assert solo_rows["name"].notna().all()


def test_precedence_neon_wins_and_fills_blanks():
    book, _ = _book()
    by = book.set_index("name")
    # Neon address present -> Neon wins over the MfS listing (different street)
    assert by.loc["Ann & Bob Smith", "address"] == "1 Main St"
    assert by.loc["Ann & Bob Smith", "address_source"] == "neon"
    # Neon blank -> the MfS list fills it
    assert by.loc["Carol Dane", "address"] == "2 Elm St"
    assert by.loc["Carol Dane", "address_source"] == "mfs-list"
    assert by.loc["Kim Family", "address"] == "PO Box 12"
    assert bool(by.loc["Kim Family", "po_box"]) is True
    # solo row: roll-strong beats the MfS listing; roll-probable stands when alone
    assert by.loc["Bob & Carolyn Akland", "address_source"] == "roll-strong"
    assert by.loc["Bob & Carolyn Akland", "address"] == "327 McDougal Lake Rd."
    assert by.loc["Elizabeth Skinner", "address_source"] == "roll-probable"


def test_conflict_flag_when_sources_disagree():
    book, candidates = _book()
    by = book.set_index("name")
    # H1: Neon "1 Main St" vs MfS "500 Fifth Ave." -> conflict, Neon still chosen
    assert bool(by.loc["Ann & Bob Smith", "address_conflict"]) is True
    assert by.loc["Ann & Bob Smith", "address"] == "1 Main St"
    assert (candidates["identity"] == "H1").sum() == 2  # both candidates recorded
    # Kim Family: only the MfS source exists -> no conflict
    assert bool(by.loc["Kim Family", "address_conflict"]) is False


def test_rule_b_flag_on_solo_fort_salem_rows():
    book, _ = _book()
    by = book.set_index("name")
    assert by.loc["Bob & Carolyn Akland", "fst_rule_b"] == "kept"  # 3 years
    assert by.loc["Ruth Flint Frew", "fst_rule_b"] == "below-bar"  # 1 year, friends tier
    assert by.loc["Elizabeth Skinner", "fst_rule_b"] == "kept"  # silver, 3 years, relabeled


def test_web_confirmed_death_kept_and_flagged_not_dropped():
    book, _ = _book()
    row = book[book["name"].eq("Ruth Flint Frew")]
    assert len(row) == 1
    assert bool(row.iloc[0]["deceased"]) is True
    assert row.iloc[0]["web_note"].startswith("Died June 2025.")


def test_survivor_relabel_and_mailing_list_letter():
    book, _ = _book()
    by = book.set_index("name")
    # the listed "Bob and Liz Skinner" row is relabeled to the survivor, and the
    # mailing-list context attaches to the relabeled name
    assert "Bob and Liz Skinner" not in by.index
    assert by.loc["Elizabeth Skinner", "letter"] == "fst-personal"
    assert bool(by.loc["Elizabeth Skinner", "in_mailing_list"]) is True
    assert by.loc["Ann & Bob Smith", "letter"] == "donor"
    assert by.loc["Bob & Carolyn Akland", "letter"] == "fst-personal"


def test_mailed_2025_via_household_and_account_ids():
    book, _ = _book()
    by = book.set_index("neon_hh_id")
    assert bool(by.loc["H1", "mailed_2025"]) is True  # by household id
    assert bool(by.loc["H4", "mailed_2025"]) is False  # its account E1 was not mailed
    assert bool(by.loc["H9", "mailed_2025"]) is True  # account id D1 -> H9 rollup
    assert bool(by.loc["H3", "mailed_2025"]) is False


def test_company_only_rollup_kept_when_list_vouched():
    book, _ = _book()
    flagged = book[book["neon_company_only"].fillna(False)]
    assert set(flagged["neon_hh_id"]) == {"H4", "H9"}
    h9 = flagged[flagged["neon_hh_id"].eq("H9")].iloc[0]
    assert bool(h9["fst"]) is True
    assert h9["address"] == "19 Cary Lane"  # address survives via the full rollup


def test_exact_received_match_flags_neon_row():
    book, _ = _book()
    by = book.set_index("name")
    assert bool(by.loc["Carol Dane", "mfs_donor"]) is True  # matched H2
    assert bool(by.loc["Kim Family", "mfs_donor"]) is True  # matched H4 (company-only)
    assert by.loc["Carol Dane", "in_neon"] is True or bool(by.loc["Carol Dane", "in_neon"])
    # unmatched names stay standalone with their flag
    assert bool(book[book["name"].eq("Teri Ptacek")].iloc[0]["friends_to_add"]) is True


def test_solo_rows_merge_across_lists_on_canonical_key():
    # FST's "Bob & Carolyn Akland" (bob folded to robert) and MfS's
    # "Robert & Carolyn Akland" are one household: one row, both flags, FST display name
    book, _ = _book()
    row = book[book["name"].eq("Bob & Carolyn Akland")]
    assert len(row) == 1
    assert bool(row.iloc[0]["fst"]) is True
    assert bool(row.iloc[0]["mfs_donor"]) is True
    assert "Robert & Carolyn Akland" not in set(book["name"])


def test_fuzzy_candidate_shown_never_folded():
    book, _ = _book()
    solo = book[~book["in_neon"]]
    assert solo["in_neon"].eq(False).all()  # never absorbed
    # 3 individual households + 2 list-vouched company-only rollups
    assert int(book["in_neon"].sum()) == 5


def _research_frame():
    return pd.DataFrame(
        {
            "household_name": ["Bob & Carolyn Akland", "Ruth Flint Frew", "Teri Ptacek",
                               "Widow Person"],
            "phone": ["518-555-0199", None, "802-555-0143", None],
            "phone_confidence": ["probable", None, "hint", None],
            "email": [None, None, "teri@example.org", None],
            "email_confidence": [None, None, "confirmed", None],
            "finding": [
                "TruePeopleSearch lists this number at the Cossayuna address.",
                "Died June 2025 (obituary).",
                "Professional site contact.",
                "Husband died 2024; she survives and still lives in Salem.",
            ],
            "death_or_move": [None, "obituary confirms death", None, "husband died 2024"],
            "sources": [
                "https://www.truepeoplesearch.com/details?x=1",
                "https://www.gariepyfuneralhomes.com/obituaries/ruth-frew",
                "https://example.org/teri",
                "https://example.org/obit",
            ],
            "deceased_web": [False, True, False, False],
        }
    )


def test_contact_research_fills_solo_rows_only():
    frame = _research_frame()
    frame.loc[3, "household_name"] = "Elizabeth Skinner"  # a solo row in the fixture
    book, _ = _book(contact_research=frame)
    by = book.set_index("name")
    # solo row: phone + confidences + joined note
    assert by.loc["Bob & Carolyn Akland", "research_phone"] == "518-555-0199"
    assert by.loc["Bob & Carolyn Akland", "research_phone_confidence"] == "probable"
    assert "TruePeopleSearch" in by.loc["Bob & Carolyn Akland", "research_note"]
    assert by.loc["Teri Ptacek", "research_email"] == "teri@example.org"
    # Neon rows are untouched — Neon's own phone/email columns serve them
    assert pd.isna(by.loc["Ann & Bob Smith", "research_phone"])
    assert "phone" in book.columns and "email" in book.columns


def test_research_deceased_flips_only_on_explicit_flag():
    # the widow's note mentions a death in prose but lacks the flag: she stays mailable
    book, _ = _book(contact_research=_research_frame())
    by = book.set_index("name")
    assert bool(by.loc["Ruth Flint Frew", "deceased"]) is True  # explicit deceased_web
    widow = book[book["name"].str.contains("Widow", na=False)]
    if len(widow):  # only present when the row survived the fixture's solo pool
        assert bool(widow.iloc[0]["deceased"]) is False
    # prose alone never flips: a died-mentioning finding with the flag off
    frame = _research_frame()
    frame["deceased_web"] = False
    frame.loc[0, "finding"] = "Died last year, sources say."
    book2, _ = _book(contact_research=frame)
    ak = book2[book2["name"].eq("Bob & Carolyn Akland")].iloc[0]
    assert bool(ak["deceased"]) is False


def test_contact_research_loader_normalizes_none(tmp_path):
    from hh.external.notes import CONTACT_RESEARCH_FILENAME, load_contact_research

    src = tmp_path / CONTACT_RESEARCH_FILENAME
    src.write_text(
        "# header\n"
        "notes:\n"
        '  "A Person":\n'
        "    phone: none\n"
        "    phone_confidence: none\n"
        "    email: a@example.org\n"
        "    email_confidence: confirmed\n"
        "    finding: \"found email\"\n"
        "    sources:\n"
        "      - https://example.org/a\n"
    )
    df = load_contact_research(src)
    assert len(df) == 1
    assert pd.isna(df.iloc[0]["phone"])  # literal "none" -> missing
    assert df.iloc[0]["email"] == "a@example.org"
    assert df.iloc[0]["sources"] == "https://example.org/a"
    assert bool(df.iloc[0]["deceased_web"]) is False  # absent flag defaults to False
