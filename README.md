# Hubbard Hall — data analysis (Neon CRM → Python → Quarto)

Provenance-driven analysis of Hubbard Hall constituents: **donors, patrons, and class-takers**.
The project ingests data from the **Neon CRM REST API v2**, cleans and categorizes it (ported from
the prior R project in `R_hhfrc/`), adds a **geography + distance** layer and **timing** analysis
that the R work lacked, and publishes the findings as **Quarto web books** for the HH board.

---

## Getting started

### 1. Neon API key  *(required only before the first data pull)*

You need a **Neon Org ID** and an **API key**. Full step-by-step — including how to create a safe,
minimum-permission integration user — is in **[`docs/getting-a-neon-api-key.md`](docs/getting-a-neon-api-key.md)**.

The short version:

1. **Org ID** → Neon → Settings cog → *Organization Profile* → copy *Organization ID*.
2. **API key** → Settings cog → *User Management* → create a dedicated user → enable *API Access* → copy the key.
3. Put both in a **`.env`** file (template: `.env.example`). It is gitignored and never committed.

Everything else can be built and tested without the key, so take your time getting it.

### 2. Python environment  *(uv)*

The project uses **uv** (the `.venv` is already uv-created; pip works inside it too).

```bash
uv sync                                              # install dependencies
uv run python -m ipykernel install --user --name hh  # register the Quarto kernel (once)
```

### 3. Pull data & render the books  *(later — after the key is set)*

```bash
uv run python scripts/refresh_neon.py   # Neon API -> data/00_raw -> interim -> processed
uv run python scripts/build.py          # rebuild processed + analytics tables
quarto render notebooks                 # build the web book(s) -> _web/
```

---

## Project layout

```
config/        settings.yaml · overrides.yaml (manual data fixes) · fieldmap.yaml (Neon->standard names)
data/          00_raw (immutable extracts) · 10_interim · 20_processed · 30_external · 90_cache · manifest/
src/hh/        neon/ (API client) · clean/ · categorize/ · geo/ · analytics/ · provenance/
notebooks/     the Quarto book(s)
scripts/       refresh_neon.py · build.py · geocode.py · render_books.sh
tests/         pytest
docs/          getting-a-neon-api-key.md and more
R_hhfrc/       legacy R project (separate git repo, PII) — read-only reference + validation oracle
```

---

## Data & privacy

- Everything under `data/` is **donor PII** (names, home addresses, gift amounts) and is
  **gitignored — never committed**. It is regenerated from code + the Neon API.
- The legacy `R_hhfrc/` project is a separate git repository and also contains PII; it is gitignored
  here and kept only as a read-only reference and **validation oracle** (we compare Python totals
  against the R outputs before trusting the new pipeline).

## Provenance

Every Neon pull is recorded in a **manifest** — endpoint, filters, output fields, timestamp,
Neon-reported counts, file SHA-256 hashes, and the code commit that produced it — so any figure can
be reproduced exactly. See the *data-and-provenance* notebook chapter.

**Always saved, never lost.** Every record retrieved from the Neon API streams straight to disk
into immutable, date-stamped folders under `data/00_raw/neon/` as it arrives — never held only in
memory. So if API access is ever lost, every previously pulled dataset remains and analysis still
runs. Downstream code loads saved data via `hh.io.load_raw()`, never the live API.
