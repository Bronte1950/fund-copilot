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
    """Return document and chunk counts across all indices.

    Phase 1: populated once the ingest pipeline runs.
    """
    # TODO Phase 1: query manifest.sqlite for real counts
    return {
        "documents": {"total": 0, "indexed": 0, "pending": 0, "failed": 0},
        "chunks": {"total": 0},
        "indices": {
            "vector": "not initialised",
            "keyword": "not initialised",
        },
    }


@router.post("/admin/reindex", summary="Trigger re-indexing")
async def reindex() -> dict:
    """Kick off a full re-index of all documents.

    Phase 1: wires to the ingest pipeline CLI.
    """
    # TODO Phase 1: invoke pipeline.run_full() as a background task
    return {"status": "not_implemented", "phase": "Phase 1"}
