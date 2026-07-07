"""High-level Neon extraction: pull entities to a dated ``data/00_raw/neon/`` folder + manifest.

Writes one JSONL file per entity (accounts, donations, events, registrations) and small
reference JSON files, plus a ``manifest.yaml`` recording exactly how each was obtained
(endpoint, output fields, Neon-reported totals, local row counts, file SHA-256, code
commit). Appends a line to the run log.

All retrieved records stream straight to disk as they arrive (never held only in memory), and each
pull is an immutable date-stamped folder — so previously retrieved data always survives, even if
API access is later lost. Downstream code loads saved data via ``hh.io.load_raw``, never the API.

Registrations are gathered by sweeping every event id from the events extract (there is no bulk
registrations search endpoint). Events are therefore always extracted before registrations.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .. import config, io
from ..provenance import manifest
from . import endpoints
from .client import NeonClient

DEFAULT_ENTITIES = ("accounts", "donations", "events", "registrations")


def _pull_folder_name() -> str:
    return "pull-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _extract_search(
    client: NeonClient, entity: str, pull_dir: Path
) -> tuple[int, int | None, Path]:
    """Stream a search entity to JSONL. Returns (local_count, neon_total, path)."""
    path = pull_dir / f"{entity}.jsonl"
    total: int | None = None
    count = 0
    pages = 0
    with path.open("w") as f:
        for records, pagination in client.search_pages(entity, validate_fields=True):
            if total is None:
                total = pagination.get("totalResults")
            for record in records:
                f.write(json.dumps(record, default=str) + "\n")
                count += 1
            pages += 1
    print(f"[neon] {entity}: {count:,} records ({pages} page(s)); neon total={total}", flush=True)
    return count, total, path


def _event_ids(events_path: Path) -> list[str]:
    ids: list[str] = []
    for record in io.read_jsonl(events_path):
        for key in endpoints.event_id_key():
            value = record.get(key)
            if value:
                ids.append(str(value))
                break
    return ids


def _extract_registrations(
    client: NeonClient, pull_dir: Path, events_path: Path | None
) -> tuple[int, int, Path]:
    """Sweep registrations per event. Returns (count, event_count, path)."""
    out = pull_dir / "registrations.jsonl"
    event_ids = _event_ids(events_path) if events_path else []
    count = 0
    failed: list[tuple[str, str]] = []
    with out.open("w") as f:
        for i, event_id in enumerate(event_ids, 1):
            try:
                records = list(client.get_event_registrations(event_id))
            except Exception as exc:  # noqa: BLE001 - one event must not abort the whole sweep
                failed.append((event_id, type(exc).__name__))
                continue
            for record in records:
                record["_swept_event_id"] = event_id  # provenance: which event this came from
                f.write(json.dumps(record, default=str) + "\n")
                count += 1
            if i % 500 == 0 or i == len(event_ids):
                print(
                    f"[neon] registrations: {i}/{len(event_ids)} events, {count:,} records",
                    flush=True,
                )
    if failed:
        print(
            f"[neon] registrations: {len(failed)} event(s) failed; saved {count} records. "
            f"first failures: {failed[:3]}"
        )
    return count, len(event_ids), out


def _extract_reference(client: NeonClient, pull_dir: Path) -> dict[str, Path]:
    ref_dir = pull_dir / "reference"
    ref_dir.mkdir(exist_ok=True)
    written: dict[str, Path] = {}
    for name, path in endpoints.REFERENCE_PATHS.items():
        data = client.get(path)
        out = ref_dir / f"{name}.json"
        out.write_text(json.dumps(data, default=str, indent=2))
        written[name] = out
    return written


def _relpath(path: Path) -> str:
    try:
        return str(path.relative_to(config.project_root()))
    except ValueError:
        return path.name


def extract_all(
    client: NeonClient | None = None,
    *,
    entities: tuple[str, ...] = DEFAULT_ENTITIES,
    include_reference: bool = True,
    raw_dir: Path | str | None = None,
    pull_name: str | None = None,
    run_log: bool = True,
) -> Path:
    """Pull selected entities into a dated raw folder and write a provenance manifest.

    A ``client`` may be injected (for tests or reuse); if omitted, a real ``NeonClient`` is created
    using the credentials in ``.env``.
    """
    raw_dir = Path(raw_dir) if raw_dir is not None else config.layer_dir("raw_neon")
    pull_dir = raw_dir / (pull_name or _pull_folder_name())
    pull_dir.mkdir(parents=True, exist_ok=True)

    owns_client = client is None
    if owns_client:
        client = NeonClient()

    try:
        entities_entry: dict[str, Any] = {}

        if "accounts" in entities:
            count, total, path = _extract_search(client, "accounts", pull_dir)
            entities_entry["accounts"] = _search_entry(
                "accounts", count, total, path
            )
        if "donations" in entities:
            count, total, path = _extract_search(client, "donations", pull_dir)
            entities_entry["donations"] = _search_entry(
                "donations", count, total, path
            )
        if "events" in entities:
            count, total, path = _extract_search(client, "events", pull_dir)
            entities_entry["events"] = _search_entry("events", count, total, path)
            events_path = path
        else:
            events_path = None

        if "registrations" in entities:
            count, event_count, path = _extract_registrations(
                client, pull_dir, events_path
            )
            entities_entry["registrations"] = {
                "method": "GET /events/{id}/eventRegistrations (per-event sweep)",
                "events_swept": event_count,
                "neon_total_results": None,
                "local_row_count": count,
                "file": _relpath(path),
                "sha256": manifest.sha256_file(path),
            }

        reference_entry: dict[str, Any] = {}
        if include_reference:
            for name, path in _extract_reference(client, pull_dir).items():
                reference_entry[name] = {
                    "method": f"GET {endpoints.REFERENCE_PATHS[name]}",
                    "file": _relpath(path),
                    "sha256": manifest.sha256_file(path),
                }

        entry: dict[str, Any] = {
            "pulled_at": manifest.now_iso(),
            "source": "Neon CRM API v2",
            "base_url": client.base_url,
            "search_page_size": client.page_size,
            "client": "hh.neon.client.NeonClient",
            "git_commit": manifest.git_commit(),
            "entities": entities_entry,
            "reference": reference_entry,
        }
        manifest.write_manifest(pull_dir, entry)
        if run_log:
            manifest.append_run_log(
                {
                    "pulled_at": entry["pulled_at"],
                    "pull_dir": _relpath(pull_dir),
                    "row_counts": {
                        k: v.get("local_row_count") for k, v in entities_entry.items()
                    },
                    "git_commit": entry["git_commit"],
                }
            )
        return pull_dir
    finally:
        if owns_client:
            client.close()


def _search_entry(entity: str, count: int, total: int | None, path: Path) -> dict[str, Any]:
    return {
        "method": f"POST {endpoints.SEARCH_PATHS[entity]}",
        "output_fields": endpoints.OUTPUT_FIELDS.get(entity, []),
        "neon_total_results": total,
        "local_row_count": count,
        "file": _relpath(path),
        "sha256": manifest.sha256_file(path),
    }
