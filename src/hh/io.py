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
