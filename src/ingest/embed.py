"""Embed chunks using sentence-transformers (CPU).

Model:  all-MiniLM-L6-v2  (384 dims, ~80 MB, MIT licence)
Input:  list[Chunk] (in-memory, from chunk.py)
Output: list of (chunk_id, vector[384 floats])

The model is loaded once per process (module-level singleton) so repeated
calls within the same run() don't reload weights.

Embeddings are L2-normalised by the model so cosine similarity reduces to
a dot product — compatible with pgvector's vector_cosine_ops index.
"""

from __future__ import annotations

from src.common.config import settings
from src.common.logging import get_logger
from src.common.schemas import Chunk

log = get_logger(__name__)

# Lazy singleton — avoids 1-2 s model load on every import
_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        log.info("loading_embedding_model", model=settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        log.info("embedding_model_loaded", model=settings.embedding_model)
    return _model


def embed_chunks(
    chunks: list[Chunk],
    batch_size: int | None = None,
) -> list[tuple[str, list[float]]]:
    """Encode a list of Chunk objects and return (chunk_id, vector) pairs.

    Vectors are L2-normalised (unit length), ready for cosine similarity.
    """
    if not chunks:
        return []

    if batch_size is None:
        batch_size = settings.embedding_batch_size

    model = _get_model()
    texts = [c.text for c in chunks]

    # encode() returns numpy ndarray shape (n, 384), dtype float32
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    return [(chunk.chunk_id, vec.tolist()) for chunk, vec in zip(chunks, vectors)]
