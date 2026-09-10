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


CONTACT_RESEARCH_FILENAME = "contact-research.yaml"


def load_contact_research(path: Path | None = None) -> pd.DataFrame:
    """Web-research phone/email for list people not in Neon, one row per book name:
    ``[household_name, phone, phone_confidence, email, email_confidence, finding,
    death_or_move, sources, deceased_web]``.

    Hand/AI-maintained under ``data/30_external`` (local only — names real people and
    cites people-search pages). Confidence follows the research policy in
    ``meta-docs/address-sources.md``: people-search hits are hints, never confirmed
    contact until Don says so. ``deceased_web`` is an explicit flag (not parsed from
    prose — a note saying "husband died, she survives" must never mark the widow
    deceased) and is set only when the listed person themselves is confirmed dead with
    a cited obituary; it flips the book's ``deceased`` column. ``sources`` is the
    joined URL list for provenance.
    """
    src = (
        Path(path)
        if path is not None
        else config.layer_dir("external") / CONTACT_RESEARCH_FILENAME
    )
    cols = [
        "household_name", "phone", "phone_confidence", "email", "email_confidence",
        "finding", "death_or_move", "sources", "deceased_web",
    ]
    if not src.exists():
        return pd.DataFrame(columns=cols)
    loaded = yaml.safe_load(src.read_text()) or {}
    _blank = {"", "none", "n/a", "nan"}

    def _clean(v):
        return None if v is None or str(v).strip().lower() in _blank else str(v).strip()

    rows = [
        {
            "household_name": str(k),
            "phone": _clean(v.get("phone")),
            "phone_confidence": _clean(v.get("phone_confidence")),
            "email": _clean(v.get("email")),
            "email_confidence": _clean(v.get("email_confidence")),
            "finding": _clean(v.get("finding")),
            "death_or_move": _clean(v.get("death_or_move")),
            "sources": "; ".join(str(s) for s in v.get("sources") or []),
            "deceased_web": bool(v.get("deceased_web", False)),
        }
        for k, v in (loaded.get("notes") or {}).items()
        if isinstance(v, dict)
    ]
    return pd.DataFrame(rows, columns=cols)
