# Questions and cleanups for Judy (Neon data hygiene)

*A working list of things Judy could clarify or fix in Neon, collected from the donor,
mailing-list, and attendance work (started 2026-08-31). Each item notes what we observed
and whether we already work around it in code. Nothing here is blocking; the big ones are
the first two. Keep it free of personal names — counts and ids only.*

## Ask

1. **What does the do-not-contact flag mean?** It is set on ~300 living individuals in 280
   households with $469k of lifetime giving — several of our largest donors — plus ~100
   company accounts, and also on deceased members. If it is an email opt-out (or an import
   artifact) rather than "never contact", the records could be cleaned or the flag split
   into something clearer. *(Already asked in the fall-campaign email; we keep flagged
   households in the mailing list and just mark them.)*
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

## Not Neon problems (for the record)

- The PLEDGEPAYMENT filter bug (Aug 2026) was a typo in *our* Python code, not in Neon —
  the database spells it correctly. Fixed in commit 49e21a6; recorded in
  `data-lessons.md`.
- Film screenings vs community, and youth showcases counting as classes, are *our*
  categorization decisions (see `src/hh/categorize/major.py`), not Neon data issues.
