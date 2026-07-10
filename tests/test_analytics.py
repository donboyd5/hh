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


def test_enrich_registrations_adds_band_and_weekday():
    from hh.analytics.registrations_enriched import enrich_registrations

    reg = pd.DataFrame(
        {
            "registration_id": ["R1"],
            "account_id": ["A1"],
            "starts_on": pd.to_datetime(["2024-01-06"]),  # Saturday
        }
    )
    ag = pd.DataFrame(
        {
            "account_id": ["A1"],
            "distance_band": ["<= 1 mi"],
            "geo_precision": ["street"],
        }
    )
    out = enrich_registrations(reg, ag)
    assert str(out["distance_band"].iloc[0]) == "<= 1 mi"
    assert str(out["weekday"].iloc[0]) == "Saturday"


def test_household_summary_flags_and_counts():
    from hh.analytics.households import household_summary

    ag = pd.DataFrame(
        {
            "id": ["H1", "H1", "A2"],
            "account_id": ["A1", "A1b", "A2"],
            "name": ["X", "X", "Y"],
            "group": ["household", "household", "account"],
            "distance_band": ["<= 1 mi", "<= 1 mi", "> 20 mi"],
            "geo_precision": ["street", "street", "street"],
            "city": ["c", "c", "d"],
            "state_province": ["NY", "NY", "NY"],
            "zip_code": ["1", "1", "2"],
        }
    )
    don = pd.DataFrame(
        {
            "id": ["H1", "A2"],
            "account_id": ["A1", "A2"],
            "account_type": ["Individual", "Individual"],
            "donation_type": ["DONATION", "DONATION"],
            "donation_status": ["SUCCEEDED", "SUCCEEDED"],
            "donation_amount": [100.0, 50.0],
            "donation_id": ["d1", "d2"],
            "donation_date": pd.to_datetime(["2024-01-01", "2024-02-01"]),
        }
    )
    reg = pd.DataFrame(
        {
            "id": ["H1", "A2"],
            "account_id": ["A1", "A2"],
            "registration_id": ["r1", "r2"],
            "event_majorcat": ["class", "performance"],
            "event_minorcat": ["other", "theater"],
        }
    )
    h = household_summary(ag, don, reg).set_index("id")
    assert h.loc["H1", "total_donations"] == 100.0
    assert h.loc["H1", "n_class"] == 1
    assert bool(h.loc["H1", "is_donor"]) and bool(h.loc["H1", "is_class_taker"])
    assert h.loc["A2", "n_perf_theater"] == 1
    assert bool(h.loc["A2", "is_patron"])


def test_theater_productions_mapping_and_runs():
    from hh.analytics.productions import (
        count_succeeded_attendees,
        full_weekend_runs,
        is_excluded,
        match_production,
        production_performances,
        time_slot,
    )

    assert match_production("Theater: Ondine - Friday, November 15") == "Ondine"
    assert match_production("Fun Home - Saturday, February 4 at 7:30 pm") == "Fun Home"
    assert match_production("Some Brand New Show") is None
    assert is_excluded("The Mystery of Edwin Drood - Sat.Nov.25.7:30pm - Cancelled")
    assert is_excluded("The Mystery of Edwin Drood - Tues. Nov 21 at 10am")
    assert not is_excluded("The Mystery of Edwin Drood - Sun.Nov.26.2pm")
    assert time_slot("Fun Home - Saturday, February 4 - 2:00 pm Matinee") == "matinee"
    assert time_slot("Fun Home - Saturday, February 4 at 7:30 pm") == "evening"

    tickets = [
        {"attendees": [{"registrationStatus": "SUCCEEDED"}, {"registrationStatus": "CANCELED"}]},
        {"attendees": None},
    ]
    assert count_succeeded_attendees(tickets) == 1
    assert count_succeeded_attendees(None) == 0

    # Two Whispering Bones nights a year apart split into separate runs; only the run
    # covering Fri+Sat+Sun qualifies as a full-weekend run.
    def reg(rid, eid, name, date):
        return {
            "registration_id": rid,
            "swept_event_id": eid,
            "event_name": name,
            "starts_on": pd.Timestamp(date),
            "event_majorcat": "performance",
            "event_minorcat": "theater",
            "tickets": [{"attendees": [{"registrationStatus": "SUCCEEDED"}] * 2}],
        }

    regs = pd.DataFrame(
        [
            reg("r1", "e1", "Fun Home - Friday, February 3 at 7:30 pm", "2023-02-03"),
            reg("r2", "e2", "Fun Home - Saturday, February 4 at 7:30 pm", "2023-02-04"),
            reg("r3", "e3", "Fun Home - Sunday, February 5 - 2:00 pm Matinee", "2023-02-05"),
            reg("r4", "e4", "Whispering Bones - Saturday, October 27th at 7:30pm", "2018-10-27"),
            reg("r5", "e5", "Whispering Bones - Ghost Stories - Sat, October 26", "2024-10-26"),
            reg("r6", "e1", "Fun Home - Friday, February 3 at 7:30 pm", "2023-02-03"),
        ]
    )
    perf = production_performances(regs)
    assert set(perf["production_run"]) == {
        "Fun Home (2023)",
        "Whispering Bones (2018)",
        "Whispering Bones (2024)",
    }
    fri = perf[perf["starts_on"] == pd.Timestamp("2023-02-03")]
    assert fri["attendees"].iloc[0] == 4 and fri["registrations"].iloc[0] == 2

    fw = full_weekend_runs(perf)
    assert set(fw["production_run"]) == {"Fun Home (2023)"}


