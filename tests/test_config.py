from pathlib import Path

import pytest

from hh import config


def test_project_root_has_pyproject():
    assert (config.project_root() / "pyproject.toml").is_file()


def test_load_settings_shape():
    s = config.load_settings()
    assert "paths" in s
    assert "neon" in s
    assert s["fiscal_year"]["start_month"] == 7


def test_resolve_path_relative_is_absolute():
    p = config.resolve_path("data/00_raw")
    assert p.is_absolute()
    assert p.name == "00_raw"


def test_layer_dir_creates_directory(tmp_path, monkeypatch):
    # point settings.paths at a temp tree so the test doesn't touch real data/
    monkeypatch.setattr(
        config,
        "load_settings",
        lambda: {
            "paths": {"processed": str(tmp_path / "proc")},
            "neon": {},
            "fiscal_year": {},
        },
    )
    out = config.layer_dir("processed")
    assert out.is_dir()
    assert out.name == "proc"


def test_get_neon_credentials_missing(monkeypatch):
    monkeypatch.delenv("NEON_ORG_ID", raising=False)
    monkeypatch.delenv("NEON_API_KEY", raising=False)
    monkeypatch.setattr(config, "project_root", lambda: Path("/nonexistent"))
    with pytest.raises(RuntimeError, match="Missing Neon credential"):
        config.get_neon_credentials()
