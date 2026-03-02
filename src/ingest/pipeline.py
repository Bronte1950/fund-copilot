"""Orchestrate the full ingest pipeline end-to-end.

Phase 1 implementation.

Steps (in order):
    1. inventory   — scan raw_pdfs/, build manifest
    2. download    — fetch any missing PDFs from fund_sources.csv
    3. extract     — PDF → per-page JSONL (PyMuPDF)
    4. clean       — remove boilerplate, normalise
    5. chunk       — sliding window, token-sized
    6. embed       — sentence-transformers vectors
    7. index_vector — upsert into pgvector
    8. index_keyword — upsert into SQLite FTS5

Incremental: skips docs whose checksum hasn't changed (manifest tracking).
"""

from __future__ import annotations

# TODO Phase 1: wire all steps, add --force flag, structured logging, error recovery
