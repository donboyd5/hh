"""Fort Salem Theater individual sponsors (fortsalem.com/our-sponsors) — external prospect pool.

Fort Salem is a nearby theater whose individual sponsors are plausible Hubbard Hall prospects
(meta-docs/create_list.md). The page lists sponsors by year (2020–2025) and tier (Platinum
$15,000+ down to Friends $20+); we take every tier and trim later with Don.

Structure as scraped (Squarespace): ``<h2>YYYY Sponsors:</h2>`` sections. The recent years
mark tiers with ``<strong>`` sub-headings and names in ``<em>`` blocks; 2021 and 2020 pack
tiers and comma-separated names into plain ``<p>`` text. The parser therefore flattens each
section to text and splits on the ``YYYY <Tier> Sponsors`` headings, which handles both
layouts. Quirks handled explicitly:

- the page's final section is headed ``2022 Sponsors:`` but its tiers say 2020 — it is the
  2020 list (Founding Sponsors / Opening Angels), so each tier heading's own year wins over
  the section heading;
- tier price ranges ("($500-$1,999)") contain commas, so they are stripped from the front
  of a tier's names rather than split apart;
- ``Your Name Here`` placeholder names, blank comma-splits, and HTML entities.

The HTML snapshot is cached under ``data/30_external/`` with a sha256 provenance entry, so
the parse is reproducible offline and a page change leaves a manifest trail. Names of real
people make this local-only, like the other external sources.
"""
from __future__ import annotations

import html as html_lib
import re
from pathlib import Path

import httpx
import pandas as pd

from .. import config
from .provenance import append_external_manifest, external_source_entry

FST_SPONSORS_URL = "https://www.fortsalem.com/our-sponsors"
SNAPSHOT_FILENAME = "fortsalem-our-sponsors.html"

# tier (as parsed) -> rank for "highest tier reached" (2020's special categories rank as
# top-level commitments: Founding created the theater; Opening Angels backed its reopening)
TIER_RANK = {
    "founding": 7,
    "opening angels": 6,
    "platinum": 6,
    "gold": 5,
    "silver": 4,
    "bronze": 3,
    "inner circle": 2,
    "friends of fort salem": 1,
}

# word-boundary markers for organizations (businesses, foundations, agencies). Sponsors
# matching these are flagged, not dropped — Don's spec wants individuals, so the mailing
# list filters on the flag and anything unclear goes to the review list, not guessed.
_ORG_MARKERS = (
    "foundation", "fund", "council", "realty", "supply", "staples", "bank", "trust",
    "llc", "llp", "inc", "ltd", "group", "assoc", "society", "company", "agency",
    "theatre", "theater", "church", "school", "pharmacy", "market", "garage", "clinic",
    "energy", "insurance", "wellness", "studio", "inn", "store", "shoppe", "grille",
    "cafe", "café", "lodge", "construction", "services", "enterprises", "productions",
)
_ORG_PATTERN = re.compile(
    r"\b(" + "|".join(_ORG_MARKERS) + r")\b", re.IGNORECASE
)

# listings are people/couple names; anything much longer is page junk that slipped through
_MAX_NAME_LEN = 60

_PLACEHOLDER_NAMES = {"your name here"}

_H2_YEAR = re.compile(r"<h2[^>]*>\s*(\d{4})\s+Sponsors:\s*</h2>", re.S)
# "2025 Platinum Sponsors ($15,000+)", "2020 FOUNDING SPONSORS:", "2020 OPENING ANGELS:"
_TIER_HEADING = re.compile(
    r"(\d{4})\s+([A-Za-z][A-Za-z ]*?)\s+(?:SPONSORS|Sponsors?|ANGELS)\b\s*:?\s*"
)
# a tier's price range ("($500-$1,999)") is *not* part of the heading match — it contains
# commas, so it stripped from the front of the names text instead of being split apart
_PRICE_RANGE = re.compile(r"^\s*\([^)]*\)\s*")
_TAG = re.compile(r"<[^>]+>")
# style/script bodies carry CSS text that flattening would smear into the last section's names
_STYLE_OR_SCRIPT = re.compile(r"<(style|script)[^>]*>.*?</\1>", re.S)
# adjacent <em> name blocks have no separator between them — flatten the closing tag to a
# comma so "…Council on the Arts</em> <em>Kyle &…" becomes two names, not one merged one
_EM_CLOSE = re.compile(r"</em\s*>", re.I)
# the site footer glues onto the final section's last real name ("…Lindsey Yarborough Fort
# Salem Theater | Copyright 2025…"); cut it so the name survives name-length cleaning
_FOOTER = re.compile(r"\s*Fort Salem Theater\s*\|\s*Copyright\b.*$", re.I)


