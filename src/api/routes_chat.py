"""Chat routes — POST /chat and POST /chat/stream endpoints.

Flow (both endpoints):
    1. Validate query (length + basic prompt-injection check).
    2. Retrieve context chunks via hybrid search.
    3. Assemble prompt with token budgeting.
    4. Call Ollama (blocking for /chat, streaming for /chat/stream).
    5. Validate citations + grounding.
    6. Return ChatResponse or SSE stream.
"""

from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.common.config import settings
from src.common.logging import get_logger
from src.common.schemas import ChatRequest, ChatResponse, RetrievalRequest
from src.llm.client import generate, stream_generate
from src.llm.grounding import ground_response
from src.llm.prompts import assemble_prompt
from src.retrieval.service import retrieve

log = get_logger(__name__)
router = APIRouter(tags=["chat"])

# ── Prompt-injection defence ──────────────────────────────────────────────────

_MAX_QUERY_LEN = 2_000

_INJECTION_RE = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions"
    r"|override\s+your\s+(rules|instructions)"
    r"|forget\s+your\s+(rules|instructions)"
    r"|new\s+system\s+prompt"
    r"|you\s+are\s+now\s+a\s+different)",
    re.IGNORECASE,
)


def _validate_query(query: str) -> None:
    """Raise HTTP 400 for obviously malicious or oversized queries."""
    if len(query) > _MAX_QUERY_LEN:
        raise HTTPException(
            status_code=400,
            detail=f"Query too long (max {_MAX_QUERY_LEN} characters).",
        )
    if _INJECTION_RE.search(query):
        raise HTTPException(
            status_code=400,
            detail="Query contains disallowed patterns.",
        )


# ── Shared pipeline helper ────────────────────────────────────────────────────


async def _run_retrieval(request: ChatRequest) -> tuple[list, float]:
    """Retrieve chunks and return (results, retrieval_ms)."""
    t0 = time.perf_counter()
    retrieval_req = RetrievalRequest(
        query=request.query,
        top_k=min(request.top_k, settings.max_context_chunks),
        provider=request.provider,
        doc_type=request.doc_type,
        isin=request.isin,
    )
    results = await retrieve(retrieval_req)
    retrieval_ms = (time.perf_counter() - t0) * 1000
    log.info(
        "chat_retrieval_done",
        n_results=len(results),
        retrieval_ms=round(retrieval_ms, 1),
    )
    return results, retrieval_ms


# ── POST /chat ────────────────────────────────────────────────────────────────


@router.post("/chat", summary="RAG chat with mandatory citations")
async def chat(request: ChatRequest) -> ChatResponse:
    """Retrieve context, generate a grounded answer, and return citations.

    - **query**: natural-language question about a UCITS fund document.
    - **provider** / **doc_type** / **isin**: optional pre-filters for retrieval.
    - **top_k**: chunks to retrieve (default 10; capped at max_context_chunks).

    Returns a `ChatResponse`.  When the LLM cannot find sufficient evidence it
    sets `confidence: "refused"` and explains why in `refusal_reason`.
    """
    query = request.query.strip()
    _validate_query(query)

    results, retrieval_ms = await _run_retrieval(request)
    messages, chunks_used = assemble_prompt(query, results)

    t0 = time.perf_counter()
    answer_text = await generate(messages)
    generation_ms = (time.perf_counter() - t0) * 1000

    log.info(
        "chat_generation_done",
        answer_len=len(answer_text),
        generation_ms=round(generation_ms, 1),
        model=settings.ollama_model,
    )

    response = ground_response(
        answer_text=answer_text,
        chunks_used=chunks_used,
        results=results,
        retrieval_time_ms=retrieval_ms,
        generation_time_ms=generation_ms,
        model=settings.ollama_model,
    )

    log.info(
        "chat_complete",
        confidence=response.confidence,
        n_citations=len(response.citations),
    )
    return response


# ── POST /chat/stream ─────────────────────────────────────────────────────────


@router.post("/chat/stream", summary="Streaming RAG chat (SSE)")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Same as POST /chat but streams the answer as Server-Sent Events.

    SSE event types:
    - **token** — incremental answer text: `{"text": "..."}`
    - **done**  — full `ChatResponse` JSON payload once generation is complete.
    - **error** — error message: `{"error": "..."}`

    The client should accumulate `token` events to display the streaming answer,
    then use the `done` payload for citations and metadata.
    """
    query = request.query.strip()
    _validate_query(query)

    async def _generate():
        try:
            results, retrieval_ms = await _run_retrieval(request)
            messages, chunks_used = assemble_prompt(query, results)

            t0 = time.perf_counter()
            full_answer: list[str] = []

            async for token in stream_generate(messages):
                full_answer.append(token)
                yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"

            generation_ms = (time.perf_counter() - t0) * 1000
            answer_text = "".join(full_answer)

            response = ground_response(
                answer_text=answer_text,
                chunks_used=chunks_used,
                results=results,
                retrieval_time_ms=retrieval_ms,
                generation_time_ms=generation_ms,
                model=settings.ollama_model,
            )

            log.info(
                "chat_stream_complete",
                confidence=response.confidence,
                n_citations=len(response.citations),
                generation_ms=round(generation_ms, 1),
            )

            yield f"event: done\ndata: {json.dumps(response.model_dump())}\n\n"

        except Exception as exc:
            log.error("chat_stream_error", error=str(exc))
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
