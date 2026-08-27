"""Fort Salem sponsor scraper (synthetic HTML exercising both page layouts and quirks)."""
import pandas as pd

from hh.external.fortsalem import (
    is_anonymous,
    likely_org,
    parse_sponsors,
    summarize_sponsors,
)

# recent-years layout: strong tier headings + <em> name blocks (no comma between ems)
_RECENT = """
<h2>2024 Sponsors:</h2>
<p>(Donors $20 &amp; Above)</p>
<strong>2024 Platinum Sponsors</strong>
<em>New York State Council on the Arts</em><em>Kyle &amp; Jared West</em>
<strong>2024 Friends of Fort Salem Sponsors ($20-$99)</strong>
<em>Sue Smith, Your Name Here, (anonymous)</em>
"""

# 2021/2020 layout: tiers and comma-separated names inside plain paragraphs
_OLD = """
<h2>2022 Sponsors:</h2>
<p>2021 Gold Sponsors ($5,000-$14,999) Anonymous Family Fund, Bob &amp; Carolyn Akland</p>
<p>2020 OPENING ANGELS: Andy Albrecht, The Astrowsky Family</p>
"""

# the final section carries a footer that glues onto the last name
_FOOTER = " Fort Salem Theater | Copyright 2025 Fort Salem Theater productions are made possible."


def test_parse_both_layouts_years_tiers_names():
    df = parse_sponsors(_RECENT + _OLD + _FOOTER)
    got = {(r.year, r.tier, r.name) for r in df.itertuples()}
    assert (2024, "platinum", "New York State Council on the Arts") in got
    assert (2024, "platinum", "Kyle & Jared West") in got  # em boundary splits names
    assert (2024, "friends of fort salem", "Sue Smith") in got
    assert (2024, "friends of fort salem", "Your Name Here") not in got
    assert (2021, "gold", "Bob & Carolyn Akland") in got
    assert (2020, "opening angels", "Andy Albrecht") in got  # heading year beats section typo
    # footer text must not survive into names
    assert not any("Copyright" in n or "productions" in n for n in df["name"])


def test_price_range_not_split_into_names():
    df = parse_sponsors(_RECENT)
    non_anon = [n for n in df["name"] if not is_anonymous(n)]
    assert not any(
        n.startswith("(") or "$" in n or n.isdigit() for n in non_anon
    ), df["name"].tolist()


def test_summarize_collapses_years_and_best_tier():
    df = pd.DataFrame(
        [
            {"year": 2023, "tier": "inner circle", "name": "Dan Snyder"},
            {"year": 2024, "tier": "bronze", "name": "Dan Snyder"},
            {"year": 2025, "tier": "friends of fort salem", "name": "Dan Snyder"},
            {"year": 2024, "tier": "gold", "name": "Anonymous Family Fund"},
        ]
    )
    out = summarize_sponsors(df).set_index("name")
    assert out.loc["Dan Snyder", "n_years"] == 3
    assert out.loc["Dan Snyder", "years"] == "2023,2024,2025"
    assert out.loc["Dan Snyder", "best_tier"] == "bronze"
    assert bool(out.loc["Anonymous Family Fund", "org"]) is True


def test_anonymous_and_org_flags():
    assert is_anonymous("(anonymous)") and is_anonymous("Anonymous Family Fund")
    assert not is_anonymous("Sue Smith")
    assert likely_org("Salem Farm Supply") and likely_org("Glens Falls National Bank")
    assert not likely_org("Lindsey Yarborough")
    assert not likely_org("Elizabeth Skinner")  # 'inn' must not match inside 'Skinner'
