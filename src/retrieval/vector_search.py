"""pgvector cosine similarity search.

Score: 1 - cosine_distance  (range 0–1, higher = more similar).
Query is embedded with the same model used at index time (all-MiniLM-L6-v2).
"""

from __future__ import annotations

import json

from src.common.db import get_postgres_conn
from src.common.schemas import RetrievalRequest, RetrievalResult

_VECTOR_SQL = """
SELECT
    chunk_id,
    doc_id,
    1 - (embedding <=> $1::vector) AS score,
    text,
    metadata,
    page_start,
    page_end,
    section_heading
FROM chunks
WHERE (metadata->>'doc_type' = $3 OR $3 IS NULL)
  AND (metadata->>'provider' = $4 OR $4 IS NULL)
  AND (metadata->>'isin'     = $5 OR $5 IS NULL)
ORDER BY embedding <=> $1::vector
LIMIT $2
"""


def embed_query(text: str) -> list[float]:
    """Embed a single query string using the shared model singleton."""
    from src.ingest.embed import _get_model

    model = _get_model()
    vec = model.encode(
        [text],
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )[0]
    return vec.tolist()


async def vector_search(
    query_vec: list[float],
    top_k: int,
    request: RetrievalRequest,
) -> list[RetrievalResult]:
    """Run a pgvector cosine ANN search and return scored RetrievalResults."""
    vec_str = "[" + ",".join(f"{v:.8f}" for v in query_vec) + "]"

    async with get_postgres_conn() as conn:
        rows = await conn.fetch(
            _VECTOR_SQL,
            vec_str,
            top_k,
            request.doc_type,
            request.provider,
            request.isin,
        )

    results = []
    for row in rows:
        meta_raw = row["metadata"]
        meta = meta_raw if isinstance(meta_raw, dict) else json.loads(meta_raw or "{}")
        results.append(
            RetrievalResult(
                chunk_id=row["chunk_id"],
                doc_id=row["doc_id"],
                score=float(row["score"]),
                text=row["text"],
                page_start=row["page_start"],
                page_end=row["page_end"],
                section_heading=row["section_heading"],
                source_file="",  # enriched in service.py
                provider=meta.get("provider"),
                fund_name=meta.get("fund_name"),
                search_type="vector",
            )
        )
    return results
