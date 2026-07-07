import hashlib

from hh.provenance import manifest


def test_sha256_file(tmp_path):
    p = tmp_path / "f.txt"
    p.write_text("hello hubbard hall")
    assert manifest.sha256_file(p) == hashlib.sha256(b"hello hubbard hall").hexdigest()


def test_manifest_roundtrip(tmp_path):
    entry = {
        "endpoint": "/accounts/search",
        "totalResults": 42,
        "files": {"accounts.jsonl": "abc123"},
    }
    path = manifest.write_manifest(tmp_path, entry)
    assert path.name == "manifest.yaml"
    assert manifest.read_manifest(path) == entry


def test_git_commit_is_str_or_none():
    assert manifest.git_commit() is None or isinstance(manifest.git_commit(), str)


def test_run_log_path_name():
    assert manifest.run_log_path().name == "run_log.jsonl"


def test_file_hashes(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("aaa")
    b = tmp_path / "b.txt"
    b.write_text("bbb")
    hashes = manifest.file_hashes([a, b])
    assert set(hashes) == {"a.txt", "b.txt"}
    assert hashes["a.txt"] == hashlib.sha256(b"aaa").hexdigest()
