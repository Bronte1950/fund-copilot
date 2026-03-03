"""Admin routes — /health and /admin/* endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter

from src.common.config import settings
from src.common.db import check_postgres
from src.common.logging import get_logger

router = APIRouter(tags=["admin"])
log = get_logger(__name__)


async def _check_ollama() -> dict:
    """Ping Ollama and return a status dict with available models."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
        return {"status": "ok", "models": models}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@router.get("/health", summary="Service health check")
async def health() -> dict:
    """Return the live status of every downstream service.

    - **ok**: all services reachable
    - **degraded**: one or more services unreachable (API still answers)
    """
    postgres = await check_postgres()
    ollama = await _check_ollama()

    overall = (
        "ok"
        if postgres["status"] == "ok" and ollama["status"] == "ok"
        else "degraded"
    )

    log.info(
        "health_check",
        overall=overall,
        postgres=postgres["status"],
        ollama=ollama["status"],
    )

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.1.0",
        "services": {
            "postgres": postgres,
            "ollama": ollama,
        },
    }


@router.get("/admin/stats", summary="Ingestion metrics")
async def stats() -> dict:
    """Return document and chunk counts across all indices."""
    import asyncio
    import sqlite3

    from src.common.db import FTS_DB_PATH, MANIFEST_DB_PATH, get_postgres_conn

    def _manifest_stats() -> dict:
        conn = sqlite3.connect(str(MANIFEST_DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                """SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN extraction_status IN ('extracted','needs_ocr') THEN 1 ELSE 0 END) AS indexed,
                    SUM(CASE WHEN extraction_status = 'pending' THEN 1 ELSE 0 END) AS pending,
                    SUM(CASE WHEN extraction_status = 'failed' THEN 1 ELSE 0 END) AS failed,
                    SUM(chunk_count) AS total_chunks
                FROM documents"""
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def _fts_count() -> int:
        try:
            conn = sqlite3.connect(str(FTS_DB_PATH))
            n = conn.execute("SELECT COUNT(*) FROM chunks_kw").fetchone()[0]
            conn.close()
            return n
        except Exception:
            return 0

    m, fts_n = await asyncio.gather(
        asyncio.to_thread(_manifest_stats),
        asyncio.to_thread(_fts_count),
    )

    vector_n = 0
    try:
        async with get_postgres_conn() as conn:
            vector_n = await conn.fetchval("SELECT COUNT(*) FROM chunks") or 0
    except Exception:
        pass

    return {
        "documents": {
            "total": m["total"] or 0,
            "indexed": m["indexed"] or 0,
            "pending": m["pending"] or 0,
            "failed": m["failed"] or 0,
        },
        "chunks": {"total": m["total_chunks"] or 0},
        "indices": {
            "vector": f"{vector_n} rows (pgvector)",
            "keyword": f"{fts_n} rows (FTS5)",
        },
    }


@router.post("/admin/reindex", summary="Trigger re-indexing")
async def reindex() -> dict:
    """Kick off a full re-index of all documents.

    Phase 1: wires to the ingest pipeline CLI.
    """
    # TODO Phase 1: invoke pipeline.run_full() as a background task
    return {"status": "not_implemented", "phase": "Phase 1"}
