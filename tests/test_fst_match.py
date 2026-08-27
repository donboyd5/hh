"""Fuzzy Fort Salem -> Neon candidate scoring (synthetic frames)."""
import pandas as pd

from hh.analytics.fst_match import (
    auto_candidates,
    fuzzy_fst_candidates,
    given_score,
    score_pair,
)


def test_given_score_nicknames_prefixes_and_strangers():
    assert given_score("rich", "richard") == 100.0
    assert given_score("bob", "robert") == 100.0
    assert given_score("kathy", "katherine") == 100.0
    assert given_score("christie", "christine") == 100.0  # listed nickname
    assert given_score("dave", "davis") == 85.0  # shared prefix only
    assert given_score("anne", "diane") < 85.0


def test_score_pair_partner_order_and_single_partner():
    score, surname, given = score_pair("Kyle & Jared West", "Jared and Kyle West")
    assert (score, surname, given) == (100.0, 100.0, 100.0)
    score, _, _ = score_pair("Tara Smith", "Scott & Tara Smith")
    assert score == 100.0
    score, _, _ = score_pair("Tara Smith", "Scott Smyth")  # surname close, given unrelated
    assert score < 78
    assert score_pair("Tara Smith", "Tara Jones")[0] == 0.0  # surname too far: not a candidate


def _accounts():
    return pd.DataFrame(
        {
            "id": ["H1", "H1", "H2", "H3", "H4"],
            "name": ["Jared and Kyle West"] * 2 + ["Rich Butler", "Jennifer Shaw", "Pat Doe"],
            "full_name": ["Jared West", "Kyle West", "Rich Butler", "Jennifer Shaw", "Pat Doe"],
            "city": ["Salem"] * 2 + ["Cambridge", "Eagle Bridge", "Salem"],
        }
    )


def test_fuzzy_candidates_rank_and_auto_fill():
    fst = pd.DataFrame(
        {
            "name": ["Kyle & Jared West", "Richard Butler", "Jennie Shaw", "Sue Doe", "Pat Doe"],
            "best_tier": ["gold"] * 5,
            "years": ["2024"] * 5,
            "in_neon": [False, False, False, False, True],
        }
    )
    review = fuzzy_fst_candidates(fst, _accounts())
    top = review[review["rank"] == 1].set_index("fst_name")
    assert top.loc["Kyle & Jared West", "neon_hh_id"] == "H1"
    assert top.loc["Kyle & Jared West", "score"] == 100.0
    assert top.loc["Richard Butler", "neon_hh_id"] == "H2"  # nickname
    assert 85 <= top.loc["Jennie Shaw", "score"] < 92  # probable, needs a look
    assert "Sue Doe" not in top.index  # surname matches, given unrelated -> not a candidate
    assert "Pat Doe" not in top.index  # exact match already; no candidate needed
    auto = auto_candidates(review).set_index("name")
    assert set(auto.index) == {"Kyle & Jared West", "Richard Butler"}  # 92+ only
    assert auto.loc["Richard Butler", "fst_candidate_name"] == "Rich Butler"