def test_opera_music_mapping():
    from hh.analytics.productions import (
        is_excluded,
        match_production,
        production_performances,
        unmatched_events,
    )

    assert match_production("Opera: Rigoletto - August 14 at 8pm") == "Rigoletto (opera)"
    assert match_production("Wayward Home - A Musical Folktale (Sat 2pm)") == (
        "Wayward Home - A Musical Folktale"
    )
    # one-off concerts are intentionally unmatched
    assert match_production("Music from Salem Concert: Baroque") is None
    # rehearsal-type opera events are excluded
    assert is_excluded("Opera: Rigoletto - August 12 at 8pm PWYW REHEARSAL")
    assert is_excluded("Opera: Dress Rehearsal Performance, Marriage of Figaro")
    assert is_excluded("Special Event: A Day at the Opera, August 15")

    def reg(rid, eid, name, cat, date):
        return {
            "registration_id": rid,
            "swept_event_id": eid,
            "event_name": name,
            "starts_on": pd.Timestamp(date),
            "event_majorcat": "performance",
            "event_minorcat": cat,
            "tickets": [{"attendees": [{"registrationStatus": "SUCCEEDED"}]}],
        }

    regs = pd.DataFrame(
        [
            reg("r1", "e1", "Opera: Rigoletto - August 14 at 8pm", "opera", "2015-08-14"),
            reg("r2", "e2", "Music from Salem Concert: Baroque", "music", "2014-01-04"),
        ]
    )
    perf = production_performances(regs, minorcats=("music", "opera"))
    assert set(perf["production_run"]) == {"Rigoletto (opera) (2015)"}
    assert unmatched_events(regs, ("music", "opera")) == ["Music from Salem Concert: Baroque"]


def _gifts(extra=None):
    """Succeeded individual gifts with the household rollup `id` (as clean_donations yields)."""
    base = pd.DataFrame(
        {
            "donation_id": ["g1", "g2", "g3", "g4", "g5"],
            "id": ["H1", "H1", "H2", "H2", "H3"],
            "account_id": ["A1", "A1", "A2", "A2", "A3"],
            "account_type": ["Individual"] * 5,
            "donation_type": ["DONATION"] * 5,
            "donation_status": ["SUCCEEDED"] * 5,
            "donation_amount": [50.0, 1200.0, 30.0, 30.0, 6000.0],
            "donation_date": pd.to_datetime(
                ["2023-05-01", "2024-06-01", "2023-07-01", "2024-07-01", "2023-09-01"]
            ),
        }
    )
    return base


def test_size_tier_boundaries():
    from hh.analytics.donors import size_tier, TIER_LABELS

    assert size_tier(0) == "<$100"
    assert size_tier(99.99) == "<$100"
    assert size_tier(100) == "$100–999"
    assert size_tier(999.99) == "$100–999"
    assert size_tier(1000) == "$1,000–4,999"
    assert size_tier(4999.99) == "$1,000–4,999"
    assert size_tier(5000) == "$5,000+"
    assert size_tier(1_000_000) == "$5,000+"
    # tier labels stay in display order
    assert TIER_LABELS == ["<$100", "$100–999", "$1,000–4,999", "$5,000+"]


def test_annual_gifts_and_reconciliation():
    from hh.analytics.donors import annual_gifts, succeeded_individual_gifts

    raw = _gifts()
    ag = annual_gifts(raw)
    # all 5 succeeded individual gifts survive, with an integer year column
    assert len(ag) == 5
    assert {"id", "year", "donation_amount"} <= set(ag.columns)
    # annual_gifts total reconciles with succeeded_individual_gifts total
    assert ag["donation_amount"].sum() == succeeded_individual_gifts(raw)["donation_amount"].sum()


def test_donors_by_size_year():
    from hh.analytics.donors import annual_gifts, donors_by_size_year, TIER_LABELS

    out = donors_by_size_year(annual_gifts(_gifts()))
    # H1: 2023=$50 (<$100), 2024=$1200 ($1,000–4,999); H2: 2023=$30, 2024=$30 (both <$100);
    # H3: 2023=$6000 ($5,000+)
    row = out.set_index(["year", "tier"]).sort_index()
    assert row.loc[(2023, "<$100"), "donors"] == 2          # H1 + H2
    assert row.loc[(2023, "<$100"), "dollars"] == 80.0
    assert row.loc[(2023, "$5,000+"), "donors"] == 1        # H3
    assert row.loc[(2024, "$1,000–4,999"), "donors"] == 1   # H1
    assert row.loc[(2024, "$1,000–4,999"), "dollars"] == 1200.0
    # every tier label is a known one
    assert set(out["tier"]).issubset(set(TIER_LABELS))


def test_donors_above_threshold_by_year():
    from hh.analytics.donors import annual_gifts, donors_above_threshold_by_year

    big = donors_above_threshold_by_year(annual_gifts(_gifts()), min_amount=1000).set_index("year")
    assert big.loc[2023, "donors"] == 1   # H3 ($6000)
    assert big.loc[2024, "donors"] == 1   # H1 ($1200)
    assert 2022 not in big.index


def test_donor_retention():
    from hh.analytics.donors import annual_gifts, donor_retention

    ret = donor_retention(annual_gifts(_gifts())).set_index("year")
    # H1 active in both 2023 and 2024 -> retained; H2 active in both -> retained; H3 only 2023
    # so 2023 active=3, returned=2 -> 2/3
    assert ret.loc[2023, "active"] == 3
    assert ret.loc[2023, "returned_next_year"] == 2
    assert abs(ret.loc[2023, "retention"] - 2 / 3) < 1e-9
    # final year (2024) is dropped — no next year
    assert 2024 not in ret.index
