# What we've learned about the data

*Durable lessons from the Hubbard Hall data work — things that surprised us, cost us time,
or silently change numbers if ignored. Each notes where it is encoded in code, so this doc
is the index, not the implementation. Started 2026-08-31; dates mark when a lesson landed.*

## Neon: households and accounts

- **The household rollup id, not `household_id`, is the join key.** `household_id` is blank
  for single-account households — 6,259 of ~28k registrations — and keying on it silently
  zeroed those households' engagement (found 2026-08-28). Always use the rollup
  `id = household_id if present else account_id` (`clean/households.py`; the warning
  comment in `analytics/mailing.py:engagement_spend`).
- **Donation and registration records carry no household.** Donations have `account_id`
  only (`clean/donations.py` joins accounts); registrations have camelCase fields and no
  names at all — category comes from events, household from accounts
  (`clean/registrations.py`).
- **Neon renames households between pulls** (e.g. account 39722 / household 1684 changed
  between the 2026-07-07 and 2026-08-27 pulls). Name-keyed external lists need hand
  aliases (`HOUSEHOLD_ALIASES` in `scripts/export_mailing_list.py`).
- **Duplicate person records exist** — the same person under two accounts/households
  (surfaced twice in the Fort Salem review). Never auto-merged; listed in export QA.
- **577 households share a name with another household**, so name-only matching is
  ambiguous. Match on normalized name + city, fall back to name, and report the unmatched
  rather than fuzzy-guessing (`external/mailing.py:match_households`). Names arrive with
  double spaces and "and" vs "&" — normalize both (`norm_name`).

## Neon: flags

- **`deceased` is per account, and Neon also sets `do_not_contact` on deceased members.**
  A household is dropped only when *every* member is deceased; a surviving spouse keeps it
  and becomes the contact. This cost six widows who gave to the 2025 campaign before it
  was fixed (2026-08-28; `pick_contact` and `apply_exclusions` in `analytics/mailing.py`).
- **`do_not_contact` is the Constant Contact email opt-out** (Neon and CC are integrated;
  CC opt-outs flow back, new accounts are opted in by hand — Judy, 2026-08). But her
  review found the flag also covers old accounts, returned mail, removal requests, and
  former playbill advertisers — so it mixes "no email" with "no mail at all"; the split
  lives in her annotated spreadsheet, not in Neon. It also sits on deceased members and
  ~100 company accounts. Judged on living members only; kept and flagged on the mailing
  list, never silently dropped (`apply_exclusions`; do-not-contact sheet in the workbook).
- **Account 36805 is a known junk account** — excluded from donor analytics
  (`analytics/donors.py`).

## Neon: events and registrations

- **Event category strings arrive with irregular spacing** — incidental trailing spaces
  ("Visual Arts ") and internal double spaces ("Bollywood  Dance"). Normalize (casefold,
  collapse whitespace) before any matching (`categorize/major.py:_norm`).
- **Neon relabels event categories between pulls**, like households: "Irish Step Dance"
  became "Irish Dance" between 2026-08-27 and 09-01 (141 events). The categorizer's
  real-data tripwire caught it on the build; new spellings get a rule and a test case.
- **The major categorizer has been ours since 2026-08-31** (informed by the R port it
  replaced) — documented principles in `categorize/major.py`, cross-cutting indicator
  flags in `categorize/indicators.py`. It still returns `"ERROR"` for unmatched events on
  purpose, and a real-data test now fails the build if a pull contains any.
- **A registration is not a headcount.** A ticket registration averages about two
  attendees; true headcount needs the nested `tickets` arrays flattened
  (`analytics/productions.py` counts real headcount for productions; `analytics/timing.py`
  proxies by registration count). Any new attendance table must say which it is using.
- **Each Neon event is one performance**, not a production — multi-day runs are
  reconstructed from title patterns plus a run gap. Theater patterns are exhaustive;
  one-off concerts are deliberately left unmatched (`analytics/productions.py`,
  `unmatched_events` for the audit).
- **Canceled or moved events exist** and are excluded before attendance analysis
  (`analytics/productions.py`).
- **Event names embed their dates, ages, and status** — "(Ages 8-12)", "Thursdays,
  September 11 - December 11", "*Class is Full*", "*SOLD OUT*", "CANCELLED". Any
  name-based grouping must cut at date/weekday tokens and strip status markers
  (`series_name` in `scripts/attendance_doc.py`).
- **`eventId` can be missing on registrations** — a per-event sweep recovers records and
  records the fix in `_swept_event_id` (`scripts/sweep_registrations.py`,
  `clean/registrations.py`).

## Money

