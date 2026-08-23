"""External staff-maintained workbooks (data/30_external): loading, cleaning, provenance.

Unlike the Neon pulls, these files arrive as emailed spreadsheets with no API behind them, so
provenance is recorded as file checksums (:mod:`hh.external.provenance`) rather than pull
manifests. Each workbook gets its own loader module with the same pure-function style as
``hh.clean`` — loaders read the file, cleaners transform in-memory frames so tests never need
the real (PII) data.
"""
