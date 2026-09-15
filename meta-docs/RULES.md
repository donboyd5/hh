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

## Google Drive deliverables (Docs and Sheets)

- **Never overwrite or replace a Google Doc that people may have commented on.** Colleagues
  leave comments in the Drive copies of deliverables (e.g. "Final mailing list - draft 1");
  those comments are decisions and must never be lost. Publish each new version as a
  **new file under a new name** carrying a version number and date (e.g.
  "Final mailing list - draft 1 - v2 2026-09-13"), and leave every earlier Doc exactly as
  it is - do not trash it, do not rewrite its contents, do not "update in place".
- Before touching any Drive file, read it with comments included; if it has comment
  threads, treat it as read-only and tell Don what the comments say.
- **Do not build Drive Sheets from CSV. Hand the xlsx to Don and let him upload it**
  (Don, 2026-09-15). The assistant's Drive tool takes content inline only - there is no
  "upload this path" - so a CSV Sheet means retyping every row through the model. That is
  wrong on three counts, and the third is the one that matters:
    1. CSV is one tab, so five sheets become five separate files rather than one workbook.
    2. CSV carries no formatting, so the house style below is lost every single time.
    3. **It invents errors.** Transcribing 558 rows by hand duplicated a household
       (Mitsuo Lockrow appeared twice, 559 rows) - and the uploads are too large to read
       back and verify, so such an error can ship unnoticed. A mailing list that silently
       gains or drops a row is worse than no Drive copy at all.
  The xlsx already has the tabs and the formatting. Regenerate it, save a dated copy
  (`final-mailing-list-draft_YYYY-MM-DD_HHMM.xlsx`), and tell Don the path; he drags it
  into the Drive folder and does File > Save as Google Sheets. Uploading the xlsx
  directly is not an option for the assistant: it would have to pass ~186,000 characters
  of base64 through the model, and a 9,000-character attempt already failed.
- Docs are different and stay the assistant's job: HTML -> Google Doc import works
  cleanly (real `<table>`, no rowspan) and needs no transcription of tabular data.
  Bold inside table cells survives the import - `read_file_content` renders it back as
  escaped `\*\*text\*\*`, which looks like a bug but is just its markdown serialization.
- **Only the current files live in the Drive folder.** Before publishing a new round,
  move what is there into `Archive/` (Don keeps that subfolder) rather than leaving old
  and new side by side - mixed vintages are what made the folder confusing (Don,
  2026-09-15). One workbook plus the overview Doc is the target state.
- Only one Drive upload in flight at a time (two concurrent uploaders to the same folder
  once produced duplicate sheets under identical titles).

## Spreadsheet deliverables (xlsx and Drive Sheets)

House style, set by Don by hand on the Drive board sheet (2026-09-13). Every sheet we
generate for people (donor lists, address book, attendee match, ...) gets it in the xlsx:

- **Bold header row.**
- **Freeze panes at B2** - row 1 (headers) and column A (the id / first column) stay
  visible while scrolling. (`ws.freeze_panes = "B2"` in openpyxl.)
- **Money columns financial-formatted, no decimals**: `#,##0` (comma thousands, no `$`).
- **Names readable without widening**: mailing name, salutation and category columns
  wide enough to show most of their text (currently 32 / 22 / 32 characters); address
  and notes wide too.
- A CSV->Sheets upload carries NONE of this (no cell formatting in CSV), which is one of
  the reasons the Drive rule above says to ship the xlsx and let Don upload it. Google
  Sheets converts an uploaded xlsx with the tabs and formatting intact.
