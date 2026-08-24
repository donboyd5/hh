"""Provenance for external spreadsheet sources.

The Neon pulls record how data was fetched; external workbooks can only record *what arrived*:
filename, checksum, size, mtime, and the code commit that loaded it. Each source gets a small
``data/manifest/external-<slug>.yaml`` holding one entry per distinct file version (deduped by
sha256), so replacing a workbook with a new version appends history rather than overwriting it.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml

from .. import config
from ..provenance.manifest import git_commit, now_iso, sha256_file


def external_source_entry(path: Path | str, note: str) -> dict:
    """Provenance entry for one external file as it exists right now."""
    p = Path(path)
    return {
        "file": p.name,
        "sha256": sha256_file(p),
        "size_bytes": p.stat().st_size,
        "modified_local": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
        "git_commit": git_commit(),
        "recorded_at": now_iso(),
        "note": note,
    }


def append_external_manifest(entry: dict, *, slug: str) -> Path:
    """Add ``entry`` to ``data/manifest/external-<slug>.yaml``, one entry per distinct sha256."""
    manifest_dir = config.layer_dir("manifest")
    path = manifest_dir / f"external-{slug}.yaml"
    existing: dict = {}
    if path.exists():
        existing = yaml.safe_load(path.read_text()) or {}
    entries = [e for e in existing.get("sources", []) if e.get("sha256") != entry["sha256"]]
    entries.append(entry)
    path.write_text(yaml.safe_dump({"sources": entries}, sort_keys=False))
    return path
