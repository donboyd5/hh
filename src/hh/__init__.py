"""Hubbard Hall data analysis (Neon CRM).

A provenance-driven Python pipeline that ingests data from the Neon CRM REST API v2,
cleans and categorizes it, adds a geospatial + timing layer, and publishes findings
as Quarto web books for the Hubbard Hall board.

Layers (see ``data/``):
    00_raw      immutable API/CSV extracts           (one dated folder per pull)
    10_interim  typed, column-standardized           (regenerable)
    20_processed analytics-ready tables              (regenerable)
    30_external reference data (geocodes, boundaries) (regenerable)
    90_cache    geocode cache

Every pull is recorded in a provenance manifest so any figure is reproducible.
"""

__version__ = "0.1.0"
