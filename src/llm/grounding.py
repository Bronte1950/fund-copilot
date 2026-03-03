"""Citation validation and refusal detection.

After the LLM generates a response:
    1. Parse [SOURCE: chunk_id] citations from the answer text.
    2. Verify each cited chunk_id was actually in the context (chunks_used).
    3. Detect REFUSED: prefix → set confidence = "refused".
    4. Assign confidence level based on citation count and chunk retrieval scores.
"""

from __future__ import annotations

import re

from src.common.schemas import ChatResponse, Citation, RetrievalResult

# ── Regex patterns ────────────────────────────────────────────────────────────

# Match numbered citations [1], [2], [12], etc.
# The model is now instructed to cite using sequential passage numbers, not
# opaque hex chunk IDs.  Numbers only (no letters) avoids matching other
# bracket patterns in financial text like [USD] or [UCITS].
_SOURCE_RE = re.compile(r"\[(\d+)\]")
_REFUSED_RE = re.compile(r"^\s*REFUSED\s*:\s*(.+)", re.DOTALL | re.IGNORECASE)


# ── Parsing ───────────────────────────────────────────────────────────────────


def parse_citations(answer_text: str) -> list[str]:
    """Extract citation numbers from [1], [2], ... markers in the answer.

    Returns a list of number strings in order of first appearance (may contain
    duplicates).  Callers resolve numbers to chunk_ids using chunks_used.
    """
    return [m.group(1) for m in _SOURCE_RE.finditer(answer_text)]


def detect_refusal(answer_text: str) -> tuple[bool, str | None]:
    """Check if the LLM's answer is a refusal.

    Returns:
        (is_refused, reason_text)
        reason_text is the text after "REFUSED:" when is_refused is True.
    """
    m = _REFUSED_RE.match(answer_text)
    if m:
        return True, m.group(1).strip()
    return False, None


# ── Confidence ────────────────────────────────────────────────────────────────


def _assign_confidence(
    valid_cited: list[str],
    results_by_id: dict[str, RetrievalResult],
) -> str:
    """Assign confidence based on citation count and average retrieval score.

    Rules:
        high   — ≥2 valid citations with average retrieval score ≥ 0.65
        medium — ≥1 valid citation with average retrieval score ≥ 0.45
        low    — ≥1 valid citation but low scores, or only 1 citation
    """
    if not valid_cited:
        return "low"

    scores = [results_by_id[c].score for c in valid_cited if c in results_by_id]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    if len(valid_cited) >= 2 and avg_score >= 0.65:
        return "high"
    if avg_score >= 0.45:
        return "medium"
    return "low"


# ── Citation objects ──────────────────────────────────────────────────────────


def _build_citations(
    valid_cited: list[str],
    results_by_id: dict[str, RetrievalResult],
) -> list[Citation]:
    """Convert a list of validated chunk_ids to Citation objects.

    Deduplicates by chunk_id; preserves first-appearance order.
    """
    seen: set[str] = set()
    citations: list[Citation] = []
    for chunk_id in valid_cited:
        if chunk_id in seen or chunk_id not in results_by_id:
            continue
        seen.add(chunk_id)
        r = results_by_id[chunk_id]
        citations.append(
            Citation(
                doc_id=r.doc_id,
                file_name=r.source_file or r.doc_id,
                provider=r.provider,
                fund_name=r.fund_name,
                page_start=r.page_start,
                page_end=r.page_end,
                section=r.section_heading,
                snippet=r.text[:300],
            )
        )
    return citations


# ── Main entry point ──────────────────────────────────────────────────────────


def ground_response(
    answer_text: str,
    chunks_used: list[str],
    results: list[RetrievalResult],
    retrieval_time_ms: float,
    generation_time_ms: float,
    model: str,
) -> ChatResponse:
    """Validate citations and build the final ChatResponse.

    Steps:
        1. Detect refusal → return immediately with confidence="refused".
        2. Parse [SOURCE: chunk_id] from the answer.
        3. Drop citations to chunks that were not in chunks_used (hallucinated refs).
        4. Assign confidence from citation count + retrieval scores.
        5. Build Citation objects for the valid, deduplicated cited chunks.
    """
    results_by_id = {r.chunk_id: r for r in results}
    valid_ids = set(chunks_used)

    # ── Refusal ───────────────────────────────────────────────────────────────
    is_refused, refusal_reason = detect_refusal(answer_text)
    if is_refused:
        return ChatResponse(
            answer=answer_text,
            citations=[],
            confidence="refused",
            refusal_reason=refusal_reason,
            chunks_used=chunks_used,
            chunks_cited=[],
            model=model,
            retrieval_time_ms=retrieval_time_ms,
            generation_time_ms=generation_time_ms,
        )

    # ── Citation validation ───────────────────────────────────────────────────
    # parse_citations returns number strings ["1", "2", ...].
    # Resolve each to the chunk_id at that 1-based position in chunks_used.
    cited_numbers = parse_citations(answer_text)
    cited_ids = [
        chunks_used[int(n) - 1]
        for n in cited_numbers
        if n.isdigit() and 1 <= int(n) <= len(chunks_used)
    ]
    # Only keep citations that refer to chunks actually in the prompt context.
    valid_cited = [c for c in cited_ids if c in valid_ids]

    confidence = _assign_confidence(valid_cited, results_by_id)
    citations = _build_citations(valid_cited, results_by_id)

    return ChatResponse(
        answer=answer_text,
        citations=citations,
        confidence=confidence,
        refusal_reason=None,
        chunks_used=chunks_used,
        chunks_cited=list(dict.fromkeys(valid_cited)),  # deduplicated, ordered
        model=model,
        retrieval_time_ms=retrieval_time_ms,
        generation_time_ms=generation_time_ms,
    )
