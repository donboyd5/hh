"""Externally received people-lists: parsers for the tidy frames the address book needs.

Inputs live in ``data/00_raw/external/`` (PII, gitignored; see ``meta-docs/external-lists.md``
for how each file arrived and ``meta-docs/address-sources.md`` for the catalog). Every
parser returns one row per *listed household* — couple names stay together, matching
Fort Salem's household-level convention — because the address book is keyed to
households, not individuals. Splitting a couple for matching is the fuzzy matcher's
job (``fst_match.fuzzy_fst_candidates``), not the parser's.

The 2026-09-03 layout quirks documented in ``external-lists.md`` still hold, except the
MfS donor list was replaced around 2026-09-10 with a 68-name revision that *adds*
address columns (the doc described the 60-name names-only version). That revision is
the reason this module exists: received files change under us, so their parse lives in
tested code rather than in a one-off script.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .. import config

MFS_DONORS_FILENAME = "MfS 2026 Donors - SubSet Rev.xlsx"
FRIENDS_FILENAME = "Friends to add.xlsx"
ATTENDEES_FILENAME = "MfS Concerts attendees at HH.xlsx"
APPEAL2025_FILENAME = "Fall Appeal 2025 L With Donations.xlsx"  # lives in data/30_external

# street-column placeholders that are not addresses (2026-09-10 revision)
_NOT_ADDRESSES = {"address unavailable", "duplicate (see above)"}


def _raw_path(filename: str) -> Path:
    return config.layer_dir("raw") / "external" / filename


def _zip_str(z: pd.Series) -> pd.Series:
    """Zips as clean strings: numeric cells drop Excel's trailing ``.0``; zip+4 text
    ("10017-2134") passes through untouched."""
    num = pd.to_numeric(z, errors="coerce")
    out = [
        f"{int(v)}" if pd.notna(v) else (str(zv) if pd.notna(zv) else pd.NA)
        for v, zv in zip(num, z, strict=True)
    ]
    return pd.Series(out, dtype="string", index=z.index)


def load_mfs_donors(path: Path | None = None) -> pd.DataFrame:
    """Music from Salem 2026 donors: ``[name, street, city, state_province, zip_code]``.

    Header-less sheet: a title banner in row 1, a blank row, then name / (blank) /
    street / city / state / zip in columns 1, 3, 4, 5, 6. Two street placeholders
    ("Address Unavailable", "Duplicate (See Above)") parse to a missing street; the
    duplicate row itself is kept — it is still evidence the household is a donor.
    """
    src = Path(path) if path is not None else _raw_path(MFS_DONORS_FILENAME)
    raw = pd.read_excel(src, header=None)
    df = pd.DataFrame(
        {
            "name": raw[0],
            "street": raw[2],
            "city": raw[3],
            "state_province": raw[4],
            "zip_code": raw[5],
        }
    )
    df = df[df["name"].notna() & df["name"].astype(str).str.strip().ne("")]
    df = df[~df["name"].astype(str).str.contains("Music from Salem", case=False, regex=False)]
    # placeholders are not addresses — blank them, keep the donor row
    street = df["street"].astype("string").str.strip()
    df["street"] = street.where(~street.str.lower().isin(_NOT_ADDRESSES), other=pd.NA)
    df["zip_code"] = _zip_str(df["zip_code"])
    return df.reset_index(drop=True)


def load_friends(path: Path | None = None) -> pd.DataFrame:
    """``Friends to add``: ``[name]`` — single header column, rows as listed.

    A few rows carry two partners joined by ``&`` or a comma; they stay one household
    row (the address book mails households, and the fuzzy matcher sees both partners).
    """
    src = Path(path) if path is not None else _raw_path(FRIENDS_FILENAME)
    df = pd.read_excel(src)
    df = df.rename(columns={df.columns[0]: "name"})
    df = df[df["name"].notna() & df["name"].astype(str).str.strip().ne("")]
    return df[["name"]].reset_index(drop=True)


def load_attendees(path: Path | None = None) -> pd.DataFrame:
    """MfS concert attendees at Hubbard Hall: ``[name, row_note]``, one row per person
    or couple reconstructed from the sheet's name fragments.

    The sheet (title banner in row 1, no header) is five columns:
    ``LastName | FirstName(s) | "&/or" | LastName2 | FirstName2``. Three shapes:

    - ``Avis | Elizabeth & Walter`` — a couple sharing the surname → one household
      row, "Elizabeth & Walter Avis".
    - ``Anderson | Karen | &/or | Gurney | Richard`` — two alternate individuals
      (either may be the Neon record) → two rows.
    - ``M Fortier | Douglas`` — a middle initial in front of the surname →
      "Douglas M Fortier". Anything else is ``First Last``.

    ``row_note`` keeps the original fragments so a reconstruction can be checked.
    """
    src = Path(path) if path is not None else _raw_path(ATTENDEES_FILENAME)
    raw = pd.read_excel(src, header=None)
    rows: list[dict[str, str]] = []
    for r in raw.itertuples(index=False, name=None):
        last, first = r[0], r[1]
        if pd.isna(last) or not str(last).strip():
            continue
        if "music from salem" in str(last).lower():  # title banner row
            continue
        last, first = str(last).strip(), "" if pd.isna(first) else str(first).strip()
        mark = "" if len(r) < 3 or pd.isna(r[2]) else str(r[2]).strip()
        alt_last = "" if len(r) < 4 or pd.isna(r[3]) else str(r[3]).strip()
        alt_first = "" if len(r) < 5 or pd.isna(r[4]) else str(r[4]).strip()
        if "&" in first:  # couple sharing the surname
            rows.append({"name": f"{first} {last}", "row_note": f"{last} | {first}"})
        elif mark == "&/or" and alt_last:
            note = f"{last} | {first} | &/or | {alt_last} | {alt_first}"
            rows.append({"name": f"{first} {last}".strip(), "row_note": note})
            rows.append({"name": f"{alt_first} {alt_last}".strip(), "row_note": note})
        else:
            toks = last.split()
            if len(toks) == 2 and len(toks[0]) == 1 and toks[0].upper() == toks[0] and first:
                rows.append({"name": f"{first} {toks[0]} {toks[1]}", "row_note": f"{last} | {first}"})
            else:
                rows.append({"name": f"{first} {last}".strip(), "row_note": f"{last} | {first}"})
    return pd.DataFrame(rows, columns=["name", "row_note"])


def load_appeal2025_ids(path: Path | None = None) -> pd.DataFrame:
    """Neon ids actually mailed in the Fall 2025 appeal: ``[sheet, neon_hh_id, account_id]``.

    The workbook's own ids make this exact — no name matching. ``gen appeal`` and
    ``top for segments and personaliz`` carry ``hhid`` (household-level mailings) with
    an account-level ``id`` on rows where ``hhid`` is blank; ``theater appeal to
    artists`` carries only ``Account ID``. Account ids are resolved to household
    rollups by the caller, who has the accounts table.
    """
    src = Path(path) if path is not None else config.layer_dir("external") / APPEAL2025_FILENAME
    out = []
    for sheet in ("gen appeal", "top for segments and personaliz", "theater appeal to artists"):
        df = pd.read_excel(src, sheet_name=sheet)
        if sheet == "theater appeal to artists":
            out.append(
                pd.DataFrame(
                    {
                        "sheet": sheet,
                        "neon_hh_id": pd.NA,
                        "account_id": df["Account ID"],
                    }
                )
            )
            continue
        hh = pd.to_numeric(df.get("hhid"), errors="coerce")
        acct = pd.to_numeric(df.get("id"), errors="coerce").where(hh.isna())
        out.append(pd.DataFrame({"sheet": sheet, "neon_hh_id": hh, "account_id": acct}))
    ids = pd.concat(out, ignore_index=True).dropna(subset=["neon_hh_id", "account_id"], how="all")
    ids["neon_hh_id"] = ids["neon_hh_id"].astype("Int64").astype("string")
    ids["account_id"] = ids["account_id"].astype("Int64").astype("string")
    return ids.drop_duplicates().reset_index(drop=True)
