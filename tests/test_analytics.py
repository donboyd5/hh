import pandas as pd

from hh.analytics.timing import best_weekday, timing_by_weekday


def test_timing_by_weekday_and_best():
    df = pd.DataFrame(
        {
            "registration_id": ["R1", "R2", "R3"],
            "event_majorcat": ["performance", "performance", "class"],
            "event_minorcat": ["theater", "music", "other"],
            # 2024-01-06=Sat, 2024-01-07=Sun, 2024-01-05=Fri
            "starts_on": pd.to_datetime(["2024-01-06", "2024-01-07", "2024-01-05"]),
            "amount": [10.0, 20.0, 30.0],
        }
    )
    perf = timing_by_weekday(df, category="performance")
    assert set(perf["weekday"]) == {"Saturday", "Sunday"}
    weekday, revenue = best_weekday(df, category="performance", metric="revenue")
    assert weekday == "Sunday" and revenue == 20.0
    # minor filter
    music = timing_by_weekday(df, category="performance", minor="music")
    assert set(music["weekday"]) == {"Sunday"}


def test_donors_by_band():
    from hh.analytics.donors import donors_by_band

    accounts_geo = pd.DataFrame(
        {
            "account_id": ["A1", "A2", "A3", "36805"],
            "household_id": ["H1", "H2", None, None],
            "distance_band": ["<= 1 mi", "> 20 mi", "<= 10 mi", "<= 1 mi"],
            "geo_precision": ["street", "street", "centroid", "street"],
            "deceased": [False, False, False, False],
            "do_not_contact": [False, False, False, False],
        }
    )
    donations = pd.DataFrame(
        {
            "account_id": ["A1", "A1", "A2", "A3", "36805"],
            "account_type": ["Individual"] * 5,
            "donation_type": ["DONATION"] * 5,
            "donation_status": ["SUCCEEDED"] * 5,
            "donation_amount": [100.0, 50.0, 200.0, 75.0, 999.0],
            "donation_id": ["d1", "d2", "d3", "d4", "d5"],
            "household_id": ["H1", "H1", "H2", None, None],
        }
    )
    out = donors_by_band(accounts_geo, donations).set_index("distance_band")
    assert out.loc["<= 1 mi", "total_donations"] == 150.0  # A1 only; junk 36805 excluded
    assert out.loc["<= 10 mi", "total_donations"] == 75.0
    assert out.loc["> 20 mi", "total_donations"] == 200.0
    assert out.loc["<= 1 mi", "donor_households"] == 1
