"""Thin synchronous client for the Neon CRM REST API v2.

- HTTP Basic auth (username = Org ID, password = API key).
- ``search_pages()`` / ``search()`` paginate the bulk ``POST */search`` endpoints, throttled to the
  1-req/sec limit, with exponential backoff on ``429``.
- ``get_event_registrations(event_id)`` sweeps the per-event registration endpoint (there is no bulk
  registrations search).
- Injectable ``transport`` (httpx.MockTransport) and ``sleep`` make it fully unit-testable offline.
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import httpx

from .. import config
from . import endpoints


class NeonClient:
    def __init__(
        self,
        org_id: str | None = None,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        settings: dict | None = None,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
    ) -> None:
        settings = settings if settings is not None else config.neon_settings()
        if org_id is None or api_key is None:
            org_id, api_key = config.get_neon_credentials()
        self.base_url = base_url or settings.get("base_url", endpoints.BASE_URL)
        self.page_size = int(settings.get("search_page_size", 200))
        self.search_interval = float(settings.get("search_min_interval_seconds", 1.1))
        self.get_interval = float(settings.get("get_min_interval_seconds", 0.2))
        self.max_retries = int(settings.get("max_retries_on_429", 8))
        self.timeout = float(settings.get("request_timeout_seconds", 30))
        self._sleep = sleep
        self._last_request_at = 0.0
        self._client = httpx.Client(
            base_url=self.base_url,
            auth=httpx.BasicAuth(org_id, api_key),
            timeout=self.timeout,
            transport=transport,
            headers={"Content-Type": "application/json"},
        )

    # -- context manager ---------------------------------------------------
    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NeonClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # -- low-level ---------------------------------------------------------
    def _throttle(self, interval: float) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            self._sleep(interval - elapsed)
        self._last_request_at = time.monotonic()

    def _request(
        self,
        method: str,
        path: str,
        *,
        interval: float,
        **kwargs: Any,
    ) -> httpx.Response:
        """Issue one request with throttle + 429 backoff; raise on other errors."""
        response: httpx.Response | None = None
        for attempt in range(self.max_retries + 1):
            self._throttle(interval)
            response = self._client.request(method, path, **kwargs)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after is not None else min(2.0**attempt, 30.0)
                self._sleep(delay)
                continue
            response.raise_for_status()
            return response
        assert response is not None
        response.raise_for_status()
        return response

    # -- search (bulk) -----------------------------------------------------
    def search_pages(
        self,
        entity: str,
        *,
        search_fields: list[dict] | None = None,
        output_fields: list[str] | None = None,
        page_size: int | None = None,
    ) -> Iterator[tuple[list[dict], dict]]:
        """Yield ``(records, pagination)`` per page for a ``POST /<entity>/search`` endpoint."""
        if entity not in endpoints.SEARCH_PATHS:
            raise ValueError(f"Unknown search entity {entity!r}")
        path = endpoints.SEARCH_PATHS[entity]
        page_size = page_size or self.page_size
        if output_fields is None:
            output_fields = endpoints.OUTPUT_FIELDS.get(entity, [])
        page = 0
        while True:
            body = {
                "searchFields": search_fields or [],
                "outputFields": output_fields,
                "pagination": {"currentPage": page, "pageSize": page_size},
            }
            data = self._request(
                "POST", path, interval=self.search_interval, json=body
            ).json()
            pagination = data.get("pagination", {}) or {}
            records = data.get("searchResults", []) or []
            yield records, pagination
            total_pages = pagination.get("totalPages")
            if total_pages is not None:
                if page + 1 >= total_pages:
                    break
            elif len(records) < page_size:
                break
            if not records:
                break
            page += 1

    def search(self, entity: str, **kwargs: Any) -> Iterator[dict]:
        """Flatten ``search_pages`` into a stream of records."""
        for records, _ in self.search_pages(entity, **kwargs):
            yield from records

    # -- single GET --------------------------------------------------------
    def get(self, path: str, *, params: dict | None = None, interval: float | None = None) -> Any:
        return self._request(
            "GET", path, interval=self.get_interval if interval is None else interval, params=params
        ).json()

    def get_event_registrations(self, event_id: str, *, page_size: int = 200) -> Iterator[dict]:
        """Page through ``GET /events/{id}/eventRegistrations``.

        The response's results list is expected under ``eventRegistrations`` (with ``pagination``),
        matching the rest of the API. Confirm on first real pull.
        """
        path = f"/events/{event_id}/eventRegistrations"
        page = 0
        while True:
            data = self.get(
                path, params={"currentPage": page, "pageSize": page_size}
            )
            pagination = data.get("pagination", {}) or {}
            records = data.get("eventRegistrations", []) or []
            yield from records
            total_pages = pagination.get("totalPages")
            if total_pages is not None:
                if page + 1 >= total_pages:
                    break
            elif len(records) < page_size:
                break
            if not records:
                break
            page += 1

    def list_output_fields(self, entity: str) -> list[dict]:
        """Fetch the valid output fields for a search entity (for first-pull validation)."""
        if entity not in endpoints.OUTPUT_FIELDS_PATHS:
            raise ValueError(f"No outputFields endpoint for {entity!r}")
        data = self.get(endpoints.OUTPUT_FIELDS_PATHS[entity])
        return data if isinstance(data, list) else data.get("outputFields", [])
