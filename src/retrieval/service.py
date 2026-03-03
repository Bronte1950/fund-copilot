"""High-level retrieval interface used by the API.

Orchestrates:
  1. Embed query + keyword search in parallel (both are sync/CPU-bound).
  2. Await vector search (async asyncpg).
  3. Fuse with hybrid_combine.
  4. Enrich results with file_name from manifest.sqlite.
"""

from __future__ import annotations

import asyncio
import sqlite3

from src.common.db import MANIFEST_DB_PATH
from src.common.schemas import RetrievalRequest, RetrievalResult
from src.retrieval.hybrid import hybrid_combine
from src.retrieval.keyword_search import keyword_search
from src.retrieval.vector_search import embed_query, vector_search


def _fetch_file_names(doc_ids: list[str]) -> dict[str, str]:
    """Synchronous manifest lookup — run in threadpool from async context."""
    if not doc_ids:
        return {}
    conn = sqlite3.connect(str(MANIFEST_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" * len(doc_ids))
        rows = conn.execute(
            f"SELECT doc_id, file_name FROM documents WHERE doc_id IN ({placeholders})",
            doc_ids,
        ).fetchall()
        return {r["doc_id"]: r["file_name"] for r in rows}
    finally:
        conn.close()


async def retrieve(request: RetrievalRequest) -> list[RetrievalResult]:
    """Run hybrid retrieval and return top-k fused results.

    Parallel phase: embedding + keyword search run concurrently.
    Sequential phase: vector search uses the embedding from the parallel phase.
    """
    fetch_k = max(request.top_k * 2, 20)

    # Embed query and run keyword search concurrently
    query_vec, keyword_results = await asyncio.gather(
        asyncio.to_thread(embed_query, request.query),
        asyncio.to_thread(keyword_search, request.query, fetch_k, request),
    )

    # Vector search uses the now-ready embedding
    vector_results = await vector_search(query_vec, fetch_k, request)

    # Fuse both lists
    results = hybrid_combine(vector_results, keyword_results, request.top_k)

    # Enrich with file names (manifest lookup)
    doc_ids = list({r.doc_id for r in results})
    file_names = await asyncio.to_thread(_fetch_file_names, doc_ids)
    for r in results:
        r.source_file = file_names.get(r.doc_id, "")

    return results
