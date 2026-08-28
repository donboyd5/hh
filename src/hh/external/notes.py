"""Don's household notes (``data/30_external/boyd-notes.yaml``) — local only.

The file holds personal stewardship notes about identifiable households, so it lives
under ``data/`` (gitignored) and is never committed. Consumers: the appeal analysis
site's silent-donor table and the donor workbook export.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
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


FST_CONTACT_NOTES_FILENAME = "fst-contact-notes.yaml"


def load_fst_contact_notes(path: Path | None = None) -> pd.DataFrame:
    """Web-research contact notes on Fort Salem sponsors not in Neon, one row per name:
    ``[household_name, contact_note, contact_confidence, contact_address, deceased,
    survivor]``. Hand/AI-maintained under ``data/30_external`` (local only)."""
    default = config.layer_dir("external") / FST_CONTACT_NOTES_FILENAME
    src = Path(path) if path is not None else default
    cols = [
        "household_name", "contact_note", "contact_confidence", "contact_address",
        "deceased", "survivor",
    ]
    if not src.exists():
        return pd.DataFrame(columns=cols)
    loaded = yaml.safe_load(src.read_text()) or {}
    rows = [
        {
            "household_name": str(k),
            "contact_note": v.get("finding"),
            "contact_confidence": v.get("confidence"),
            "contact_address": v.get("address"),
            "deceased": bool(v.get("deceased", False)),
            "survivor": v.get("survivor"),
        }
        for k, v in (loaded.get("notes") or {}).items()
        if isinstance(v, dict)
    ]
    return pd.DataFrame(rows, columns=cols)
