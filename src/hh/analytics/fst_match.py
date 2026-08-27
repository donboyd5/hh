"""Fuzzy matching of Fort Salem sponsor names to Neon households, for human review.

Exact-name matching (``hh.external.mailing.match_households``) misses real people whenever
Fort Salem's casual listing differs from Neon's household label: nicknames ("Rich" /
"Richard"), partner order ("Kyle & Jared" / "Jared and Kyle"), one partner listed alone
("Tara Smith" for "John & Tara Smith"), maiden or compound names ("Amy Wise Foster"), and
plain typos. This module scores every Fort Salem name against every Neon household and
member account name and reports the close candidates — it never merges. Don confirms or
rejects each on the ``fst-candidates`` sheet of the mailing-list workbook.

Scoring (0–100): the surname must be close (rapidfuzz ratio ≥ 80), then the best
given-name agreement across all partners on either side — exact or known nickname 100,
shared 3-letter prefix 85, otherwise the string ratio. ``score`` is the weighted mean
(surname 40%, given 60%): a shared surname alone is weak evidence in a small town.
"""
from __future__ import annotations

import re

import pandas as pd
from rapidfuzz import fuzz

MIN_SURNAME = 80  # surname ratio below this: not a candidate at all
MIN_SCORE = 78  # report candidates at or above this
MAX_CANDIDATES = 3  # per Fort Salem name
AUTO_FILL_SCORE = 92  # unique candidate at/above this fills fst_candidate_* on the main sheet

_STOP = {"&", "and", "the", "family", "dr", "mr", "mrs", "ms"}

# canonical -> nicknames; both directions are treated as the same person
_NICKNAMES = {
    "robert": {"bob", "rob", "bobby", "robbie"},
    "richard": {"rich", "rick", "dick", "richie"},
    "william": {"bill", "will", "billy", "willie"},
    "james": {"jim", "jimmy", "jamie"},
    "john": {"jack", "johnny"},
    "michael": {"mike", "mick"},
    "thomas": {"tom", "tommy"},
    "edward": {"ed", "eddie", "ted", "ned"},
    "daniel": {"dan", "danny"},
    "david": {"dave"},
    "donald": {"don", "donnie"},
    "charles": {"charlie", "chuck", "chas"},
    "joseph": {"joe", "joey"},
    "anthony": {"tony"},
    "kenneth": {"ken", "kenny"},
    "timothy": {"tim"},
    "christopher": {"chris"},
    "matthew": {"matt"},
    "andrew": {"andy", "drew"},
    "stephen": {"steve"},
    "steven": {"steve"},
    "patrick": {"pat", "paddy"},
    "patricia": {"pat", "patty", "trish", "tricia"},
    "elizabeth": {"liz", "beth", "betsy", "betty", "eliza", "lizzie"},
    "katherine": {"kathy", "kate", "katie", "kat", "kay"},
    "catherine": {"cathy", "cate", "kate", "katie"},
    "kathleen": {"kathy", "kate", "katie"},
    "margaret": {"peggy", "meg", "maggie", "marge", "margie"},
    "susan": {"sue", "susie", "suzy"},
    "deborah": {"deb", "debbie"},
    "barbara": {"barb", "barbie"},
    "jennifer": {"jen", "jenny"},
    "rebecca": {"becky", "becca"},
    "christine": {"chris", "christie", "chrissy"},
    "christina": {"chris", "christie", "tina"},
    "cynthia": {"cindy"},
    "nancy": {"nan"},
    "judith": {"judy"},
    "dorothy": {"dot", "dottie"},
    "virginia": {"ginny"},
    "victoria": {"vicki", "vicky"},
    "samantha": {"sam"},
    "samuel": {"sam"},
    "alexander": {"alex"},
    "alexandra": {"alex"},
    "benjamin": {"ben"},
    "jonathan": {"jon"},
    "lawrence": {"larry"},
    "gerald": {"gerry", "jerry"},
    "jerome": {"jerry"},
    "ronald": {"ron"},
    "raymond": {"ray"},
    "frederick": {"fred"},
    "gregory": {"greg"},
    "peter": {"pete"},
    "nicholas": {"nick"},
    "leonard": {"len", "lenny"},
    "douglas": {"doug"},
    "harold": {"hal", "harry"},
    "abigail": {"abby"},
    "carolyn": {"carol"},
    "eleanor": {"ellie", "nora"},
    "florence": {"flo"},
}
_ALIAS: dict[str, str] = {}
for canon, nicks in _NICKNAMES.items():
    _ALIAS[canon] = canon
    for n in nicks:
        _ALIAS.setdefault(n, canon)


def _tokens(name: str) -> tuple[str | None, list[str]]:
    """(surname, given names) from a person or household label, lowercased."""
    s = re.sub(r"\(.*?\)", "", str(name)).lower()
    toks = [t.strip(",.") for t in s.split() if t.strip(",.")]
    if len(toks) < 2:
        return None, []
    return toks[-1], [t for t in toks[:-1] if t not in _STOP]