- **Clean-gift definition**: status `SUCCEEDED`, type `DONATION` or `PLEDGEPAYMENT`,
  account `Individual`; then drop deceased / do-not-contact / junk accounts, and roll up
  to the household (`analytics/donations.py`, `notebooks/99-methodology.qmd`).
- **The pledge-payment literal bug (2026-08-27)**: the type filter contained a stray
  character ("PLEDBGEPAYMENT"), matched nothing, and silently dropped 112 gifts / $91,100
  / 76 households from every donor figure. Build such literals by concatenation so a typo
  cannot hide, and reconcile against Judy's reports, which count exactly this filter
  (commit 49e21a6).
- **~18% of appeal-responding households gave only through a household member's account**
  — gifts must be rolled to the household or responders vanish (`analytics/appeal.py`).
- **Campaign coding matters inside a window**: of the Oct 2025–Jan 2026 gifts, ~$2k were
  coded Misc/Sustaining rather than to `Annual Fund Drive - 2025-2026`. The campaign
  literal plus the window reproduce Judy's campaign total (`analytics/mailing.py`).
- **Fiscal year** = July–June, labeled by ending year (FY26 = 2025-07-01 … 2026-06-30),
  matching Judy's report columns and Neon campaign names (`analytics/mailing.py`).
- **"Prior" engagement uses the event's start date, not the registration date** —
  registering in September for a November show is not prior engagement
  (`analytics/appeal.py`). The current calendar year is partial: excluded from trends,
  labeled YTD where shown (`notebooks/99-methodology.qmd`).

## Judy's workbooks (data/30_external)

- **New-accounts export**: header sits on workbook row 4; hand notes live in headerless
  columns at the right edge; the "HH/Acct. …" amount columns are household-level
  (`external/mailing.py:load_new_accounts`).
- **Row counts need confirming with Judy**: the workbook we have holds 268 new-account
  rows; she quoted 176. Of the 268, 73 have ≥$100 lifetime registrations on her own
  column, and all 73 match Neon households — the email table's "67 new accounts" is those
  73 minus 6 that clear the $500 engaged-non-donor bar (2026-08-31;
  `meta-docs/mailing-list-floor-alternatives.md`).
- **The donor export (FY24–26) carries no Neon ids** — matched by normalized name + city.

## External people-lists (data/00_raw/external)

- **Name lists from partners arrive in odd layouts** — couples in one cell, "&/or"
  alternates, surname fragments — and get fuzzy-matched against Neon for human
  review, never auto-merged. Files, layout quirks, and the full matching recipe
  (nickname map + token-set + double-metaphone) live in
  `meta-docs/external-lists.md`; scoring primitives in `analytics/fst_match.py`.

## Fort Salem (web source)

- **The sponsor page's structure differs by year**, and its final "2022 Sponsors:"
  section is actually the 2020 list — each tier heading's own year wins
  (`external/fortsalem.py`).
- **Exact-name matching misses real people**: nicknames, partner order, one partner
  listed alone, compound names. Fuzzy candidates are scored and offered for human review;
  never auto-merged (`analytics/fst_match.py`).
- **Match decisions live outside the workbook**, in YAML keyed by (name, household id), so
  Don's Y/N marks survive regeneration (`external/fst_confirmations.py`). A name confirmed
  against two differently-named households is held as a conflict, not applied.
- **Web research needs a source + confidence recorded**, and deaths found on the web drop
  a prospect (one of the 32 addressed prospects' cohort was dropped this way before the
  sheet shipped). Addresses came from county assessment rolls.

## Geography

- **The Census batch geocoder is flaky** (intermittent 502s, inconsistent coordinate
  format) — use the oneline endpoint concurrently with a local cache keyed by address
  (`geo/geocode.py`).
- **Location resolution is tiered**: own street → household member's street → ZIP centroid
  → unmapped, with `geo_precision` recording which. PO boxes are flagged, not dropped;
  ZIP-centroid placements are approximate and excluded from the tight distance bands
  (`geo/resolve.py`).

## Process lessons

- **Rebuild and compare before trusting a variant.** The sent email table was regenerated
  from the pull and verified cell-by-listed-cell before using the same code path for the
  six alternatives (2026-08-31).
- **Guard merges against NA keys** — pandas joins NA==NA and multiplies rows; the mailing
  build drops NA-id right sides and fails loudly on duplicate households
  (`analytics/mailing.py`).
- **Every exclusion is named in QA** — dropped households are listed with a reason, so a
  rule change can be audited by eyeball (`apply_exclusions`).
- **Ties break by list order, so document it** — the "top 30 by campaign gift" cut has a
  $250 tie at positions 30/31; the order is the list sort (campaign gift, five-year
  giving, class spend, name).
