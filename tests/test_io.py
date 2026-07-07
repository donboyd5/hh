import json

import pytest

from hh.io import load_raw


def test_load_raw_reads_saved_jsonl(tmp_path, monkeypatch):
    pull = tmp_path / "pull-x"
    pull.mkdir()
    (pull / "events.jsonl").write_text(
        json.dumps({"Event ID": "1", "Event Name": "Hamlet"}) + "\n"
        + json.dumps({"Event ID": "2", "Event Name": "Macbeth"}) + "\n"
    )
    monkeypatch.setattr("hh.io.latest_pull_dir", lambda: pull)
    df = load_raw("events")
    assert list(df["Event ID"]) == ["1", "2"]
    assert list(df["Event Name"]) == ["Hamlet", "Macbeth"]


def test_load_raw_explicit_pull_dir(tmp_path):
    pull = tmp_path / "pull-y"
    pull.mkdir()
    (pull / "accounts.jsonl").write_text(json.dumps({"Account ID": "7"}) + "\n")
    df = load_raw("accounts", pull_dir=pull)
    assert list(df["Account ID"]) == ["7"]


def test_load_raw_missing_entity_raises(tmp_path, monkeypatch):
    pull = tmp_path / "pull-z"
    pull.mkdir()
    monkeypatch.setattr("hh.io.latest_pull_dir", lambda: pull)
    with pytest.raises(FileNotFoundError, match="not found"):
        load_raw("donations")


def test_load_raw_no_pull_raises(monkeypatch):
    monkeypatch.setattr("hh.io.latest_pull_dir", lambda: None)
    with pytest.raises(FileNotFoundError, match="No saved Neon pull"):
        load_raw("accounts")