def given_score(a: str, b: str) -> float:
    """Agreement between two given names (0–100)."""
    if a == b or _ALIAS.get(a, a) == _ALIAS.get(b, b):
        return 100.0
    if a[:3] == b[:3] or a.startswith(b) or b.startswith(a):
        return 85.0
    return float(fuzz.ratio(a, b))


def score_pair(fst_name: str, neon_name: str) -> tuple[float, float, float]:
    """(score, surname_ratio, given_agreement) for one Fort Salem / Neon name pair."""
    fs, fg = _tokens(fst_name)
    ns, ng = _tokens(neon_name)
    if not fs or not ns or not fg or not ng:
        return 0.0, 0.0, 0.0
    surname = float(fuzz.ratio(fs, ns))
    if surname < MIN_SURNAME:
        return 0.0, surname, 0.0
    given = max(given_score(a, b) for a in fg for b in ng)
    return round(0.4 * surname + 0.6 * given, 1), surname, given


def _neon_name_pool(accounts: pd.DataFrame) -> pd.DataFrame:
    """One row per (household id, name string) over household labels and member names."""
    a = accounts if "city" in accounts.columns else accounts.assign(city=pd.NA)
    hh = a.drop_duplicates(subset=["id"])[["id", "name", "city"]]
    labels = hh.rename(columns={"name": "candidate_name"}).assign(kind="household")
    members = a[a["full_name"].notna()][["id", "full_name", "city"]].rename(
        columns={"full_name": "candidate_name"}
    ).assign(kind="member")
    pool = pd.concat([labels, members], ignore_index=True).dropna(subset=["candidate_name"])
    pool["label"] = pool["id"].map(dict(zip(hh["id"], hh["name"], strict=True)))
    return pool.drop_duplicates(subset=["id", "candidate_name"])


def fuzzy_fst_candidates(
    fst_summary: pd.DataFrame,
    accounts: pd.DataFrame,
    *,
    min_score: float = MIN_SCORE,
    max_candidates: int = MAX_CANDIDATES,
) -> pd.DataFrame:
    """Close Neon candidates for every Fort Salem name lacking an exact match.

    Long format, best first within each name:
    ``[fst_name, fst_best_tier, fst_years, rank, score, surname_ratio, given_agreement,
    matched_via, neon_hh_id, neon_household, neon_city]``. Names with no candidate at or
    above ``min_score`` are absent (they are the genuine "not in Neon" pool).
    """
    pool = _neon_name_pool(accounts)
    pool_tokens = [_tokens(n) for n in pool["candidate_name"]]
    exact = fst_summary["in_neon"].fillna(False).astype(bool) if "in_neon" in fst_summary else None

    rows = []
    for i, r in enumerate(fst_summary.itertuples(index=False)):
        if exact is not None and bool(exact.iloc[i]):
            continue
        fs, fg = _tokens(r.name)
        if not fs or not fg:
            continue
        best: dict[str, tuple] = {}  # neon id -> best (score, surname, given, via)
        for (ns, ng), cand in zip(pool_tokens, pool.itertuples(index=False), strict=True):
            if not ns or not ng:
                continue
            surname = float(fuzz.ratio(fs, ns))
            if surname < MIN_SURNAME:
                continue
            given = max(given_score(a, b) for a in fg for b in ng)
            score = round(0.4 * surname + 0.6 * given, 1)
            if score < min_score:
                continue
            prev = best.get(cand.id)
            if prev is None or score > prev[0]:
                best[cand.id] = (score, surname, given, cand.candidate_name, cand.label, cand.city)
        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])[:max_candidates]
        for rank, (hh_id, (score, surname, given, via, label, city)) in enumerate(ranked, 1):
            rows.append(
                {
                    "fst_name": r.name,
                    "fst_best_tier": getattr(r, "best_tier", None),
                    "fst_years": getattr(r, "years", None),
                    "rank": rank,
                    "score": score,
                    "surname_ratio": surname,
                    "given_agreement": given,
                    "matched_via": via,
                    "neon_hh_id": hh_id,
                    "neon_household": label,
                    "neon_city": city,
                }
            )
    return pd.DataFrame(
        rows,
        columns=[
            "fst_name", "fst_best_tier", "fst_years", "rank", "score", "surname_ratio",
            "given_agreement", "matched_via", "neon_hh_id", "neon_household", "neon_city",
        ],
    )


def auto_candidates(review: pd.DataFrame, *, min_score: float = AUTO_FILL_SCORE) -> pd.DataFrame:
    """The single strong candidate per name (rank 1 at/above ``min_score`` with no rank 2
    at/above it) -> ``[name, fst_candidate_id, fst_candidate_name]`` for the main sheet."""
    if review.empty:
        return pd.DataFrame(columns=["name", "fst_candidate_id", "fst_candidate_name"])
    strong = review[review["score"] >= min_score]
    counts = strong.groupby("fst_name").size()
    unique = strong[strong["fst_name"].map(counts) == 1]
    return unique.rename(
        columns={"fst_name": "name", "neon_hh_id": "fst_candidate_id",
                 "neon_household": "fst_candidate_name"}
    )[["name", "fst_candidate_id", "fst_candidate_name"]].reset_index(drop=True)
