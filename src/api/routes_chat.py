"""Chat routes — POST /chat and POST /chat/stream endpoints.

Flow (both endpoints):
    1. Validate query (length + basic prompt-injection check).
    2. Retrieve context chunks via hybrid search.
       If query is a market-data/comparison query, also fetch Yahoo Finance live data.
    3. Prepend live data as numbered context passages alongside PDF chunks.
    4. Assemble prompt with token budgeting.
    5. Call Ollama (blocking for /chat, streaming for /chat/stream).
    6. Validate citations + grounding.
    7. Enrich any Yahoo Finance citations with url/citation_type for the frontend.
    8. Return ChatResponse or SSE stream.
"""

from __future__ import annotations

import asyncio
import json
import re
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.common.config import settings
from src.common.logging import get_logger
from src.common.schemas import (
    ChatRequest,
    ChatResponse,
    Citation,
    FundLiveData,
    RetrievalRequest,
    RetrievalResult,
)
from src.data_sources.yahoo_finance import get_all_manifest_isins, get_live_data
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


# ── Live data query detection ─────────────────────────────────────────────────
# Both a market-data signal AND a fund-context signal must match.
# Conservative: false negatives (missed comparisons) are OK — user still gets PDF answer.
# False positives (injecting irrelevant live data) would add noise.

_MARKET_DATA_RE = re.compile(
    r"\b("
    r"compar[ei(ing)(ison)]"
    r"|versus|vs\.?"
    r"|which\s+fund"
    r"|highest|lowest|cheapest|most\s+expensive"
    r"|price|nav|net\s+asset"
    r"|yield|dividend"
    r"|return|performance|ytd|year.to.date"
    r"|1.year|3.year|5.year"
    r"|ongoing\s+charge|ocf|ter|expense\s+ratio"
    r"|aum|assets\s+under\s+management"
    r")\b",
    re.IGNORECASE,
)

_FUND_CONTEXT_RE = re.compile(
    r"\b(fund|etf|ucits|isin|portfolio|index|trust|tracker)\b",
    re.IGNORECASE,
)


def _is_live_data_query(query: str) -> bool:
    """Return True if the query likely wants live market data (price, yield, comparison)."""
    return bool(_MARKET_DATA_RE.search(query) and _FUND_CONTEXT_RE.search(query))


def _live_data_to_results(live_rows: list[FundLiveData]) -> list[RetrievalResult]:
    """Convert FundLiveData rows to synthetic RetrievalResult objects.

    These are prepended to the retrieval results list so they appear as numbered
    passages [1], [2], ... inside the CONTEXT section of the system prompt — the
    same section the model is instructed to cite from.  The model can then cite
    live data naturally with [1] just like a PDF chunk, and the grounding
    validator validates those citations through the normal pipeline.

    source_file is set to "Yahoo Finance — {ticker}" so _build_citations() in
    grounding.py produces a Citation with that as file_name.  _enrich_live_citations()
    then adds url and citation_type="live_data" so the frontend renders the
    clickable Yahoo Finance link.
    """
    results: list[RetrievalResult] = []
    for row in live_rows:
        parts: list[str] = []
        if row.price is not None:
            currency = row.currency or ""
            parts.append(f"Price: {row.price} {currency}".strip())
        if row.price_change_pct is not None:
            parts.append(f"24h change: {row.price_change_pct:+.2f}%")
        if row.ytd_return_pct is not None:
            parts.append(f"YTD return: {row.ytd_return_pct:.2f}%")
        if row.one_year_return_pct is not None:
            parts.append(f"1-year return: {row.one_year_return_pct:.2f}%")
        if row.expense_ratio_pct is not None:
            parts.append(f"Ongoing charge (OCF): {row.expense_ratio_pct:.4f}%")
        if row.aum_millions is not None:
            parts.append(f"AUM: {row.aum_millions:.0f}M")
        if row.dividend_yield_pct is not None:
            parts.append(f"Dividend yield: {row.dividend_yield_pct:.2f}%")
        if row.yahoo_url:
            parts.append(f"Source: {row.yahoo_url}")

        text = " | ".join(parts) if parts else "No market data available."

        results.append(
            RetrievalResult(
                chunk_id=f"yahoo:{row.isin}",
                doc_id=f"yahoo:{row.isin}",
                score=1.0,
                text=text,
                page_start=0,
                page_end=0,
                section_heading="Live Market Data",
                source_file=f"Yahoo Finance — {row.resolved_ticker or row.isin}",
                provider="Yahoo Finance",
                fund_name=row.fund_name,
                search_type="hybrid",
            )
        )
    return results


def _enrich_live_citations(citations: list[Citation], live_rows: list[FundLiveData]) -> None:
    """Post-process grounded citations: add url and citation_type for Yahoo Finance entries.

    ground_response() builds Citation objects from RetrievalResult fields but does not
    know about url or citation_type.  This function patches those fields in-place so the
    frontend SourceCard can render the clickable Yahoo Finance link with the live badge.
    """
    live_by_isin = {row.isin: row for row in live_rows}
    for citation in citations:
        if not citation.doc_id.startswith("yahoo:"):
            continue
        isin = citation.doc_id[len("yahoo:"):]
        row = live_by_isin.get(isin)
        if row:
            citation.url = row.yahoo_url
            citation.citation_type = "live_data"


async def _run_live_data(request: ChatRequest, query: str) -> list[FundLiveData]:
    """Fetch live data if the query is a market-data query and feature is enabled."""
    if not settings.yahoo_live_data_enabled:
        return []
    if not _is_live_data_query(query):
        return []

    # Single ISIN filter → only that fund; otherwise all ISINs from manifest
    if request.isin:
        isins = [request.isin]
    else:
        isins = await asyncio.to_thread(get_all_manifest_isins)

    isins = isins[: settings.yahoo_max_live_funds]

    try:
        return await get_live_data(isins)
    except Exception as exc:
        log.warning("live_data_fetch_failed", error=str(exc))
        return []


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

    # Run retrieval and live data fetch concurrently
    (results, retrieval_ms), live_rows = await asyncio.gather(
        _run_retrieval(request),
        _run_live_data(request, query),
    )

    # Prepend live data as numbered context passages — they flow through the
    # normal assemble_prompt / ground_response pipeline alongside PDF chunks.
    if live_rows:
        results = _live_data_to_results(live_rows) + results
        log.info("live_data_injected", n_funds=len(live_rows))

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

    # Patch url + citation_type on any Yahoo Finance citations grounding produced
    if live_rows:
        _enrich_live_citations(response.citations, live_rows)

    log.info(
        "chat_complete",
        confidence=response.confidence,
        n_citations=len(response.citations),
        live_data=len(live_rows) > 0,
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
            (results, retrieval_ms), live_rows = await asyncio.gather(
                _run_retrieval(request),
                _run_live_data(request, query),
            )

            if live_rows:
                results = _live_data_to_results(live_rows) + results

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

            if live_rows:
                _enrich_live_citations(response.citations, live_rows)

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