def snapshot_path() -> Path:
    return config.layer_dir("external") / SNAPSHOT_FILENAME


def fetch_snapshot(*, force: bool = False, timeout: int = 30) -> Path:
    """Save the sponsors page to the external layer (kept if present unless ``force``)."""
    dest = snapshot_path()
    if dest.exists() and not force:
        return dest
    resp = httpx.get(FST_SPONSORS_URL, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    append_external_manifest(
        external_source_entry(dest, "Fort Salem our-sponsors page snapshot"),
        slug="fortsalem-sponsors",
    )
    return dest


def _strip_tags(fragment: str) -> str:
    no_style = _STYLE_OR_SCRIPT.sub(" ", fragment)
    text = html_lib.unescape(_TAG.sub(" ", _EM_CLOSE.sub(",", no_style)))
    return re.sub(r"\s+", " ", text).strip()


def _year_sections(html: str) -> list[str]:
    """Bodies of the ``h2`` year sections (the year itself comes from each tier heading)."""
    matches = list(_H2_YEAR.finditer(html))
    return [
        html[m.end() : matches[i + 1].start() if i + 1 < len(matches) else len(html)]
        for i, m in enumerate(matches)
    ]


def _tier_names(body: str) -> list[tuple[int, str, str]]:
    """(year, tier, name) triples from one section's flattened text, split on tier headings.

    The year is taken from the tier heading itself ("2020 OPENING ANGELS:") rather than the
    section heading — the page's final section is headed ``2022 Sponsors:`` but is the 2020
    list, and its tier headings say so.
    """
    text = _FOOTER.sub("", _strip_tags(body))
    out: list[tuple[int, str, str]] = []
    heads = list(_TIER_HEADING.finditer(text))
    for i, m in enumerate(heads):
        year, tier = int(m.group(1)), m.group(2).strip().lower()
        if tier == "opening":  # "2020 OPENING ANGELS" loses ANGELS to the heading regex
            tier = "opening angels"
        span = text[m.end() : heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        span = _PRICE_RANGE.sub("", span, count=1)
        for name in span.split(","):
            clean = name.strip()
            # placeholders, page junk beyond name length, and blanks are dropped
            if (
                clean
                and clean.lower() not in _PLACEHOLDER_NAMES
                and len(clean) <= _MAX_NAME_LEN
            ):
                out.append((year, tier, clean))
    return out


def parse_sponsors(html: str) -> pd.DataFrame:
    """One row per (year, tier, listed name) across all year sections."""
    rows = [
        {"year": year, "tier": tier, "name": name}
        for body in _year_sections(html)
        for year, tier, name in _tier_names(body)
    ]
    df = pd.DataFrame(rows, columns=["year", "tier", "name"])
    if df.empty:
        raise ValueError("no sponsor names parsed — page structure may have changed")
    df["year"] = df["year"].astype(int)
    return df


def is_anonymous(name: str) -> bool:
    """Anonymous-style listings can't be mailed; keep them in the table, flagged."""
    return name.strip().lstrip("([ ").lower().startswith("anonymous")


def likely_org(name: str) -> bool:
    """Heuristic organization flag (see ``_ORG_MARKERS``); flagged, never silently dropped."""
    return bool(_ORG_PATTERN.search(name))


def summarize_sponsors(sponsors: pd.DataFrame) -> pd.DataFrame:
    """Collapse year rows to one row per listed name with span, years, and best tier."""
    return (
        sponsors.assign(
            anonymous=sponsors["name"].map(is_anonymous),
            org=sponsors["name"].map(likely_org),
        )
        .groupby("name", as_index=False)
        .agg(
            n_years=("year", "nunique"),
            first_year=("year", "min"),
            last_year=("year", "max"),
            years=("year", lambda s: ",".join(map(str, sorted(set(s))))),
            best_tier=(
                "tier",
                lambda s: max(s, key=lambda t: TIER_RANK.get(t.strip().lower(), 0)),
            ),
            anonymous=("anonymous", "first"),
            org=("org", "first"),
        )
        .sort_values(["n_years", "name"], ascending=[False, True])
        .reset_index(drop=True)
    )


def load_fst_sponsors(*, force: bool = False) -> pd.DataFrame:
    """Snapshot (fetch if missing) then parse; returns the (year, tier, name) table."""
    path = fetch_snapshot(force=force)
    return parse_sponsors(path.read_text(errors="replace"))
