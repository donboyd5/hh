# Working rules

**Read this at the start of every session.** These are the standing rules for how work is
done in this project. They apply on top of `CLAUDE.md` and the conventions there. When two
statements conflict, the rule that is more specific to Hubbard Hall wins.

## 1. Branches and pull requests

- **Always work on a branch or worktree — never commit directly to `main`.** Create a
  descriptive branch (`feature/…`, `fix/…`, `chore/…`, `docs/…`) before making changes.
- **All changes land on `main` through a GitHub pull request** (`gh pr create`).
- **Never merge into `main` without Don's explicit permission.** Open the PR, summarize it,
  and wait for Don to review and merge (or to tell me to merge). After merge, pull `main`
  and delete the branch.
- **Use best programming practices, and recommend the same.** Prefer clear, readable code
  that matches the surrounding style; small, well-named functions; and changes that are easy
  to review.

## 2. Test and verify

- **Always test, and be sure things are right before opening a PR.** Run `pytest`. If a
  change touches `src/` or `notebooks/`, also render the book (`quarto render notebooks`)
  so a broken chunk never reaches `main`.
- Don't report a step as done unless it actually passed. If something is skipped or fails,
  say so plainly.

## 3. Document well

- **Document well.** Code should explain *why*, not just *what*. Keep docstrings and
  comments current with the code. Methodology, definitions, and data notes live in the
  Methodology appendix so they stay with the analysis.

## 4. Keep interpretation out of the web pages

- **Keep interpretive text in the web pages to a minimum — let Don do that.** State what the
  data shows; do not editorialize, speculate about causes, or prescribe actions. Don writes
  the narrative.

## 5. Strong documentation in the appendix

- **Provide strong documentation, primarily in the appendix.** The public chapters stay lean;
  the Methodology appendix carries the detail: raw data, cleaning, definitions, geography, and
  methods. When a question is "how is this defined?" or "where does this come from?", the
  answer belongs in the appendix.
