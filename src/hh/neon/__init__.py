"""Neon CRM API v2 client and extractors.

Thin sync client (HTTP Basic auth) over https://api.neoncrm.com/v2/, with a
1-request/second paginator for the bulk ``*/search`` endpoints, 429 backoff, and a
per-event registration sweeper (there is no bulk registrations search endpoint).
"""
