from datetime import date

import pandas as pd

from hh.utils import hhfy, ns


def test_hhfy_single_date():
    assert hhfy(date(2024, 6, 30)) == 2024
    assert hhfy(date(2024, 7, 1)) == 2025
    assert hhfy(date(2024, 12, 31)) == 2025


def test_hhfy_series():
    s = pd.to_datetime(pd.Series(["2024-06-30", "2024-07-01", "2024-12-31"]))
    assert list(hhfy(s)) == [2024, 2025, 2025]


def test_hhfy_custom_start_month():
    assert hhfy(date(2024, 9, 1), start_month=10) == 2024
    assert hhfy(date(2024, 10, 1), start_month=10) == 2025


def test_ns_returns_df_unchanged(capsys):
    df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
    out = ns(df)
    pd.testing.assert_frame_equal(out, df)
    assert "rows x 2 cols" in capsys.readouterr().out
