# External people-lists and the Neon matching recipe

*Externally provided name lists that we match against Neon to find who is already in
the CRM. Inputs live in `data/00_raw/external/` (PII, gitignored); outputs are review
workbooks in `data/20_processed/` (also PII). **None of this goes in the book or on
the web page** — the published site carries aggregates only. Started 2026-09-03;
dates mark when a file or decision landed.*

## Files received

| File (in `data/00_raw/external/`) | Received | Rows | sha256 (first 16) |
|---|---|---:|---|
| `MfS 2026 Donors - SubSet Rev.xlsx` | 2026-08-31 | 60 | `b16fbffdce95c640` |
| `Friends to add.xlsx` | 2026-09-03 | 24 | `1d606886ac415f03` |
| `MfS Concerts attendees at HH.xlsx` | 2026-09-03 | 36 | `eb7a52aedc8a00c1` |

Origins beyond "externally provided to Don" are not recorded in the files; the MfS
lists come from Music from Salem (co-presenter at Hubbard Hall). Treat the contents
as names-only seed lists — no consent implied beyond normal constituent contact.

## Layout quirks (parse before matching)

- **MfS donor list**: one sheet, header on row 1, full names in one column plus
  address columns. Straightforward.
- **Friends to add**: one sheet, single `Name` column. Mostly one person per row,
  but three rows carry two partners — joined by `&` or by comma — and must be split
  into person names first (both partners are matchable).
- **MfS Concerts attendees**: name *fragments*, not full names. Row 1 is a title
  banner, real header below. Columns are `LastName | FirstName(s) | "&/or" |
  LastName2 | FirstName2`:
  - `Last | First & First` — a couple sharing the surname → two person names.
  - `Last | First | &/or | Last2 | First2` — two alternate individuals (often a
    shared household; *either* may be the Neon record) → two person names.
  - `M Fortier | Douglas` — a surname with a middle initial in front of it
    ("Douglas M Fortier"), not two surnames.

## Matching recipe (fuzzy, for human review — never auto-merge)

Reuse of the Fort Salem matcher (`src/hh/analytics/fst_match.py`), strengthened for
these lists. A one-off script (kept out of `src/` — the pipeline never loads these
files) does:

1. **Parse** each input row into 1–2 person names per the quirks above.
2. **Pool**: from `accounts_geocoded.parquet`, one row per *(household rollup id,
   name string)* over both household labels and member `full_name`s — member names
   are what catch households labeled under the *other* partner. Company-type
   accounts are excluded.
3. **Normalize** both sides: casefold, strip punctuation/suffixes, `&`/`and` dropped
   (the FST lesson: names arrive with double spaces and ampersand variants).
4. **Score** each person × pool pair, 0–100:
   - *surname gate*: the best of plain ratio, token-set ratio (catches hyphenated
     and maiden forms — "Shaw-Hebert" vs "Hebert"), and a phonetic match via
     **double metaphone** (the `DoubleMetaphone` package — note `jellyfish` ≥1.0
     dropped its `dmetaphone`) — the modern Soundex-class algorithm, chosen over
     Soundex itself because it handles the Slavic spellings these lists carry
     ("Ptacek", "Lescarbeau"). Phonetically-equal surnames score as 88 even when
     spelled differently.
   - *given-name agreement*: best across partners on either side — exact or known
     nickname 100 (the `fst_match` nickname map), shared 3-letter prefix 85,
     otherwise string ratio. Middle initials are tokens too, so "Douglas M" matches
     "Douglas".
   - *combined* = 0.4 × surname + 0.6 × given, but a full-name token-set ratio
     (order- and extra-token-insensitive) can carry the score when the surname
     spelling diverges.
5. **Report** the top 3 candidates per person at score ≥ 80 ("plausible"); ≥ 92 is
   "strong". The winning strategy is recorded per candidate (`via`). Names with no
   plausible candidate get no candidate rows — they are the "not in Neon" pool.
6. **Outputs**: one workbook per input in `data/20_processed/` — sheet 1 is the
   original file untouched; sheet 2 lists every original row followed by its
   candidate rows (Neon account id, household id, household label, address, and the
   deceased / do-not-contact flags — both matter before adding anyone to a list).
   Don reviews; only then does anything enter Neon or a mailing.

## Results

### 2026-09-03 — Friends to add (24 rows) and MfS Concerts attendees (36 rows)

Outputs: `data/20_processed/friends-to-add-matched.xlsx`,
`data/20_processed/mfs-concerts-attendees-matched.xlsx`. Script: one-off
(`/tmp/match_external.py`, method above; rebuildable from this doc).

- **Friends**: 24 rows → 27 person names (3 couple rows split). 19 names have a
  plausible candidate (15 uniquely strong); 8 have none — the not-in-Neon pool.
- **MfS attendees**: 36 rows → 48 person names (couples and "&/or" alternates
  split). 41 plausible (38 uniquely strong); 7 none — six of the seven are the
  *alternate* partner of an "&/or" pair or the second half of a couple, where the
  household is already keyed to the other partner; only one lead name missed.
- Fuzzy layer earned its keep: spellings in the lists differ from Neon for several
  strong matches (Stein/Stine, Hebert/Herbert, Gemert-Dott/Gernert-Dott,
  Koziel/Koziol, Pam/Pamela, Clifford/Cliff), plus one household matched through a
  member whose surname differs from the household label, and one "&/or" row whose
  fragments reconstruct exactly to a Neon record whose own name parts look
  swapped. One input name surfaced a likely duplicate-person pair in Neon (two
  households, same person, one address-less) — flagged for review, not merged.
- Flags carried into the workbooks: a handful of candidate households carry
  do-not-contact and/or deceased flags — check those columns before adding anyone
  to a list.
- Known looseness, accepted for a review workflow: a lone middle initial can
  prefix-match a full given name at 85 (survives as a rank-2 "possible" behind an
  exact match), and phonetic credit can pair unrelated surnames at ~86 — both are
  visible via the `via` and `Verdict` columns.
