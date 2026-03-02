"""SQLite FTS5 BM25 keyword search.

Phase 2 implementation.

Returns top-k chunks ranked by BM25 relevance to the query string.
SQLite FTS5 bm25() returns negative values — negate for a positive score.
"""

from __future__ import annotations

# TODO Phase 2: tokenise query, run FTS5 MATCH, return (chunk_id, -bm25) pairs
