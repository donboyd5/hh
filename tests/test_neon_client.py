import json

import httpx
import pytest

from hh.neon.client import NeonClient


def _client(handler, **overrides):
    settings = {
        "base_url": "https://api.neoncrm.com/v2/",
        "search_page_size": 2,
        "search_min_interval_seconds": 0,
        "get_min_interval_seconds": 0,
        "max_retries_on_429": 4,
        "request_timeout_seconds": 5,
    }
    settings.update(overrides)
    transport = httpx.MockTransport(handler)
    return NeonClient(
        org_id="org",
        api_key="key",
        settings=settings,
        transport=transport,
        sleep=lambda s: None,
    )


def test_search_paginates_and_flattens():
    pages = [
        {
            "pagination": {"totalPages": 2, "totalResults": 3, "currentPage": 0, "pageSize": 2},
            "searchResults": [{"i": 1}, {"i": 2}],
        },
        {
            "pagination": {"totalPages": 2, "totalResults": 3, "currentPage": 1, "pageSize": 2},
            "searchResults": [{"i": 3}],
        },
    ]
    calls = {"n": 0}

    def handler(request):
        i = calls["n"]
        calls["n"] += 1
        return httpx.Response(200, json=pages[i])

    c = _client(handler)
    out = list(c.search("accounts"))
    c.close()
    assert [r["i"] for r in out] == [1, 2, 3]
    assert calls["n"] == 2


def test_search_pages_returns_pagination():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "pagination": {"totalPages": 1, "totalResults": 2},
                "searchResults": [{"i": 1}, {"i": 2}],
            },
        )

    c = _client(handler)
    pages = list(c.search_pages("donations"))
    c.close()
    assert len(pages) == 1
    records, pg = pages[0]
    assert records == [{"i": 1}, {"i": 2}]
    assert pg["totalResults"] == 2


def test_search_body_has_pagination_and_output_fields():
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "pagination": {"totalPages": 1, "totalResults": 1},
                "searchResults": [{"i": 1}],
            },
        )

    c = _client(handler)
    list(c.search("events", page_size=50))
    c.close()
    assert seen[0]["pagination"]["currentPage"] == 0
    assert seen[0]["pagination"]["pageSize"] == 50
    assert seen[0]["outputFields"]  # events has seeded output fields


def test_retries_on_429_then_succeeds():
    seq = [429, 429, 200]

    def handler(request):
        code = seq.pop(0)
        if code == 429:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "pagination": {"totalPages": 1, "totalResults": 1},
                "searchResults": [{"i": 9}],
            },
        )

    c = _client(handler)
    out = list(c.search("accounts"))
    c.close()
    assert out == [{"i": 9}]


def test_basic_auth_header_sent():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(
            200,
            json={"pagination": {"totalPages": 1, "totalResults": 0}, "searchResults": []},
        )

    c = _client(handler)
    list(c.search("accounts"))
    c.close()
    assert seen["auth"].startswith("Basic ")
    assert "/accounts/search" in seen["url"]


def test_get_event_registrations_pages():
    pages = [
        {"pagination": {"totalPages": 2}, "eventRegistrations": [{"r": 1}, {"r": 2}]},
        {"pagination": {"totalPages": 2}, "eventRegistrations": [{"r": 3}]},
    ]
    calls = {"n": 0}
    seen = {}

    def handler(request):
        i = calls["n"]
        calls["n"] += 1
        seen["url"] = str(request.url)
        return httpx.Response(200, json=pages[i])

    c = _client(handler)
    out = list(c.get_event_registrations("E1"))
    c.close()
    assert [r["r"] for r in out] == [1, 2, 3]
    assert "/events/E1/eventRegistrations" in seen["url"]


def test_search_unknown_entity_raises():
    c = _client(lambda req: httpx.Response(200, json={}))
    with pytest.raises(ValueError):
        list(c.search("widgets"))
    c.close()
