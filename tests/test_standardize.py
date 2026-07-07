import pandas as pd

from hh.clean.standardize import standardize_columns, vmap


def test_vmap_basic():
    assert vmap("Full Name") == "full_name"
    assert vmap("Account ID") == "account_id"


def test_vmap_phone_and_line_collapse():
    assert vmap("Phone 2") == "phone2"
    assert vmap("Address Line 1") == "address_line1"


def test_vmap_suffix_removal():
    assert vmap("Email (c)") == "email"
    assert vmap("Donor (f)") == "donor"


def test_vmap_slash_and_punct():
    assert vmap("State/Province") == "state_province"
    assert vmap("Zip? Code.") == "zip_code"


def test_standardize_columns_uses_mapping_then_vmap():
    df = pd.DataFrame({"Full Name": ["x"], "Foo Bar": ["y"]})
    out = standardize_columns(df, mapping={"Full Name": "full_name"})
    assert "full_name" in out.columns
    assert "foo_bar" in out.columns


def test_standardize_columns_uses_config_fieldmap_by_default():
    df = pd.DataFrame({"Category": ["x"], "Event Name": ["y"], "Random Thing": ["z"]})
    out = standardize_columns(df)
    assert "category" in out.columns
    assert "event_name" in out.columns
    assert "random_thing" in out.columns
