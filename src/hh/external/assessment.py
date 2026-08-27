"""NYS assessment rolls (RPS "owners name sequence" PDFs) as a mailing-address source.

Washington County publishes each town's final roll as a PDF
(https://www.washingtoncountyny.gov/290/Assessment-Rolls). ``pdftotext -layout`` yields a
fixed-width text where every parcel block starts with a line of asterisks and the parcel
id, and the left column (first ~31 characters) then carries, in order: the owner name
line(s) ("Surname Given [& Given]"), the mailing street, and "City, ST ZIP". The block's
first line holds the property location. :func:`parse_roll` walks those blocks; the
result is one row per parcel with owners and the *mailing* address, which is what a
letter needs (it may differ from the parcel location — seasonal owners, PO boxes).

Rolls are public records but name people, so the PDFs/text stay under gitignored
``data/00_raw/external/assessment/<year>/``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

LEFT_COL = 31
_BLOCK_START = re.compile(r"^\*{10,}\s+(\S+)\s+\*+")
_CITY_LINE = re.compile(r"^(?P<city>[A-Za-z .'-]+),\s+(?P<state>[A-Z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)\s*$")
_PAGE_NOISE = re.compile(r"^(STATE OF NEW YORK|COUNTY -|TOWN\s+-|SWIS\s+-|TAX MAP PARCEL|CURRENT OWNERS|PARCEL SIZE|\s*$)")
_LEFT_NOISE = re.compile(r"^(MAY BE SUBJECT|UNDER AGDIST|UNDER RPTL|PRIOR OWNER|DEED BOOK|FULL MARKET|EAST-|ACRES|FRNT|BANK)", re.I)


def parse_roll(text: str, *, town: str) -> pd.DataFrame:
    """Parcels from one roll's text: ``[town, parcel, location, owners, street, city, state, zip]``."""
    lines = text.splitlines()
    rows = []
    i = 0
    while i < len(lines):
        m = _BLOCK_START.match(lines[i])
        if not m:
            i += 1
            continue
        parcel = m.group(1)
        location = lines[i + 1].strip().split("  ")[0].strip() if i + 1 < len(lines) else ""
        owners: list[str] = []
        street = city = state = zipc = None
        j = i + 3  # skip location line and the parcel-number/class line
        while j < len(lines) and not _BLOCK_START.match(lines[j]):
            left = lines[j][:LEFT_COL].rstrip()
            if _PAGE_NOISE.match(lines[j]) or _LEFT_NOISE.match(left) or not left.strip():
                j += 1
                continue
            cm = _CITY_LINE.match(left.strip())
            if cm:
                city, state, zipc = cm.group("city").strip(), cm.group("state"), cm.group("zip")
                break
            if street is None and re.match(r"^(\d|PO Box|P\.?O\.? Box|Box )", left.strip(), re.I):
                street = left.strip()
            elif street is None:
                owners.append(left.strip())
            else:
                street = f"{street} {left.strip()}"  # second street line (c/o, apt)
            j += 1
        rows.append({"town": town, "parcel": parcel, "location": location,
                     "owners": " | ".join(owners), "street": street, "city": city,
                     "state": state, "zip": zipc})
        i = j if j > i else i + 1
    return pd.DataFrame(rows)


def load_rolls(folder: Path) -> pd.DataFrame:
    """Parse every ``<Town>.txt`` in a roll folder."""
    frames = [parse_roll(p.read_text(errors="replace"), town=p.stem.replace("-", " "))
              for p in sorted(folder.glob("*.txt"))]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# -- matching people to parcel owners ------------------------------------------------
_OWNER_SKIP = {
    "&", "and", "trust", "trustee", "trustees", "life", "estate", "llc", "revocable",
    "irrevocable", "the", "of", "jr", "sr", "ii", "iii", "iv", "etal", "et", "al",
}


