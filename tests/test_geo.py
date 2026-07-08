import pandas as pd

from hh.geo.distance import assign_bands, band_label, band_series, haversine


def test_haversine_same_point_zero():
    assert haversine(43.0, -73.4, 43.0, -73.4) == 0.0


def test_haversine_cambridge_to_albany():
    # Cambridge NY -> Albany NY is ~30 miles
    d = haversine(43.028, -73.380, 42.6526, -73.7562)
    assert 25 < d < 40


def test_band_labels():
    assert band_label(0.5) == "[0, 1)"
    assert band_label(4.9) == "[1, 5)"
    assert band_label(5) == "[5, 10)"  # boundary -> half-open next band
    assert band_label(15) == "[10, 20)"
    assert band_label(50) == "[20, ∞)"
    assert band_label(None) is None


def test_band_series_order():
    s = pd.Series([0.5, 5, 15, 50, None])
    out = list(band_series(s))
    assert [str(x) for x in out[:4]] == ["[0, 1)", "[5, 10)", "[10, 20)", "[20, ∞)"]
    assert pd.isna(out[4])


def test_assign_bands():
    # venue + ~3mi + ~7mi + ~15mi + NYC(~200mi)
    df = pd.DataFrame(
        {
            "lat": [43.028, 43.0715, 43.1294, 43.2454, 40.7128],
            "lon": [-73.380, -73.380, -73.380, -73.380, -74.0060],
        }
    )
    out = assign_bands(df, venue_lat=43.028, venue_lon=-73.380)
    bands = [str(x) for x in out["distance_band"]]
    assert bands == ["[0, 1)", "[1, 5)", "[5, 10)", "[10, 20)", "[20, ∞)"]
