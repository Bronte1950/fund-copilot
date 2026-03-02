"""Upsert chunk text into SQLite FTS5 for BM25 keyword search.

Phase 1 implementation.

Schema:
    CREATE VIRTUAL TABLE fts USING fts5(
        chunk_id UNINDEXED,
        doc_id UNINDEXED,
        text,
        content='chunks_meta',
        content_rowid='rowid'
    );
"""

from __future__ import annotations

# TODO Phase 1: create FTS5 table, populate from chunks JSONL, handle updates
