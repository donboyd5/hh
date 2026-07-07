"""Parquet/JSONL I/O for the layered data model. All output resolves under data/."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from . import config


def write_parquet(df: pd.DataFrame, layer_key: str, filename: str) -> Path:
    path = config.layer_dir(layer_key) / filename
    df.to_parquet(path, index=False)
    return path


def read_parquet(layer_key: str, filename: str) -> pd.DataFrame:
    return pd.read_parquet(config.layer_dir(layer_key) / filename)


def write_jsonl(records, path: Path | str) -> Path:
    """Write an iterable of dict records as newline-delimited JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for record in records:
            f.write(json.dumps(record, default=str) + "\n")
    return path


def read_jsonl(path: Path | str) -> list[dict]:
    path = Path(path)
    with path.open() as f:
        return [json.loads(line) for line in f if line.strip()]


# -- raw Neon pulls (saved API data; the source of truth downstream) ----------
def raw_neon_dir() -> Path:
    """Directory holding dated Neon pulls (data/00_raw/neon), created if missing."""
    return config.layer_dir("raw_neon")


def latest_pull_dir() -> Path | None:
    """Most recent ``pull-*`` directory under data/00_raw/neon, or None if none exists."""
    pulls = sorted(p for p in raw_neon_dir().glob("pull-*") if p.is_dir())
    return pulls[-1] if pulls else None


def load_raw(entity: str, pull_dir: Path | str | None = None) -> pd.DataFrame:
    """Load a saved raw entity (Neon field names preserved as-is) from a pull's JSONL.

    This is the canonical way to access retrieved Neon data downstream: it reads entirely from
    saved files (the latest pull by default, or a specific ``pull_dir``), so analysis continues
    even if API access is lost. The API is only ever written to disk by
    ``hh.neon.extract.extract_all``; never call the client directly for data you intend to keep.
    Raises a clear error if no pull or entity exists.
    """
    pull = Path(pull_dir) if pull_dir is not None else latest_pull_dir()
    if pull is None:
        raise FileNotFoundError(
            "No saved Neon pull found under data/00_raw/neon. Run "
            "hh.neon.extract.extract_all() (which always writes here) before loading."
        )
    path = pull / f"{entity}.jsonl"
    if not path.exists():
        available = sorted(p.stem for p in pull.glob("*.jsonl"))
        raise FileNotFoundError(f"{entity!r} not found in {pull}; available: {available}")
    return pd.DataFrame(read_jsonl(path))

