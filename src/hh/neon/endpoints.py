"""Neon CRM API v2 endpoint paths and per-entity output-field selection.

The bulk-extraction endpoints are the ``POST */search`` methods (throttled to 1 req/sec). Event
registrations have NO bulk search endpoint, so they are gathered via a per-event sweep of
``GET /events/{id}/eventRegistrations``.

NOTE: the ``OUTPUT_FIELDS`` below are a best-effort starter set of human-readable field names. The
exact valid names for your Neon instance should be confirmed on the first real pull via
``NeonClient.list_output_fields(entity)`` (which calls ``GET /<entity>/search/outputFields``) and
then committed here. The R project's CSV-report column names are a close guide.
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

# Starter output-field sets (confirm via list_output_fields on first pull).
OUTPUT_FIELDS: dict[str, list[str]] = {
    "accounts": [
        "Account ID",
        "Account Type",
        "First Name",
        "Last Name",
        "Full Name",
        "Organization Name",
        "Household ID",
        "Household Name",
        "Contact Type",
        "Deceased",
        "Do Not Contact",
        "Address Line 1",
        "Address Line 2",
        "City",
        "State/Province",
        "Zip/Postal Code",
        "Country",
        "Email 1",
        "Phone 1",
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
        "Campaign",
        "Purpose",
        "Source",
        "Tribute",
        "Note",
    ],
    "events": [
        "Event ID",
        "Event Name",
        "Start Date",
        "End Date",
        "Category",
        "Topic",
        "Code",
        "Status",
        "Capacity",
        "Attendees",
        "Registered",
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
