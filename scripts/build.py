"""Build the analytics-ready dataset from saved raw data (no API/key needed; geocode cache reused).

Produces data/20_processed/:
  accounts_geocoded.parquet       accounts + lat/lon + distance band + geo_precision
  registrations_enriched.parquet  registrations + event category + weekday + attendee band
  households_summary.parquet      one row per household: geography + donations + attendance + flags
  appeal_recipients.parquet       FY26 fall-appeal mailing list, cleaned (from data/30_external)
  appeal_households.parquet       one row per household: appealed/responded + prior giving +
                                  as-of-appeal engagement (full Neon universe)
  eoy_export_gifts.parquet        end-of-year FY26 campaign export, standardized (QA cross-check)

Run after `scripts/pull.py` (and the first `scripts/geocode.py`). Reruns are fast and offline.
"""
from __future__ import annotations

from hh import io
from hh.analytics.appeal import appeal_household_table
from hh.analytics.households import household_summary
from hh.analytics.registrations_enriched import enrich_registrations
from hh.clean.accounts import clean_accounts
from hh.clean.donations import clean_donations
from hh.clean.events import clean_events
from hh.clean.registrations import clean_registrations
from hh.external import appeal as appeal_ext
from hh.external import eoy as eoy_ext
from hh.external import provenance as ext_provenance
from hh.geo.distance import assign_bands
from hh.geo.geocode import geocode_one
from hh.geo.resolve import geocode_accounts
from hh.provenance import manifest

VENUE_ADDRESS = "25 E Main St, Cambridge, NY 12816"


def build_appeal(accounts_geo, donations, registrations) -> None:
    """FY26 appeal stage. Skipped (with a message) when the workbooks are absent — a fresh
    clone has no data/, and the public book must build unchanged without the appeal files."""
    appeal_file = appeal_ext.appeal_path()
    if not appeal_file.exists():
        print("appeal workbooks not found in data/30_external — skipping appeal stage", flush=True)
        return

    sheets = appeal_ext.load_appeal_sheets(appeal_file)
    recipients = appeal_ext.clean_appeal_recipients(sheets)
    qa = appeal_ext.appeal_load_qa(sheets, recipients)
    table = appeal_household_table(recipients, accounts_geo, donations, registrations)

    io.write_parquet(recipients, "processed", "appeal_recipients.parquet")
    io.write_parquet(table, "processed", "appeal_households.parquet")
    ext_provenance.append_external_manifest(
        ext_provenance.external_source_entry(appeal_file, "FY26 fall appeal mailing list"),
        slug="fall-appeal-2025",
    )

    eoy_file = eoy_ext.eoy_path()
    if eoy_file.exists():
        eoy = eoy_ext.clean_eoy_gifts(eoy_ext.load_eoy_gifts(eoy_file))
        io.write_parquet(eoy, "processed", "eoy_export_gifts.parquet")
        ext_provenance.append_external_manifest(
            ext_provenance.external_source_entry(eoy_file, "EoY FY26 campaign donations export"),
            slug="eoy-fy26",
        )
    else:
        eoy = None

    appealed = int(table["appealed"].sum())
    responded = int((table["appealed"] & table["responded"]).sum())
    manifest.append_run_log(
        {
            "recorded_at": manifest.now_iso(),
            "stage": "appeal",
            "git_commit": manifest.git_commit(),
            "appeal_qa": qa,
            "rows": {
                "recipients": len(recipients),
                "appeal_households": len(table),
                "appealed_households": appealed,
                "responding_households": responded,
                "eoy_gifts": len(eoy) if eoy is not None else None,
            },
        }
    )
    print(
        f"appeal: recipients={len(recipients)} households={len(table)} "
        f"appealed={appealed} responded={responded}",
        flush=True,
    )


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

    print("appeal stage...", flush=True)
    build_appeal(accounts_geo, donations, registrations)

    print(
        f"done: accounts={len(accounts_geo)} registrations={len(reg_enriched)} "
        f"households={len(households)}",
        flush=True,
    )
    print("saved to data/20_processed/", flush=True)


if __name__ == "__main__":
    main()
