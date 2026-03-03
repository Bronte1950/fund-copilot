"""Combine vector and keyword results into a single ranked list.

Algorithm:
  1. Normalise each score list to [0, 1] independently (min-max).
  2. Apply configured weights:
       hybrid = vector_weight * v_score + keyword_weight * k_score
  3. Deduplicate by chunk_id — keep the highest combined score;
     merge fund_name from whichever source has it.
  4. Sort descending, return top_k results with search_type='hybrid'.
"""

from __future__ import annotations

from src.common.config import settings
from src.common.schemas import RetrievalResult


def _normalise(results: list[RetrievalResult]) -> list[tuple[RetrievalResult, float]]:
    """Return (result, normalised_score) pairs, scaled to [0, 1]."""
    if not results:
        return []
    scores = [r.score for r in results]
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [(r, 1.0) for r in results]
    return [(r, (r.score - lo) / (hi - lo)) for r in results]


def hybrid_combine(
    vector_results: list[RetrievalResult],
    keyword_results: list[RetrievalResult],
    top_k: int,
) -> list[RetrievalResult]:
    """Fuse two ranked lists with weighted normalised scores."""
    combined: dict[str, float] = {}
    best: dict[str, RetrievalResult] = {}

    for result, norm in _normalise(vector_results):
        combined[result.chunk_id] = combined.get(result.chunk_id, 0.0) + (
            settings.hybrid_vector_weight * norm
        )
        best[result.chunk_id] = result

    for result, norm in _normalise(keyword_results):
        combined[result.chunk_id] = combined.get(result.chunk_id, 0.0) + (
            settings.hybrid_keyword_weight * norm
        )
        if result.chunk_id not in best:
            best[result.chunk_id] = result
        elif best[result.chunk_id].fund_name is None and result.fund_name is not None:
            # Prefer fund_name from whichever source has it
            best[result.chunk_id] = best[result.chunk_id].model_copy(
                update={"fund_name": result.fund_name}
            )

    top_ids = sorted(combined, key=lambda cid: combined[cid], reverse=True)[:top_k]
    return [
        best[cid].model_copy(
            update={"score": round(combined[cid], 4), "search_type": "hybrid"}
        )
        for cid in top_ids
    ]
