"""Provenance: file hashing, per-pull manifests, and an append-only run log.

Every Neon pull writes a ``manifest.yaml`` recording how the data was obtained (endpoint, filters,
output fields, timestamp, Neon-reported counts, file hashes, code commit), so any figure can be
reproduced exactly. A global ``run_log.jsonl`` appends one line per pipeline run.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

from .. import config


def sha256_file(path: Path | str) -> str:
    """SHA-256 hex digest of a file, streamed in 1 MiB chunks."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def git_commit() -> str | None:
    """Current git commit hash, or None if git is unavailable / not a repo."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=config.project_root(),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return None


def write_manifest(pull_dir: Path | str, entry: dict) -> Path:
    """Write a provenance manifest for one data pull."""
    pull_dir = Path(pull_dir)
    pull_dir.mkdir(parents=True, exist_ok=True)
    path = pull_dir / "manifest.yaml"
    with path.open("w") as f:
        yaml.safe_dump(entry, f, sort_keys=False)
    return path


def read_manifest(path: Path | str) -> dict:
    with Path(path).open() as f:
        return yaml.safe_load(f)


def run_log_path() -> Path:
    rel = config.load_settings()["paths"]["run_log"]
    path = config.resolve_path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def append_run_log(entry: dict) -> Path:
    """Append one JSON line describing a pipeline run."""
    path = run_log_path()
    with path.open("a") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    return path


def file_hashes(paths) -> dict[str, str]:
    """Map {basename: sha256} for a list of files."""
    return {Path(p).name: sha256_file(p) for p in paths}
