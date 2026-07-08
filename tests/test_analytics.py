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
        theater_performances,
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
    perf = theater_performances(regs)
    assert set(perf["production_run"]) == {
        "Fun Home (2023)",
        "Whispering Bones (2018)",
        "Whispering Bones (2024)",
    }
    fri = perf[perf["starts_on"] == pd.Timestamp("2023-02-03")]
    assert fri["attendees"].iloc[0] == 4 and fri["registrations"].iloc[0] == 2

    fw = full_weekend_runs(perf)
    assert set(fw["production_run"]) == {"Fun Home (2023)"}
