# Address sources and the consolidated address book

*The single catalog of every address-bearing source and the rules that combine them into
`data/20_processed/address_book.xlsx`. Everything here names real people: **local only,
nothing published or committed** — the public book carries aggregates. Decisions marked
with dates are Don's. First version 2026-09-10; update this file whenever a source
arrives, changes, or a rule moves.*

## What the address book is

One row per mailable identity — everyone in Neon plus the add-on lists — with every
candidate address, one *best* address, and the flags needed to cherry-pick a mailing
(deceased, do-not-contact, PO-box, mailed-last-year, list memberships). It is the
knowledge base, not a mailing list: rows are flagged, never silently dropped, so
web-confirmed deaths stay visible here even though the mailing-list export drops them.

Build it (offline, deterministic):

```
python scripts/export_address_book.py
```

Outputs: `data/20_processed/address_book.parquet`, `address_book_candidates.parquet`,
`address_book.xlsx` (sheets: `address-book`, `address-candidates`, `about`). Rerun after
a Neon pull/build, after `research_fst_contacts.py` / `export_mailing_list.py`, or when
any received list changes. Assembly code: `src/hh/external/address_book.py`; parsers:
`src/hh/external/lists.py`.

## Scope decisions (Don, 2026-09-10)

1. **Universe**: everyone in Neon (household rollup level) plus the add-on lists;
   filter down from there. Company-only Neon rollups are excluded *unless* an add-on
   list vouches for the person — those are kept and flagged `neon_company_only` (five
   as of 2026-09-10, including the Margo & Michael Hatzel record Judy has on the
   fix-list; Sally Brillon came in via the MfS list).
2. **Best-address precedence** (rank order, first available wins): current Neon >
   assessment-roll *strong* > MfS donor list > assessment-roll *probable* >
   web-research *business* address. Every candidate stays on the `address-candidates`
   sheet regardless of which wins; disagreeing streets flag `address_conflict`.
3. **Fall Appeal 2025** is a `mailed_2025` flag only — never an address source (its
   addresses are a year old; Neon is the CRM of record).
4. **Matching**: only exact household-name matches (city tiebreak) and Don's recorded
   confirmations fold into Neon. Fuzzy candidates are shown (`possible_neon_match`),
   never auto-folded. Standalone rows merge across lists only on an exact canonical-key
   match (surname + nickname-folded given names — "Bob & Carolyn Akland" ≡ "Robert &
   Carolyn Akland"); subset matches never merge, to avoid fusing relatives.

## Sources

| Source | File | Key | Notes |
|---|---|---|---|
| **Neon accounts** | `accounts_geocoded.parquet` (via latest pull + build) | household rollup id | authoritative for anyone in Neon; address rolled up per household by `pick_contact` (living member preferred as contact; deceased = ALL members deceased; do-not-contact = any living member flagged) |
| **Assessment rolls** | `data/00_raw/external/assessment/` — Washington Co. NY 2026, Rensselaer Co. (Hoosick) 2026, VT grand list 2025 (VCGI parcels) | Fort Salem canonical name | researched only for rule-B FST prospects; hits in `data/10_interim/fst_contacts.parquet` with `confidence` strong/probable; owners recorded for verification |
| **MfS 2026 donor list** | `data/00_raw/external/MfS 2026 Donors - SubSet Rev.xlsx` (received 2026-08-31, sha256 `b16fbffdce95c640`) | name string | header-less; 67 donor rows, 64 usable addresses ("Address Unavailable" / "Duplicate (See Above)" placeholders blanked, rows kept). Same file `external-lists.md` describes — its "60 rows" count there reflects a different counting convention, not a revision |
| **Fall Appeal 2025** | `data/30_external/Fall Appeal 2025 L With Donations.xlsx` | Neon ids (`hhid`, account `id`, artists' `Account ID`) | `mailed_2025` flag only; ids resolve exactly against the rollup, no name matching |
| **Web research** | `data/30_external/fst-contact-notes.yaml` | Fort Salem name | business addresses (confidence `business`) are last-rank candidates; confirmed deaths/survivors drive `deceased` flag and survivor relabels |
| **Contact research** | `data/30_external/contact-research.yaml` | address-book name | web-research phone/email for FST/MfS/Friends people **not in Neon** (2026-09-10 round: 142 targets — FST rule-B-kept, MfS donors, Friends). People-search hits carry confidence labels (confirmed/probable/hint) and source URLs; they are hints, never auto-contact. A death finding that cites a source flips the row's `deceased` flag (edit the yaml to override). Fills `research_phone`/`research_email` columns; Neon rows keep Neon's own `phone`/`email` |
| *Names-only lists* | `Friends to add.xlsx`, `MfS Concerts attendees at HH.xlsx`, `New Accounts 25-26 for AF Mailing.xlsx` | name string | no addresses; membership flags (`friends_to_add`, `mfs_attendee`) and fuzzy candidates only |

## Columns that matter for cherry-picking

- identity: `neon_hh_id` (blank = not in Neon), `name`, `also_listed_as` (variant names
  we know the household by — FST listings, list spellings)
- presence: `fst` + `fst_best_tier` + `fst_years` + `fst_rule_b` (kept / below-bar —
  rule B = $100+ tier any year 2021–25 or 2+ years; see `analytics/mailing.py`),
  `mfs_donor`, `friends_to_add`, `mfs_attendee`, `mailed_2025`, `in_mailing_list`,
  `letter`
- address: `address/city/state_province/zip_code`, `address_source` (which rank won),
  `address_conflict` (sources disagree — probably moved; check `address-candidates`),
  `po_box`
- contact: `phone`/`email` (Neon, for rows in Neon), `research_phone`/
  `research_email` + confidences + `research_note` (web research, for rows not in Neon)
- exclusions/context: `deceased`, `deceased_members`, `do_not_contact`, `web_note`,
  `possible_neon_match` (top fuzzy Neon candidate for not-in-Neon rows), `note_boyd`,
  `neon_company_only`

## State as of 2026-09-10 (first build)

4,696 identities: 4,368 in Neon (5 company-only, list-vouched) + 328 not in Neon.
4,280 with a best address (neon 4,200 / roll-strong 27 / mfs-list 46 / roll-probable 5 /
web-business 2). 31 address conflicts, 287 PO-box best addresses, 1,035 mailed in 2025,
34 households where every member is deceased. Not-in-Neon rows: 68 carry a fuzzy Neon
candidate, 260 none. Cross-checked against the reviewed mailing list: 405/405 addressed
Neon rows identical; FST rule-B kept = 76 (the mailing list's 75 plus Ruth Flint Frew,
web-confirmed deceased — kept here, flagged), below-bar = 168, matching the prospects
workbook exactly.
