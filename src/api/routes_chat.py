"""Chat routes — POST /chat with SSE streaming.

Phase 3 implementation.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["chat"])


@router.post("/chat", summary="RAG chat with mandatory citations")
async def chat() -> dict:
    """Accept a query, retrieve context, generate a grounded answer via Ollama.

    Phase 3: implement retrieval → context assembly → LLM → grounding → SSE.
    """
    # TODO Phase 3: accept ChatRequest, run full pipeline, stream response
    return {"error": "not_implemented", "phase": "Phase 3"}
