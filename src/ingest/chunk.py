"""Split cleaned page text into token-sized chunks.

Phase 1 implementation.

Strategy: sliding window — CHUNK_SIZE_TOKENS tokens, CHUNK_OVERLAP_TOKENS overlap.
Token counting via tiktoken (cl100k_base encoding).

Input:  data/extracted/<doc_id>.jsonl
Output: data/chunks/<doc_id>.jsonl  (one Chunk per line)
"""

from __future__ import annotations

# TODO Phase 1: load extracted JSONL, split with tiktoken, write chunks JSONL
