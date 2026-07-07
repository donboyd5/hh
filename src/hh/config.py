"""Project configuration: paths, settings.yaml, overrides.yaml, fieldmap.yaml, and .env secrets.

All file locations resolve relative to the project root (the directory holding pyproject.toml),
so the code works regardless of the current working directory.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv


def project_root() -> Path:
    """Return the project root — the nearest ancestor of this file containing pyproject.toml."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("Could not locate project root (no pyproject.toml found).")


def config_dir() -> Path:
    return project_root() / "config"


def resolve_path(relative: str | Path) -> Path:
    """Resolve a path relative to the project root (absolute paths pass through)."""
    p = Path(relative)
    return p if p.is_absolute() else project_root() / p


@lru_cache(maxsize=1)
def load_settings() -> dict:
    with (config_dir() / "settings.yaml").open() as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load_overrides() -> dict:
    with (config_dir() / "overrides.yaml").open() as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def load_fieldmap() -> dict:
    with (config_dir() / "fieldmap.yaml").open() as f:
        return yaml.safe_load(f)


def layer_dir(layer_key: str) -> Path:
    """Resolve a data-layer directory from settings.paths and ensure it exists."""
    rel = load_settings()["paths"][layer_key]
    path = resolve_path(rel)
    path.mkdir(parents=True, exist_ok=True)
    return path


def neon_settings() -> dict:
    return load_settings()["neon"]


def get_neon_credentials() -> tuple[str, str]:
    """Return (org_id, api_key) from the environment / .env.

    Raises a clear, actionable error if either is missing.
    """
    load_dotenv(project_root() / ".env")
    org_id = os.environ.get("NEON_ORG_ID")
    api_key = os.environ.get("NEON_API_KEY")
    missing = [n for n, v in [("NEON_ORG_ID", org_id), ("NEON_API_KEY", api_key)] if not v]
    if missing:
        raise RuntimeError(
            "Missing Neon credential(s): "
            + ", ".join(missing)
            + ". See docs/getting-a-neon-api-key.md and copy .env.example to .env."
        )
    return org_id, api_key
