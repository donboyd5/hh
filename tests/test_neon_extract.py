import hashlib
import json

from hh.neon import extract
from hh.provenance import manifest


class FakeClient:
    """Stand-in for NeonClient: deterministic data, no network."""

    base_url = "https://api.neoncrm.com/v2/"
    page_size = 200

    def __init__(self) -> None:
        self.closed = False

    def search_pages(self, entity, **kwargs):
        if entity == "events":
            yield [
                {"Event ID": "E1", "Event Name": "Hamlet"},
                {"Event ID": "E2", "Event Name": "Tap Dance Class"},
            ], {"totalResults": 2, "totalPages": 1}
        else:
            yield [{"id": f"{entity}-0"}, {"id": f"{entity}-1"}], {
                "totalResults": 2,
                "totalPages": 1,
            }

    def get_event_registrations(self, event_id, **kwargs):
        yield {"registration_id": f"R-{event_id}", "event_id": event_id}

    def get(self, path, **kwargs):
        return [{"endpoint": path}]

    def close(self):
        self.closed = True


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_extract_all_writes_files_and_manifest(tmp_path):
    pull = extract.extract_all(FakeClient(), raw_dir=tmp_path, run_log=False)
    assert pull.is_dir()
    for name in (
        "accounts.jsonl",
        "donations.jsonl",
        "events.jsonl",
        "registrations.jsonl",
        "manifest.yaml",
    ):
        assert (pull / name).exists(), name

    assert len(_read_jsonl(pull / "accounts.jsonl")) == 2

    regs = _read_jsonl(pull / "registrations.jsonl")
    assert len(regs) == 2  # E1 and E2, one registration each
    assert regs[0]["_swept_event_id"] == "E1"

    assert (pull / "reference" / "campaigns.json").exists()

    m = manifest.read_manifest(pull / "manifest.yaml")
    assert m["source"] == "Neon CRM API v2"
    assert m["entities"]["accounts"]["local_row_count"] == 2
    assert m["entities"]["accounts"]["neon_total_results"] == 2
    assert m["entities"]["registrations"]["local_row_count"] == 2
    assert m["entities"]["registrations"]["events_swept"] == 2
    assert m["entities"]["accounts"]["sha256"]
    assert "campaigns" in m["reference"]


def test_extract_all_does_not_close_injected_client(tmp_path):
    fc = FakeClient()
    extract.extract_all(fc, raw_dir=tmp_path, run_log=False)
    assert fc.closed is False  # we don't own an injected client


def test_manifest_sha256_matches_file(tmp_path):
    pull = extract.extract_all(FakeClient(), raw_dir=tmp_path, run_log=False)
    m = manifest.read_manifest(pull / "manifest.yaml")
    digest = hashlib.sha256((pull / "events.jsonl").read_bytes()).hexdigest()
    assert m["entities"]["events"]["sha256"] == digest


def test_extract_subset_entities(tmp_path):
    pull = extract.extract_all(
        FakeClient(),
        entities=("accounts",),
        include_reference=False,
        raw_dir=tmp_path,
        run_log=False,
    )
    assert (pull / "accounts.jsonl").exists()
    assert not (pull / "donations.jsonl").exists()
    assert not (pull / "reference").exists()
