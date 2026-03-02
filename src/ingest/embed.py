"""Embed chunks using sentence-transformers (CPU).

Phase 1 implementation.

Model:  all-MiniLM-L6-v2  (384 dims, ~80MB, MIT licence)
Input:  data/chunks/<doc_id>.jsonl
Output: list of (chunk_id, vector[384])  — passed directly to index_vector.py
"""

from __future__ import annotations

# TODO Phase 1: batch encode with SentenceTransformer, EMBEDDING_BATCH_SIZE at a time