def owner_tokens(owner: str) -> list[str]:
    """Lower-cased name tokens of one owner string, legal/suffix noise removed."""
    toks = [t.strip(",.").lower() for t in str(owner).replace("&", " & ").split() if t.strip(",.")]
    return [t for t in toks if t not in _OWNER_SKIP and not t.endswith(".")]


def surname_close(a: str, b: str) -> bool:
    """Same surname allowing common variants and typos, but not truncations.

    Exact; or ratio >= 90 on names of 5+ letters (Greene/Green); or >= 88 on 8+ letters
    (McAullife/McAuliffe — a Fort Salem typo). Ross/Rossi (4 letters) never passes.
    """
    from rapidfuzz import fuzz

    if a == b:
        return True
    n = min(len(a), len(b))
    r = fuzz.ratio(a, b)
    return (n >= 8 and r >= 88) or (n >= 5 and r >= 90)


def match_names_to_owners(
    names: pd.DataFrame,
    parcels: pd.DataFrame,
    *,
    name_col: str = "household_name",
    min_given: float = 85.0,
    max_hits: int = 2,
) -> pd.DataFrame:
    """Best parcel-owner matches per person name, for mailing addresses.

    ``parcels`` rows need ``owners`` (" | "-joined owner strings), ``street``, ``city``,
    ``state``, ``zip``, ``town``, ``source``. NYS rolls list owners "Surname Given", Vermont
    grand lists usually the same but not always — so the surname is tried at either end
    of each owner string. A hit needs :func:`surname_close` plus a given-name agreement
    (``hh.analytics.fst_match.given_score``) of at least ``min_given`` against any given
    name of any owner on the parcel. Up to ``max_hits`` distinct addresses per name, best
    first. Long format: ``[name, given_agreement, owners, street, city, state, zip, town,
    source]``.
    """
    from ..analytics.fst_match import _tokens, given_score

    parsed = [[owner_tokens(o) for o in str(x).split(" | ")] for x in parcels["owners"]]
    rows = []
    for name in names[name_col]:
        fs, fg = _tokens(name)
        fg = [g for g in fg if len(g) > 1]  # initials ("Christopher P") must not match "Paul"
        if not fs or not fg:
            continue
        best: list[tuple[float, int]] = []
        for idx, owners in enumerate(parsed):
            for toks in owners:
                if len(toks) < 2:
                    continue
                for sp in (0, len(toks) - 1):
                    if not surname_close(fs, toks[sp]):
                        continue
                    givens = [t for i, t in enumerate(toks) if i != sp and len(t) > 1]
                    g = max((given_score(a, b) for a in fg for b in givens), default=0.0)
                    if g >= min_given:
                        best.append((g, idx))
                        break
        best.sort(key=lambda t: -t[0])
        seen: set[tuple] = set()
        for g, idx in best:
            p = parcels.iloc[idx]
            key = (p["street"], p["city"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({"name": name, "given_agreement": g, "owners": p["owners"],
                         "street": p["street"], "city": p["city"], "state": p["state"],
                         "zip": p["zip"], "town": p["town"], "source": p["source"]})
            if len(seen) >= max_hits:
                break
    return pd.DataFrame(rows, columns=["name", "given_agreement", "owners", "street", "city",
                                       "state", "zip", "town", "source"])


def vt_parcels_as_rolls(vt: pd.DataFrame) -> pd.DataFrame:
    """VCGI standardized-parcel attributes -> the ``parcels`` shape used by the matcher."""
    v = vt.fillna("")
    return pd.DataFrame({
        "town": v["TNAME"].str.title(),
        "parcel": v["SPAN"],
        "location": v["E911ADDR"],
        "owners": [" | ".join(x for x in (a, b) if x) for a, b in zip(v["OWNER1"], v["OWNER2"])],
        "street": [" ".join(x for x in (a, b) if x).strip() for a, b in zip(v["ADDRGL1"], v["ADDRGL2"])],
        "city": v["CITYGL"].str.title(),
        "state": v["STGL"],
        "zip": v["ZIPGL"].astype(str).str[:5],
        "source": "VT grand list 2025 (VCGI parcels)",
    })
