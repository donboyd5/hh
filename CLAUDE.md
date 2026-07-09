# hh — project notes for Claude Code

**Read `meta-docs/RULES.md` at the start of every session** — it holds the standing working
rules (branches/PRs, testing, documentation, minimal interpretation in the web pages, strong
docs in the appendix).

## Git workflow

- **Never commit directly to `main`.** Do all work on a branch (`feature/…`, `fix/…`,
  `chore/…`) and merge to `main` via a GitHub pull request (`gh pr create`).
- Run `pytest` and render the book (`quarto render notebooks`) before opening a PR that touches
  `src/` or `notebooks/`.
- Don reviews and merges PRs (or explicitly asks for a merge). After merge, pull `main` and
  delete the branch.

## Publishing

- The book publishes to GitHub Pages (<https://donboyd5.github.io/hh/>):
  `quarto publish gh-pages notebooks --no-prompt --no-render`.
- Publish only from `main` after the corresponding changes are merged, so the public site always
  matches `main`.

## Conventions

- The book is organized as question-titled chapters; headline numbers in prose are computed
  inline, never hardcoded. Removed exhibits are parked in `notebooks/_parked-exhibits.qmd`.
- Candidate future analysis questions live in `TODO.md`.
- `data/` is PII and gitignored; publish only aggregates.
