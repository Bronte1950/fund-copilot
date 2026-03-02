"""Upsert chunk vectors into pgvector.

Phase 1 implementation.

Schema:
    CREATE TABLE chunks (
        chunk_id     TEXT PRIMARY KEY,
        doc_id       TEXT NOT NULL,
        embedding    vector(384),
        text         TEXT,
        metadata     JSONB,
        page_start   INT,
        page_end     INT,
        section_heading TEXT
    );
    CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
"""

from __future__ import annotations

# TODO Phase 1: CREATE TABLE IF NOT EXISTS, batch upsert, handle conflicts
