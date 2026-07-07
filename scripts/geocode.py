"""Bulk-geocode all account addresses (with PO-box resolution) and assign distance bands.

Resolves each account to the best location (own street -> household member -> ZIP centroid), then
assigns <=1 / <=10 / <=20 / >20 mile bands to the Hubbard Hall venue, and writes the result to
data/20_processed/accounts_geocoded.parquet.
"""
from __future__ import annotations

from hh import io
from hh.clean.accounts import clean_accounts
from hh.geo.distance import assign_bands
from hh.geo.geocode import geocode_one
from hh.geo.resolve import geocode_accounts

VENUE_ADDRESS = "25 E Main St, Cambridge, NY 12816"


def main() -> None:
    accounts = clean_accounts()
    venue = geocode_one(VENUE_ADDRESS)
    vlat, vlon = venue if venue else (43.028, -73.380)
    print(f"venue: ({vlat:.5f}, {vlon:.5f})", flush=True)

    accounts = geocode_accounts(accounts, max_workers=16)
    accounts = assign_bands(accounts, venue_lat=vlat, venue_lon=vlon)
    io.write_parquet(accounts, "processed", "accounts_geocoded.parquet")

    print("geo_precision:", accounts["geo_precision"].value_counts().to_dict(), flush=True)
    print("po_box:", int(accounts["po_box"].sum()), flush=True)
    print("bands:", accounts["distance_band"].value_counts(dropna=False).to_dict(), flush=True)
    print("saved: data/20_processed/accounts_geocoded.parquet", flush=True)


if __name__ == "__main__":
    main()
