"""Resolve a geocodable location for every account, handling PO boxes.

Priority for each account's location:
  1. own street address              -> geo_precision = 'street'
  2. a household member's street      -> 'household'
  3. ZIP centroid (median lat/lon of  -> 'centroid'  (approximate; excluded from tight bands
     street-geocoded donors in ZIP)                  by downstream analytics)
  4. none available                   -> 'unmapped'

PO-box accounts are flagged ``po_box=True``.
"""
from __future__ import annotations

import pandas as pd

from .geocode import geocode_onelines, is_po_box, to_oneline


def geocode_accounts(accounts: pd.DataFrame, *, max_workers: int = 16) -> pd.DataFrame:
    """Return accounts with lat, lon, po_box, and geo_precision columns."""
    a = accounts.copy()
    a["po_box"] = a["address_line1"].apply(is_po_box)

    geo_addr = pd.Series(pd.NA, index=a.index, dtype=object)
    precision = pd.Series(pd.NA, index=a.index, dtype=object)

    # 1. own street address (non-PO-box)
    own = (~a["po_box"]) & a["address_line1"].notna()
    geo_addr.loc[own] = a.loc[own].apply(
        lambda r: to_oneline(r["address_line1"], r["city"], r["state_province"], r["zip_code"]),
        axis=1,
    )
    precision.loc[own] = "street"

    # 2. PO-box accounts: borrow a household member's street address
    members = a[(~a["po_box"]) & a["address_line1"].notna() & a["household_id"].notna()]
    if not members.empty:
        hh_addr = (
            members.sort_values("account_id")
            .drop_duplicates("household_id")
            .set_index("household_id")
        )
        for idx, row in a[a["po_box"]].iterrows():
            hid = row["household_id"]
            if pd.notna(hid) and hid in hh_addr.index:
                m = hh_addr.loc[hid]
                geo_addr.loc[idx] = to_oneline(
                    m["address_line1"], m["city"], m["state_province"], m["zip_code"]
                )
                precision.loc[idx] = "household"

    # geocode the resolved one-line addresses
    coords = geocode_onelines(geo_addr.tolist(), max_workers=max_workers)
    lat = pd.Series([float("nan")] * len(a), index=a.index, dtype="float64")
    lon = pd.Series([float("nan")] * len(a), index=a.index, dtype="float64")
    for idx, addr in geo_addr.items():
        ll = coords.get(addr) if isinstance(addr, str) else None
        if ll:
            lat.loc[idx] = ll[0]
            lon.loc[idx] = ll[1]

    # 3. ZIP centroid fallback for accounts still without coordinates
    have = lat.notna()
    centroids = None
    if have.any():
        geoed = a[have].assign(lat=lat[have].values, lon=lon[have].values)
        centroids = geoed.groupby("zip_code")[["lat", "lon"]].median()
    need = (~have) & a["zip_code"].notna()
    for idx in a.index[need]:
        z = a.at[idx, "zip_code"]
        if centroids is not None and z in centroids.index:
            lat.loc[idx] = centroids.at[z, "lat"]
            lon.loc[idx] = centroids.at[z, "lon"]
            precision.loc[idx] = "centroid"

    a["lat"] = lat
    a["lon"] = lon
    a["geo_precision"] = precision.fillna("unmapped")
    return a
