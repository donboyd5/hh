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
