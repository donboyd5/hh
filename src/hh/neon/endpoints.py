"""Neon CRM API v2 endpoint paths, per-entity output fields, and match-all search criteria.

Bulk extraction uses the ``POST */search`` endpoints (1 req/sec). Each requires at least one
``searchFields`` criterion, so a "list everything" pull uses a NOT_BLANK match-all on a
universally-populated field (``Event`` for events, ``Account ID``/``Donation ID`` for the others).

Field names mirror Neon's report columns (including ``(F)`` formatted-field suffixes). The client
validates any requested output fields against ``GET /<entity>/search/outputFields`` and drops
invalid ones (with a warning) rather than failing the request.
"""
from __future__ import annotations

BASE_URL = "https://api.neoncrm.com/v2/"

SEARCH_PATHS: dict[str, str] = {
    "accounts": "/accounts/search",
    "donations": "/donations/search",
    "events": "/events/search",
}

OUTPUT_FIELDS_PATHS: dict[str, str] = {
    "accounts": "/accounts/search/outputFields",
    "donations": "/donations/search/outputFields",
    "events": "/events/search/outputFields",
}

# A NOT_BLANK criterion on a universally-populated field matches every record.
MATCH_ALL_FIELDS: dict[str, str] = {
    "accounts": "Account ID",
    "donations": "Donation ID",
    "events": "Event",
}


def match_all_search_fields(entity: str) -> list[dict]:
    """A searchFields list that matches every record for the entity."""
    field = MATCH_ALL_FIELDS[entity]
    return [{"field": field, "operator": "NOT_BLANK", "value": ""}]


# Requested output fields per entity (validated against the API at runtime; invalid ones dropped).
OUTPUT_FIELDS: dict[str, list[str]] = {
    "accounts": [
        "Account ID",
        "Account Type",
        "First Name",
        "Last Name",
        "Full Name (F)",
        "Company Name",
        "Household ID",
        "Household Name",
        "Contact Type",
        "Deceased",
        "Do Not Contact",
        "Full Street Address (F)",
        "Address Line 1",
        "Address Line 2",
        "City",
        "State/Province",
        "Zip Code",
        "Country",
        "Email 1",
        "Phone 1 Full Number (F)",
    ],
    "donations": [
        "Donation ID",
        "Account ID",
        "Account Type",
        "Donation Date",
        "Donation Amount",
        "Donation Type",
        "Donation Status",
        "Payment Status",
        "Fund",
        "Campaign Name",
        "Purpose",
        "Source",
        "Full Name (F)",
        "Company Name",
        "City",
        "Address Line 1",
        "State/Province",
        "Zip Code",
        "Deceased",
        "Do Not Contact",
    ],
    "events": [
        "Event ID",
        "Event Name",
        "Event Category Name",
        "Event Topic",
        "Event Code",
        "Event Start Date",
        "Event End Date",
        "Event Capacity",
        "Event Registration Attendee Count",
    ],
}

# Small reference tables (5 req/sec GET endpoints) useful for lookups/categorization.
REFERENCE_PATHS: dict[str, str] = {
    "campaigns": "/campaigns",
    "event_categories": "/properties/eventCategories",
    "event_topics": "/properties/eventTopics",
    "funds": "/properties/funds",
    "sources": "/properties/sources",
    "individual_types": "/properties/individualTypes",
}


def event_id_key() -> tuple[str, ...]:
    """Candidate keys for an event id in raw event records (in priority order)."""
    return ("Event ID", "Event Id", "event_id", "id")
