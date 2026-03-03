"""Retrieval routes — /retrieve and /docs endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.common.db import MANIFEST_DB_PATH, get_sqlite_conn
from src.common.schemas import RetrievalRequest, RetrievalResult
from src.retrieval.service import retrieve as _retrieve

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", summary="Hybrid search over indexed chunks")
async def retrieve(request: RetrievalRequest) -> list[RetrievalResult]:
    """Run hybrid (vector + keyword) search and return top-k ranked chunks.

    - **query**: natural-language question or keyword string
    - **top_k**: maximum results to return (default 10)
    - **provider** / **doc_type** / **isin**: optional pre-filters
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")
    return await _retrieve(request)


@router.get("/docs", summary="Browse indexed documents")
async def list_docs(
    provider: str | None = None,
    doc_type: str | None = None,
) -> list[dict]:
    """Return all documents in the manifest.

    Optional query parameters:
    - **provider**: e.g. `Vanguard`, `iShares`, `LGIM`
    - **doc_type**: `factsheet` | `kid` | `prospectus` | `annual_report` | `other`
    """
    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        sql = "SELECT * FROM documents WHERE 1=1"
        params: list = []
        if provider:
            sql += " AND provider = ?"
            params.append(provider)
        if doc_type:
            sql += " AND doc_type = ?"
            params.append(doc_type)
        sql += " ORDER BY provider, file_name"
        rows = conn.execute(sql, params).fetchall()

    return [dict(r) for r in rows]
