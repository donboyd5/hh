# Questions and cleanups for Judy (Neon data hygiene)

*A working list of things Judy could clarify or fix in Neon, collected from the donor,
mailing-list, and attendance work (started 2026-08-31). Each item notes what we observed
and whether we already work around it in code. Nothing here is blocking; the big ones are
the first two. Keep it free of personal names — counts and ids only.*

## Ask

1. **What does the do-not-contact flag mean? — ANSWERED (Judy, 2026-08).** The flag is
   Neon's record of the Constant Contact email opt-out (the two systems are integrated:
   a CC opt-out flows back into Neon, and new Neon accounts must be opted into CC by hand
   or bulk update; the same field covers texting, which HH has not used). Reviewing the
   flagged accounts, Judy found many are old, had mail returned, or asked to be removed —
   and some are former playbill advertisers whose business stopped. So the flag mixes
   "no marketing email" (postal mail fine) with genuine "do not mail". **Follow-up:** get
   Judy's annotated do-not-contact spreadsheet back and split the 18 flagged households
   on the fall mailing list — keep the email-only opt-outs, drop the returned-mail and
   removal-request ones.
2. **Please add Neon ids to exported reports.** The donor and new-accounts workbooks carry
   no Account ID / Household ID columns, so we match people by name and city — 577
   households share a name with another household, and when Neon renames a household
   between pulls our hand-maintained aliases are the only repair. If her report templates
   can include the ids, a whole class of matching problems disappears.
3. **New-accounts export scope:** she quoted 176 new accounts for 25–26, but the workbook
   we have holds 268 rows (all unique names, all matching Neon households). Which cut did
   she intend? (The $100 registration floor is our rule, not hers.)
4. **Are refunds recorded anywhere queryable?** Six FY26 class sections were canceled after
   people paid; the attendee records say REFUNDED/CANCELED but the registration amounts
   remain on the events (we exclude those attendees everywhere). Worth confirming the
   refund itself is tracked so revenue reports don't overstate.

## Fix in Neon (nice-to-have; all already handled in our code)

5. **Delete or archive test records** — the junk donor account 36805 and test events
   ("Test Next Gen Event", "Test Session for Events") flow into every pull.
6. **Merge duplicate person records** — at least two people exist under two accounts /
   households (surfaced during the Fort Salem matching; named in the mailing-list QA
   sheet). Duplicates double-count households until merged.
7. **Household labels after a death** — Neon household names still include the deceased
   spouse; we relabel to the survivor in our outputs. If Neon's own labels were updated
   (or there's a convention), reports generated from Neon directly would read better.
8. **Category-label consistency** — the same program family appears over the years as
   "Bollywood  Dance" (with a double space), "Bollywood & BollyX", and plain "BollyX"
   event names; a periodic category cleanup in Neon would make its own reports cleaner.
   (We normalize category strings in code since 2026-08-31.)

## Answered from our data (2026-08-31)

- **Accounts without a complete address:** the list did not exclude them — and the check
  surfaced a bug. One of the two address-less appeal rows was the internal cash-drawer
  account, which had reached the list through the cash gifts booked to it; the pipeline
  now excludes all internal accounts (cash drawer and the online-registration
  placeholder) with a regression test. The other is one real donor with nothing on file
  but a name — Judy may have an address; otherwise they come off the mail merge. 43 of
  the 75 Fort Salem prospects also lack addresses and get no appeal letter in any case.
- **"Account type Hubbard Hall":** no such account type exists in the pull — Neon carries
  only `Individual` (4,873) and `Company` (291). The internal *Hubbard Hall
  Registrations* company account is not on the mailing list. Two appeal households do
  include a company member account (a community-services agency and a former playbill
  advertiser — the case Judy's notes describe); if company-affiliated households should
  come off the appeal, those two are the ones.

## Not Neon problems (for the record)

- The PLEDGEPAYMENT filter bug (Aug 2026) was a typo in *our* Python code, not in Neon —
  the database spells it correctly. Fixed in commit 49e21a6; recorded in
  `data-lessons.md`.
- Film screenings vs community, and youth showcases counting as classes, are *our*
  categorization decisions (see `src/hh/categorize/major.py`), not Neon data issues.
