# Questions to answer next

The book is organized as questions (see `notebooks/`). These are candidate questions for future
chapters or sections, with notes on feasibility given the data we already pull from Neon
(accounts, donations, events, registrations).

## Giving

- [ ] **Do class-takers and patrons become donors?** First-activity date vs first-gift date per
  household: how often does participation precede giving, and by how long? (Feasible now:
  `registered_at` + `donation_date`.)
- [ ] **Who has lapsed?** Donor households that gave in earlier years but not recently —
  recency/frequency segmentation, and how much annual giving the lapsed group used to represent.
  (Feasible now.)
- [ ] **How concentrated is giving?** Share of lifetime dollars from the top 10 / 50 households;
  dependence on a few large gifts, and whether concentration is rising. (Feasible now; publish
  only aggregate shares, never named households.)
- [ ] **When during the year do donations arrive?** Seasonality, year-end share, spikes around
  events or appeals. (Feasible now.)
- [ ] **Do donors who attend give more than donors who don't?** Giving levels by engagement
  tier (donate-only vs donate+attend vs all three). (Feasible now via `households_summary`.)

## Audience

- [ ] **How far in advance do people buy tickets?** Lead time (`registered_at` to `starts_on`)
  by genre and day of week; the walk-up share. (Feasible; first check how much of
  `registered_at` is real timestamps vs batch-entered dates.)
- [ ] **Which shows bring in first-timers?** For each production, how many attending households
  were brand new — and did they ever come back? Acquisition value of programming. (Feasible
  now; builds on the production mapping.)
- [ ] **How many attendees come back?** Repeat rate and one-and-done share by genre; do class
  households attend more performances than performance-only households attend classes?
  (Feasible now.)
- [ ] **Has the audience gotten more or less local over time?** Distance mix of registrations
  by period, overall and by genre — the audience analogue of the donor-geography over-time
  section. (Feasible now.)
- [ ] **Are sell-outs predictable?** "SOLD OUT" in event names is a weak label; check whether
  the events extract includes a capacity field so utilization can be computed properly.
  (Needs a look at `events.jsonl` — possible data gap.)

## Data gaps to investigate

- [ ] Event **capacity** (for utilization / sell-out analysis) — is it populated in Neon?
- [ ] **Memberships** — if Hubbard Hall uses Neon's membership module, pulling it would open
  "do members behave differently?" questions.
- [ ] **Campaign/appeal codes** on donations — would let "when do donations arrive?" separate
  appeal-driven from spontaneous gifts.
