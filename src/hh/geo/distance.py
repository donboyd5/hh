"""Haversine distance and distance bands from the Hubbard Hall venue.

Straight-line (great-circle) distance in miles, bucketed into <=1 / <=10 / <=20 / >20 mi bands.
Vectorized over arrays for speed on thousands of addresses.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

EARTH_RADIUS_MILES = 3958.8
DEFAULT_BANDS = (1, 5, 10, 20)


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance in miles between two points (scalars, degrees)."""
    r = math.radians
    dlat = r(lat2 - lat1)
    dlon = r(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


def haversine_vec(lat1, lon1, lat2, lon2):
    """Vectorized great-circle distance in miles (numpy arrays / pandas Series, degrees)."""
    lat1r = np.radians(lat1)
    lon1r = np.radians(lon1)
    lat2r = np.radians(lat2)
    lon2r = np.radians(lon2)
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * np.arcsin(np.sqrt(a))


def band_labels(bands=DEFAULT_BANDS) -> list[str]:
    """Ordered half-open interval labels, e.g. '[0, 1)', '[1, 5)', ..., '[20, ∞)'."""
    edges = [0, *bands]
    labels = [f"[{edges[i]}, {edges[i + 1]})" for i in range(len(edges) - 1)]
    labels.append(f"[{bands[-1]}, ∞)")
    return labels


def band_label(distance: float, bands=DEFAULT_BANDS) -> str | None:
    """Half-open interval label for one distance, or None if distance is missing."""
    if distance is None or (isinstance(distance, float) and math.isnan(distance)):
        return None
    edges = [0, *bands]
    for i in range(len(edges) - 1):
        if distance < edges[i + 1]:
            return f"[{edges[i]}, {edges[i + 1]})"
    return f"[{bands[-1]}, ∞)"


def band_series(distances, bands=DEFAULT_BANDS):
    """Categorize a Series of distances into ordered half-open interval labels."""
    s = pd.Series(distances)
    result = pd.Series([None] * len(s), dtype=object, index=s.index)
    remaining = s.notna()
    edges = [0, *bands]
    for i in range(len(edges) - 1):
        mask = remaining & (s < edges[i + 1])
        result[mask] = f"[{edges[i]}, {edges[i + 1]})"
        remaining = remaining & ~mask
    result[remaining] = f"[{bands[-1]}, ∞)"
    return pd.Categorical(result, categories=band_labels(bands), ordered=True)


def assign_bands(
    df: pd.DataFrame,
    *,
    lat_col: str = "lat",
    lon_col: str = "lon",
    venue_lat: float,
    venue_lon: float,
    bands=DEFAULT_BANDS,
) -> pd.DataFrame:
    """Add distance_miles and distance_band (haversine to the venue) to a copy of df."""
    out = df.copy()
    out["distance_miles"] = haversine_vec(out[lat_col], out[lon_col], venue_lat, venue_lon)
    out["distance_band"] = band_series(out["distance_miles"], bands)
    return out
