"""Run a Neon pull and print a summary. Saves to data/00_raw/neon/pull-<UTC>/ with a manifest.

Usage:
    python scripts/pull.py                 # all entities
    python scripts/pull.py accounts donations events   # a subset (no registrations sweep)

Every retrieved record is streamed straight to disk, so the data is saved even if the run is
interrupted. Registrations require events (swept per-event), so requesting 'registrations' also
pulls events.
"""
from __future__ import annotations

import sys

from hh.neon.extract import DEFAULT_ENTITIES, extract_all
from hh.provenance import manifest


def main() -> None:
    ents = tuple(sys.argv[1:]) or DEFAULT_ENTITIES
    if "registrations" in ents and "events" not in ents:
        ents = ("events",) + ents
    print(f"Neon pull starting: {ents}", flush=True)
    pull_dir = extract_all(entities=ents, include_reference=True)
    print(f"PULL COMPLETE: {pull_dir}", flush=True)
    m = manifest.read_manifest(pull_dir / "manifest.yaml")
    for entity, info in m["entities"].items():
        print(
            f"  {entity}: local={info.get('local_row_count')} "
            f"neon_total={info.get('neon_total_results')}",
            flush=True,
        )
    print(f"manifest: {pull_dir / 'manifest.yaml'}", flush=True)


if __name__ == "__main__":
    main()
