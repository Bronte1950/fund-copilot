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

import asyncio
import json
import re
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.common.config import settings
from src.common.logging import get_logger
from src.common.schemas import ChatRequest, ChatResponse, Citation, FundLiveData, RetrievalRequest
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


def _build_live_context_block(live_rows: list[FundLiveData]) -> str:
    """Format live Yahoo Finance data as a plain-text context block for the LLM.

    Uses [LIVE] tag (not a [N] number) so the grounding validator ignores it.
    The LLM uses this data to reason; live citations are appended programmatically.
    """
    if not live_rows:
        return ""

    age_h = settings.yahoo_cache_max_age_hours
    lines = [f"[LIVE] Yahoo Finance market data (cached, updated within {age_h:.0f} hours):"]
    for row in live_rows:
        parts = [f"ISIN: {row.isin}"]
        if row.fund_name:
            parts.append(f"Name: {row.fund_name}")
        if row.resolved_ticker:
            parts.append(f"Ticker: {row.resolved_ticker}")
        if row.price is not None:
            currency = row.currency or ""
            parts.append(f"Price: {row.price} {currency}".strip())
        if row.price_change_pct is not None:
            parts.append(f"24h: {row.price_change_pct:+.2f}%")
        if row.ytd_return_pct is not None:
            parts.append(f"YTD: {row.ytd_return_pct:.2f}%")
        if row.one_year_return_pct is not None:
            parts.append(f"1yr: {row.one_year_return_pct:.2f}%")
        if row.expense_ratio_pct is not None:
            parts.append(f"OCF: {row.expense_ratio_pct:.4f}%")
        if row.aum_millions is not None:
            parts.append(f"AUM: {row.aum_millions:.0f}M")
        if row.dividend_yield_pct is not None:
            parts.append(f"Yield: {row.dividend_yield_pct:.2f}%")
        if row.yahoo_url:
            parts.append(f"Source: {row.yahoo_url}")
        lines.append("  " + " | ".join(parts))

    return "\n".join(lines)


def _build_live_citations(live_rows: list[FundLiveData]) -> list[Citation]:
    """Build Citation objects for live data rows. Appended after ground_response()."""
    citations: list[Citation] = []
    for row in live_rows:
        if row.fetch_status != "ok":
            continue
        price_str = f"{row.price} {row.currency or ''}".strip() if row.price is not None else "N/A"
        yield_str = f"{row.dividend_yield_pct:.2f}%" if row.dividend_yield_pct is not None else "N/A"
        citations.append(
            Citation(
                doc_id=f"yahoo:{row.isin}",
                file_name=f"Yahoo Finance — {row.resolved_ticker or row.isin}",
                provider="Yahoo Finance",
                fund_name=row.fund_name,
                page_start=0,
                page_end=0,
                section="Live Market Data",
                snippet=f"Price: {price_str} | Yield: {yield_str}",
                url=row.yahoo_url,
                citation_type="live_data",
            )
        )
    return citations


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

    # Cap to token-budget limit (largest funds by AUM are preferred but we don't sort here —
    # the list from manifest is small enough; refresh_all caps internally)
    isins = isins[: settings.yahoo_max_live_funds]

    try:
        return await get_live_data(isins)
    except Exception as exc:
        log.warning("live_data_fetch_failed", error=str(exc))
        return []


# ── Shared pipeline helper ─────────────────────────────────────────────────────


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

    messages, chunks_used = assemble_prompt(query, results)

    # Prepend live data block to system message if this is a market-data query
    if live_rows:
        live_block = _build_live_context_block(live_rows)
        messages[0]["content"] = live_block + "\n\n---\n\n" + messages[0]["content"]
        log.info("live_data_injected", n_funds=len(live_rows))

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

    # Append live data citations (bypass grounding validator — intentional)
    if live_rows:
        response.citations.extend(_build_live_citations(live_rows))

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
            messages, chunks_used = assemble_prompt(query, results)

            if live_rows:
                live_block = _build_live_context_block(live_rows)
                messages[0]["content"] = live_block + "\n\n---\n\n" + messages[0]["content"]

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
                response.citations.extend(_build_live_citations(live_rows))

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
