"""Lightweight, PII-safe probe of the Neon CRM API connection.

Verifies credentials + connectivity against the live Hubbard Hall Neon system with a few cheap
read-only calls, and reveals the real API field/category names (validating the seeded assumptions in
hh.neon.endpoints). Prints ONLY structural info (field names, category names, counts) — never donor
values. Safe to re-run anytime.
"""
from __future__ import annotations

import sys

from hh import config
from hh.neon import endpoints
from hh.neon.client import NeonClient


def main() -> None:
    # 1. credentials
    try:
        org, key = config.get_neon_credentials()
    except RuntimeError as e:
        print("CREDENTIAL ERROR:", e)
        sys.exit(1)
    print("credentials: NEON_ORG_ID and NEON_API_KEY both present (values hidden)")

    with NeonClient(org_id=org, api_key=key, settings=config.neon_settings()) as c:
        # 2. cheap read-only GET: event categories (also confirms auth)
        try:
            cats = c.get("/properties/eventCategories")
            cat_list = cats if isinstance(cats, list) else cats.get("eventCategories", [])
            sample = [
                (x.get("name") if isinstance(x, dict) else x) for x in cat_list[:10]
            ]
            print(f"\nGET /properties/eventCategories -> OK ({len(cat_list)} categories)")
            print("  sample:", sample)
        except Exception as e:  # noqa: BLE001 - probe wants to keep going
            print(f"\nGET /properties/eventCategories FAILED: {type(e).__name__}: {e}")

        # 3. output-field validation for each seeded entity
        for entity in ("accounts", "events"):
            try:
                valid = set(c.list_output_fields(entity))
                seeded = set(endpoints.OUTPUT_FIELDS[entity])
                missing = sorted(seeded - valid)
                print(f"\nGET /{entity}/search/outputFields -> OK ({len(valid)} valid fields)")
                print(
                    f"  seeded fields NOT valid for {entity}: "
                    + (", ".join(missing) if missing else "NONE - all seeded fields valid")
                )
            except Exception as e:  # noqa: BLE001
                print(f"\nGET /{entity}/search/outputFields FAILED: {type(e).__name__}: {e}")

        # 4. tiny events search: pagination check + record field KEYS only (no values)
        try:
            first = next(c.search_pages("events", page_size=3, validate_fields=True), None)
            if first is None:
                print("\nPOST /events/search -> OK but no pages returned")
            else:
                records, pg = first
                print(
                    f"\nPOST /events/search -> OK "
                    f"(totalResults={pg.get('totalResults')}, page returned {len(records)})"
                )
                if records:
                    print("  record field keys:", sorted(records[0].keys()))
        except Exception as e:  # noqa: BLE001
            print(f"\nPOST /events/search FAILED: {type(e).__name__}: {e}")

    print("\nPROBE DONE.")


if __name__ == "__main__":
    main()
