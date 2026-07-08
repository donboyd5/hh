"""Build the analytics-ready dataset from saved raw data (no API/key needed; geocode cache reused).

Produces data/20_processed/:
  accounts_geocoded.parquet       accounts + lat/lon + distance band + geo_precision
  registrations_enriched.parquet  registrations + event category + weekday + attendee band
  households_summary.parquet      one row per household: geography + donations + attendance + flags

Run after `scripts/pull.py` (and the first `scripts/geocode.py`). Reruns are fast and offline.
"""
from __future__ import annotations

from hh import io
from hh.analytics.households import household_summary
from hh.analytics.registrations_enriched import enrich_registrations
from hh.clean.accounts import clean_accounts
from hh.clean.donations import clean_donations
from hh.clean.events import clean_events
from hh.clean.registrations import clean_registrations
from hh.geo.distance import assign_bands
from hh.geo.geocode import geocode_one
from hh.geo.resolve import geocode_accounts

VENUE_ADDRESS = "25 E Main St, Cambridge, NY 12816"


def main() -> None:
    print("cleaning...", flush=True)
    accounts = clean_accounts()
    events = clean_events()
    donations = clean_donations(accounts=accounts)
    registrations = clean_registrations(events=events, accounts=accounts)

    print("geocoding (cache reused)...", flush=True)
    venue = geocode_one(VENUE_ADDRESS)
    vlat, vlon = venue if venue else (43.028, -73.380)
    accounts_geo = assign_bands(
        geocode_accounts(accounts), venue_lat=vlat, venue_lon=vlon
    )

    print("enriching + summarizing...", flush=True)
    reg_enriched = enrich_registrations(registrations, accounts_geo)
    households = household_summary(accounts_geo, donations, registrations)

    io.write_parquet(accounts_geo, "processed", "accounts_geocoded.parquet")
    io.write_parquet(reg_enriched, "processed", "registrations_enriched.parquet")
    io.write_parquet(households, "processed", "households_summary.parquet")

    print(
        f"done: accounts={len(accounts_geo)} registrations={len(reg_enriched)} "
        f"households={len(households)}",
        flush=True,
    )
    print("saved to data/20_processed/", flush=True)


if __name__ == "__main__":
    main()
