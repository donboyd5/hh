"""Don's household notes (``data/30_external/boyd-notes.yaml``) — local only.

The file holds personal stewardship notes about identifiable households, so it lives
under ``data/`` (gitignored) and is never committed. Consumers: the appeal analysis
site's silent-donor table and the donor workbook export.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from .. import config

NOTES_FILENAME = "boyd-notes.yaml"


def notes_path() -> Path:
    """Default location of the notes file under the external data layer."""
    return config.layer_dir("external") / NOTES_FILENAME


def load_boyd_notes(path: Path | None = None) -> dict[str, str]:
    """Notes as ``{household rollup id: note}``; empty dict when the file is absent.

    Entries missing a note are skipped so a half-written file can't blank a column.
    """
    src = Path(path) if path is not None else notes_path()
    if not src.exists():
        return {}
    loaded = yaml.safe_load(src.read_text()) or {}
    entries = loaded.get("notes") or {}
    return {
        str(k): v["note"]
        for k, v in entries.items()
        if isinstance(v, dict) and v.get("note")
    }


FST_WEB_NOTES_FILENAME = "fst-web-notes.yaml"


def load_fst_web_notes(path: Path | None = None) -> dict[str, str]:
    """Web-research notes on Fort Salem candidate matches, ``{fort salem name: note}``.

    Hand-maintained (Claude + Don) under ``data/30_external`` — local only, it names
    people and cites people-search pages. Each entry is ``{name: {note, sources}}``;
    the note is shown on the workbook's fst-candidates sheet, the sources stay in the file.
    """
    src = Path(path) if path is not None else config.layer_dir("external") / FST_WEB_NOTES_FILENAME
    if not src.exists():
        return {}
    loaded = yaml.safe_load(src.read_text()) or {}
    return {
        str(k): v["note"]
        for k, v in (loaded.get("notes") or {}).items()
        if isinstance(v, dict) and v.get("note")
    }
