"""High-level retrieval interface used by the API.

Phase 2 implementation.

Single entry point:
    results = await retrieve(request: RetrievalRequest) -> list[RetrievalResult]

Orchestrates: filters → vector_search + keyword_search (parallel) → hybrid combine.
"""

from __future__ import annotations

# TODO Phase 2: orchestrate parallel vector + keyword search, apply hybrid, return results
