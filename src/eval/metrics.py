"""Evaluation metrics — Hit@k, grounding accuracy, refusal accuracy.

Definitions:
    Hit@k         — 1.0 if the expected document appears in the top-k retrieved
                    chunks, else 0.0.  (Recall@k for single-relevant-doc queries.)
    Grounding     — answer contains at least one verified [SOURCE: chunk_id] citation.
    Refusal correct — should_refuse=True → confidence=="refused";
                      should_refuse=False → confidence!="refused".
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvalResult:
    question_id: str
    query: str
    category: str
    should_refuse: bool
    expected_answer: str | None
    expected_isin: str | None
    # Retrieval
    retrieved_doc_ids: list[str] = field(default_factory=list)
    retrieved_chunk_ids: list[str] = field(default_factory=list)
    hit_at_k: float | None = None       # None when expected_isin not in manifest
    # Generation
    answer: str = ""
    confidence: str = "refused"
    chunks_cited: list[str] = field(default_factory=list)
    chunks_used: list[str] = field(default_factory=list)
    grounding_ok: bool = False          # ≥1 valid citation
    refusal_correct: bool = False       # refusal matches should_refuse
    # Timing
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    error: str | None = None


def compute_hit_at_k(retrieved_doc_ids: list[str], expected_doc_id: str | None) -> float | None:
    """1.0 if expected_doc_id in retrieved_doc_ids, else 0.0. None if unknown."""
    if expected_doc_id is None:
        return None
    return 1.0 if expected_doc_id in retrieved_doc_ids else 0.0


def compute_grounding_ok(chunks_cited: list[str], chunks_used: list[str]) -> bool:
    """True if ≥1 cited chunk_id was actually in the context sent to the LLM."""
    valid = set(chunks_used)
    return any(c in valid for c in chunks_cited)


def compute_refusal_correct(confidence: str, should_refuse: bool) -> bool:
    return (confidence == "refused") == should_refuse


def summarise(results: list[EvalResult]) -> dict:
    """Aggregate metrics across all eval results."""
    n = len(results)
    if n == 0:
        return {"n_questions": 0}

    hit_scores = [r.hit_at_k for r in results if r.hit_at_k is not None]
    errors = [r for r in results if r.error]
    answerable = [r for r in results if not r.should_refuse]
    refusable  = [r for r in results if r.should_refuse]

    return {
        "n_questions": n,
        "n_errors": len(errors),
        "hit_at_k": round(sum(hit_scores) / len(hit_scores), 3) if hit_scores else None,
        "grounding_rate": round(sum(r.grounding_ok for r in results) / n, 3),
        "refusal_accuracy": round(sum(r.refusal_correct for r in results) / n, 3),
        "answerable_grounding": round(
            sum(r.grounding_ok for r in answerable) / len(answerable), 3
        ) if answerable else None,
        "correct_refusals": round(
            sum(r.refusal_correct for r in refusable) / len(refusable), 3
        ) if refusable else None,
        "avg_retrieval_ms": round(sum(r.retrieval_ms for r in results) / n, 1),
        "avg_generation_ms": round(sum(r.generation_ms for r in results) / n, 1),
        "by_category": _by_category(results),
    }


def _by_category(results: list[EvalResult]) -> dict:
    cats: dict[str, list[EvalResult]] = {}
    for r in results:
        cats.setdefault(r.category, []).append(r)
    out = {}
    for cat, rs in sorted(cats.items()):
        hits = [r.hit_at_k for r in rs if r.hit_at_k is not None]
        out[cat] = {
            "n": len(rs),
            "hit_at_k": round(sum(hits) / len(hits), 3) if hits else None,
            "grounding_rate": round(sum(r.grounding_ok for r in rs) / len(rs), 3),
            "refusal_accuracy": round(sum(r.refusal_correct for r in rs) / len(rs), 3),
        }
    return out
