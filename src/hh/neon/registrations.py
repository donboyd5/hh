"""Resumable, concurrent sweep of event registrations.

There is no bulk registrations search endpoint, so registrations come from
``GET /events/{id}/eventRegistrations`` (Neon allows 5 simultaneous per endpoint). With ~2,500
events at ~1s each, a sequential sweep would take ~40 min; a 5-worker pool brings it to ~8 min.

Resumable: a ``registrations.progress.txt`` sidecar records swept event ids, so an interrupted run
resumes without refetching. Records append to ``<pull_dir>/registrations.jsonl``; the pull's
manifest is updated with a registrations entry when the sweep finishes.
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from .. import io
from ..provenance import manifest
from .client import NeonClient
from .endpoints import event_id_key


def _fetch_one(client: NeonClient, event_id: str, page_size: int = 200, retries: int = 5):
    """All registration pages for one event, with retry. Returns None on persistent failure."""
    path = f"/events/{event_id}/eventRegistrations"
    for attempt in range(retries):
        try:
            r = client.raw_get(path, params={"currentPage": 0, "pageSize": page_size})
            if r.status_code == 429:
                time.sleep(min(2.0**attempt, 30.0))
                continue
            r.raise_for_status()
            data = r.json()
            records = list(data.get("eventRegistrations", []) or [])
            total_pages = (data.get("pagination") or {}).get("totalPages")
            page = 1
            while total_pages is not None and page < total_pages:
                r2 = client.raw_get(path, params={"currentPage": page, "pageSize": page_size})
                r2.raise_for_status()
                records.extend((r2.json() or {}).get("eventRegistrations", []) or [])
                page += 1
            return records
        except (httpx.TimeoutException, httpx.NetworkError):
            time.sleep(min(2.0**attempt, 30.0))
    return None


def sweep_registrations(
    client: NeonClient,
    pull_dir: Path | str,
    *,
    max_workers: int = 5,
    page_size: int = 200,
    resume: bool = True,
) -> dict:
    """Concurrently sweep registrations for every event in ``pull_dir/events.jsonl``.

    Resumable: skips events already recorded in ``registrations.progress.txt``.
    """
    pull_dir = Path(pull_dir)
    events_path = pull_dir / "events.jsonl"
    out_path = pull_dir / "registrations.jsonl"
    progress_path = pull_dir / "registrations.progress.txt"

    event_ids = _event_ids(events_path)
    swept = (
        set(progress_path.read_text().splitlines())
        if resume and progress_path.exists()
        else set()
    )
    todo = [e for e in event_ids if e not in swept]
    print(
        f"[neon] registrations: {len(event_ids)} events, {len(swept)} swept, {len(todo)} to do",
        flush=True,
    )

    count = 0
    failed: list[str] = []
    done = 0
    with out_path.open("a") as fout, progress_path.open("a") as fprog:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_fetch_one, client, eid, page_size): eid for eid in todo
            }
            for fut in as_completed(futures):
                eid = futures[fut]
                records = fut.result()
                if records is None:
                    failed.append(eid)
                else:
                    for record in records:
                        record["_swept_event_id"] = eid
                        fout.write(json.dumps(record, default=str) + "\n")
                    fprog.write(eid + "\n")
                    fout.flush()
                    fprog.flush()
                    count += len(records)
                done += 1
                if done % 200 == 0 or done == len(todo):
                    print(
                        f"[neon] registrations: {done}/{len(todo)} events, {count:,} records",
                        flush=True,
                    )

    print(
        f"[neon] registrations DONE: {count:,} records from {done} events"
        f" ({len(failed)} failed)",
        flush=True,
    )
    _update_manifest(pull_dir, out_path, len(event_ids), len(swept) + done, count, failed)
    return {
        "records": count,
        "events_swept": len(swept) + done,
        "total_events": len(event_ids),
        "failed": failed,
    }


def _event_ids(events_path: Path) -> list[str]:
    ids: list[str] = []
    for record in io.read_jsonl(events_path):
        for key in event_id_key():
            value = record.get(key)
            if value:
                ids.append(str(value))
                break
    return ids


def _update_manifest(pull_dir, out_path, total_events, swept, count, failed):
    mpath = pull_dir / "manifest.yaml"
    if not mpath.exists():
        return
    entry = manifest.read_manifest(mpath)
    entry.setdefault("entities", {})["registrations"] = {
        "method": "GET /events/{id}/eventRegistrations (concurrent sweep, 5 workers)",
        "events_swept": swept,
        "total_events": total_events,
        "failed_events": len(failed),
        "neon_total_results": None,
        "local_row_count": count,
        "file": manifest._relpath(out_path) if hasattr(manifest, "_relpath") else out_path.name,
        "sha256": manifest.sha256_file(out_path),
    }
    manifest.write_manifest(pull_dir, entry)
