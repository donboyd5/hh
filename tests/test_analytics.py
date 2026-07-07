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
