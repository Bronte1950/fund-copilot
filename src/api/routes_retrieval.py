"""Retrieval routes — /retrieve and /docs endpoints.

Phase 2 implementation.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["retrieval"])


@router.post("/retrieve", summary="Hybrid search over indexed chunks")
async def retrieve() -> dict:
    """Run hybrid (vector + keyword) search and return ranked chunks.

    Phase 2: implement vector_search + keyword_search + hybrid combination.
    """
    # TODO Phase 2: accept RetrievalRequest, run hybrid search, return results
    return {"error": "not_implemented", "phase": "Phase 2"}


@router.get("/docs", summary="Browse indexed documents")
async def list_docs() -> list:
    """Return all documents in the manifest with their status.

    Phase 2: query manifest.sqlite and return DocumentManifest list.
    """
    # TODO Phase 2: query manifest.sqlite
    return []
