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
