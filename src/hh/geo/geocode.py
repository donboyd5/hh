"""Geocoding via the US Census onelineaddress endpoint (reliable, no API key).

The Census batch endpoint proved flaky (intermittent 502s + an inconsistent coordinate format), so
bulk geocoding uses concurrent oneline requests with retry and a local cache (data/90_cache/) keyed
by address — a one-time cost; reruns read from cache. PO-box addresses are flagged, not dropped.
"""
from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
import pandas as pd

from .. import config

CENSUS_ONELINE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
BENCHMARK = "Public_AR_Current"
_PO_BOX_TOKENS = ("po box", "p.o. box", "p.o.box", "p.o box", "pob ")


def _clean(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()


def is_po_box(street) -> bool:
    """True if the street looks like a PO box (case-insensitive)."""
    if not isinstance(street, str):
        return False
    s = street.strip().lower()
    return any(tok in s for tok in _PO_BOX_TOKENS)


def to_oneline(street, city, state, zip_code) -> str:
    """Build a one-line address: 'street, city, state zip'."""
    parts = [_clean(street), _clean(city)]
    state_zip = (_clean(state) + " " + _clean(zip_code)).strip()
    if state_zip:
        parts.append(state_zip)
    return ", ".join(p for p in parts if p)


def geocode_one(address: str, *, retries: int = 3) -> tuple[float, float] | None:
    """Geocode a one-line address; returns (lat, lon) or None, with retry."""
    if not address or not address.strip():
        return None
    for attempt in range(retries):
        try:
            r = httpx.get(
                CENSUS_ONELINE_URL,
                params={"address": address, "benchmark": BENCHMARK, "format": "json"},
                timeout=30,
            )
            if r.status_code >= 500:
                time.sleep(1.0 * (attempt + 1))
                continue
            r.raise_for_status()
            matches = (r.json() or {}).get("result", {}).get("addressMatches", [])
            if not matches:
                return None
            coords = matches[0]["coordinates"]
            return float(coords["y"]), float(coords["x"])  # y = lat, x = lon
        except (httpx.TimeoutException, httpx.NetworkError):
            time.sleep(1.0 * (attempt + 1))
    return None


def _cache_path() -> Path:
    p = config.resolve_path(config.load_settings()["paths"]["geocode_cache"])
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def geocode_addresses(
    df: pd.DataFrame,
    *,
    id_col: str = "account_id",
    street_col: str = "address_line1",
    city_col: str = "city",
    state_col: str = "state_province",
    zip_col: str = "zip_code",
    max_workers: int = 8,
    use_cache: bool = True,
) -> pd.DataFrame:
    """Concurrently geocode a DataFrame of addresses, with caching.

    Returns a DataFrame keyed by ``id``: id, lat, lon, matched, po_box.
    """
    items = []
    for _, r in df.iterrows():
        rid = str(r[id_col]) if id_col in df.columns else str(r.name)
        street = _clean(r.get(street_col))
        oneline = to_oneline(
            street,
            _clean(r.get(city_col)),
            _clean(r.get(state_col)),
            _clean(r.get(zip_col)),
        )
        items.append((rid, oneline, is_po_box(street)))

    cache: dict[str, tuple] = {}
    if use_cache:
        cp = _cache_path()
        if cp.exists():
            cached = pd.read_parquet(cp)
            cache = {
                row["address"]: (row["lat"], row["lon"], bool(row["matched"]))
                for _, row in cached.iterrows()
            }

    uncached = list(dict.fromkeys(a for _, a, _ in items if a and a not in cache))
    if uncached:
        print(
            f"[geocode] {len(uncached)} new to geocode ({len(cache)} cached)",
            flush=True,
        )
        new: dict[str, tuple[float, float] | None] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(geocode_one, addr): addr for addr in uncached}
            done = 0
            for fut in as_completed(futures):
                addr = futures[fut]
                try:
                    new[addr] = fut.result()
                except Exception:
                    new[addr] = None
                done += 1
                if done % 250 == 0 or done == len(uncached):
                    matched = sum(1 for v in new.values() if v)
                    print(f"[geocode] {done}/{len(uncached)} ({matched} matched)", flush=True)
        for addr, ll in new.items():
            cache[addr] = (ll[0], ll[1], ll is not None) if ll else (None, None, False)
        if use_cache:
            rows = [
                {"address": a, "lat": v[0], "lon": v[1], "matched": v[2]}
                for a, v in cache.items()
            ]
            pd.DataFrame(rows).to_parquet(_cache_path(), index=False)

    out = []
    for rid, oneline, pob in items:
        lat = lon = None
        matched = False
        if oneline and oneline in cache:
            lat, lon, matched = cache[oneline]
        out.append((rid, lat, lon, matched, pob))
    return pd.DataFrame(out, columns=["id", "lat", "lon", "matched", "po_box"])