- **Honor Don's hand notes, not Neon staff notes**: staff narratives mention deaths of
  non-account people and contradict themselves; only Don's notes feed the deceased scan,
  and only an explicit survivor phrase rescues a household (`_combined_notes`).
- **Compile name-matching patterns with `re.I` and test capitalized input** — a pattern
  written in lowercase silently misses "Young", "Gala", "Ages 8", and the miss is
  invisible until a capitalized case lands in a test (learned twice in the indicators
  module, 2026-08-31).
- **External workbooks get provenance entries** — checksum, size, mtime, and loading
  commit, one entry per file version (`external/provenance.py`).

## Fall-2026 mailing-list deliverables (2026-09-10 → 09-13)

- **`mailing_list.parquet` is a prospect universe, not "everyone in Neon"** — its id
  union only holds households meeting some criterion (5-yr donor, donor-3 workbook,
  new accounts, silent keep-list, appeal responder/giver, $500 engaged spend). 12 of
  17 MfS donors already matched to Neon households had no row in it at all, so no
  loop over it can reach them (found 2026-09-11). "Include everyone" requests must
  source from the address book instead — category 7 and the reception top-30 in
  `scripts/export_donor_list.py` do exactly that, and re-apply the
  deceased/do-not-contact set-aside by hand since they bypass `apply_exclusions`.
- **Internal house accounts rank in top-donor lists unless excluded** — the cash-drawer
  rollup (36805, "Cash and Credit Card Miscellaneous Transactions") has no address and
  once appeared in a top-30 by dollar total; `INTERNAL_ACCOUNT_IDS` must be mirrored
  into any ranking that doesn't go through `build_mailing_list`
  (`_reception_draft` in `scripts/export_donor_list.py`).
- **`do_not_contact` hides real donors** — 16 would-qualify households surfaced when
  DNC records were classified with the same rules as everyone else (incl. a ~$15k/yr
  major donor). Set-asides deserve a review sheet, not a silent drop
  (`_dnc_review` in `scripts/export_donor_list.py`).
- **Assessment-roll matching needs street agreement, not just a name hit** — the roll
  is ~39k parcels across Washington + Rensselaer counties, and common names hit
  unrelated parcels (a "Karen Anderson" name hit on a different street). Name +
  normalized-street prefix both must agree (`_roll_corroborates` in
  `scripts/export_mfs_attendee_match.py`). Corollaries: PO-box households can never be
  roll-corroborated, and the roll does not cover Saratoga or Bennington-VT counties.
- **The automated list matcher misses nickname/partial-name variants** — "Lisa Chang"
  vs Neon's "William Buzbee & Lisa Chang", "Marti & Ray Ellermann" vs "Marti &
  Raymond Ellermann" both required a manual surname cross-check to catch
  (2026-09-11; `MANUAL_NEON_MATCH` in `scripts/export_mfs_attendee_match.py`).
- **Salutation resolves household-first** (`Household Salutation` fills from
  `Salutation`), and about half the list has neither — constructed first-name
  salutations are filled in but flagged (bold, yellow) for review
  (`_salutation_map` / `_construct_salutation` in `scripts/export_donor_list.py`).
- **Source-list address defects are corrected in code, never in the source** — e.g.
  Sunderland VT has no post office of its own (shares Arlington's USPS zip 05250, not
  the Manhattan 10025 the MfS list carried), plus "Bennigton"/"Grewnwich" typo towns.
  Corrections live in `ADDRESS_CORRECTIONS` (`external/address_book.py`) so every
  consumer gets them while the sha-verified source files stay pristine; name-keyed,
  so re-check after a Neon pull.
- **Record web-research *non*-findings too** — a yaml entry saying "searched, here's
  why nothing was found" (wrong-region hits ruled out, no anchor town) prevents
  re-researching the same dead end later (`data/30_external/contact-research.yaml`,
  `mfs-attendee-research.yaml`).
- **Drive deliverables**: CSV→Sheets import strips leading ZIP zeros (wrap zips as
  `="05773"` formulas) and carries no cell formatting; HTML→Google-Docs import breaks
  on `rowspan` (repeat blank cells instead). A ~550-row CSV is too big to hand-copy
  through the session's own context — delegate read-then-upload to a subagent.
- **Verify a PR's merge state before pushing to its branch again** — a commit pushed
  minutes *after* GitHub merged the PR sits orphaned on the branch while everything
  downstream behaves as if it shipped (reception_draft, 2026-09-11; caught two days
  later). `gh pr view <n> --json state,mergedAt` before every follow-up push.
