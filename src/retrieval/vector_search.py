"""pgvector cosine similarity search.

Phase 2 implementation.

Returns top-k chunks nearest to the query embedding.
Score: 1 - cosine_distance  (range 0–1, higher = more similar)
"""

from __future__ import annotations

# TODO Phase 2: embed query with same model, run:
#   SELECT chunk_id, 1 - (embedding <=> $1) AS score, ...
#   FROM chunks ORDER BY embedding <=> $1 LIMIT $2
