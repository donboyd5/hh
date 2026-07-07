"""Sweep event registrations into a pull (latest by default), concurrently & resumably.

Usage:
    python scripts/sweep_registrations.py            # latest pull under data/00_raw/neon
    python scripts/sweep_registrations.py <pull_dir>  # a specific pull

Resumable: re-running continues from where it stopped (progress sidecar). Updates the pull's
manifest with a registrations entry when finished.
"""
from __future__ import annotations

import sys
from pathlib import Path

from hh.io import latest_pull_dir
from hh.neon.client import NeonClient
from hh.neon.registrations import sweep_registrations


def main() -> None:
    pull = Path(sys.argv[1]) if len(sys.argv) > 1 else latest_pull_dir()
    if pull is None:
        raise SystemExit("No pull found under data/00_raw/neon. Run scripts/pull.py first.")
    print(f"Sweeping registrations into {pull}", flush=True)
    with NeonClient() as client:
        result = sweep_registrations(client, pull)
    print(
        f"DONE: {result['records']:,} records, "
        f"{result['events_swept']}/{result['total_events']} events swept",
        flush=True,
    )


if __name__ == "__main__":
    main()
