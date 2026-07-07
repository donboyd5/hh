import pandas as pd

from hh.clean.events import clean_events


def test_clean_events_standardizes_and_categorizes():
    raw = pd.DataFrame(
        {
            "Event ID": ["1", "2"],
            "Event Name": ["Hamlet", "Tap Dance Class"],
            "Event Category Name": ["Theater Performances", "Tap Dance"],
            "Event Start Date": ["2024-01-15", "2024-02-20"],
        }
    )
    out = clean_events(raw)
    # API field names -> standard names
    assert "event_id" in out.columns
    assert "category" in out.columns
    assert "starts_on" in out.columns
    # categorizer applied
    assert "event_majorcat" in out.columns
    assert list(out["event_majorcat"]) == ["performance", "class"]
    # date parsing
    assert pd.api.types.is_datetime64_any_dtype(out["starts_on"])


def test_clean_events_handles_missing_optional_columns():
    raw = pd.DataFrame({"Event ID": ["1"], "Event Name": ["Hamlet"]})
    out = clean_events(raw)
    # no category -> NA category falls through to "other" (per R logic), not a crash
    assert list(out["event_majorcat"]) == ["other"]


def test_add_rollup_household_and_account():
    from hh.clean.households import add_rollup

    df = pd.DataFrame(
        {
            "household_id": ["H1", None, None],
            "account_id": ["A1", "A2", None],
            "household_name": ["Smith House", None, None],
            "full_name": [None, "Jane Doe", None],
        }
    )
    out = add_rollup(df)
    assert list(out["group"]) == ["household", "account", "other"]
    assert out["id"][0] == "H1" and out["id"][1] == "A2"
    assert pd.isna(out["id"][2])
    assert out["name"][0] == "Smith House" and out["name"][1] == "Jane Doe"
    assert pd.isna(out["name"][2])


def test_clean_accounts_yes_to_bool_and_rollup():
    from hh.clean.accounts import clean_accounts

    raw = pd.DataFrame(
        {
            "Account ID": ["A1", "A2", "A3"],
            "Account Type": ["Individual", "Individual", "Company"],
            "Full Name (F)": ["Jane Doe", "John Doe", None],
            "Company Name": [None, None, "Acme"],
            "Household ID": ["H1", None, None],
            "Household Name": ["Doe House", None, None],
            "Deceased": ["No", "Yes", None],
            "Do Not Contact": [None, "No", "Yes"],
        }
    )
    out = clean_accounts(raw)
    assert list(out["deceased"]) == [False, True, False]
    assert list(out["do_not_contact"]) == [False, False, True]
    assert list(out["group"]) == ["household", "account", "account"]
    assert list(out["id"]) == ["H1", "A2", "A3"]
    assert list(out["name"]) == ["Doe House", "John Doe", "Acme"]
