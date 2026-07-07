import pandas as pd

from hh.geo.distance import assign_bands, band_label, band_series, haversine


def test_haversine_same_point_zero():
    assert haversine(43.0, -73.4, 43.0, -73.4) == 0.0


def test_haversine_cambridge_to_albany():
    # Cambridge NY -> Albany NY is ~30 miles
    d = haversine(43.028, -73.380, 42.6526, -73.7562)
    assert 25 < d < 40


def test_band_labels():
    assert band_label(0.5) == "<= 1 mi"
    assert band_label(5) == "<= 10 mi"
    assert band_label(15) == "<= 20 mi"
    assert band_label(50) == "> 20 mi"
    assert band_label(None) is None


def test_band_series_order():
    s = pd.Series([0.5, 5, 15, 50, None])
    out = list(band_series(s))
    assert [str(x) for x in out[:4]] == ["<= 1 mi", "<= 10 mi", "<= 20 mi", "> 20 mi"]
    assert pd.isna(out[4])


def test_assign_bands():
    # venue = Cambridge NY; near ~5mi; Albany ~32mi; NYC ~200mi
    df = pd.DataFrame(
        {"lat": [43.028, 43.10, 42.6526, 40.7128], "lon": [-73.380, -73.380, -73.7562, -74.0060]}
    )
    out = assign_bands(df, venue_lat=43.028, venue_lon=-73.380)
    bands = [str(x) for x in out["distance_band"]]
    assert bands == ["<= 1 mi", "<= 10 mi", "> 20 mi", "> 20 mi"]
