"""Upsert chunk vectors into pgvector (Postgres).

Schema (created on first run if absent):

    CREATE TABLE chunks (
        chunk_id        TEXT PRIMARY KEY,
        doc_id          TEXT NOT NULL,
        embedding       vector(384),
        text            TEXT NOT NULL,
        metadata        JSONB NOT NULL DEFAULT '{}',
        page_start      INT  NOT NULL,
        page_end        INT  NOT NULL,
        section_heading TEXT
    );

    -- HNSW index built once after all data is loaded
    CREATE INDEX chunks_embedding_hnsw_idx
        ON chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);

Flow per doc:
  1. Load Chunk objects from data/chunks/<doc_id>.jsonl
  2. Call embed_chunks() → (chunk_id, vector) pairs
  3. Batch-upsert to Postgres using psycopg2 execute_values
"""

from __future__ import annotations

import json

import psycopg2
import psycopg2.extras

from src.common.config import settings
from src.common.db import DATA_DIR, MANIFEST_DB_PATH, get_sqlite_conn
from src.common.logging import get_logger
from src.common.schemas import Chunk
from src.ingest.embed import embed_chunks

log = get_logger(__name__)

CHUNKS_DIR = DATA_DIR / "chunks"

_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id        TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL,
    embedding       vector(384),
    text            TEXT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    page_start      INT  NOT NULL,
    page_end        INT  NOT NULL,
    section_heading TEXT
);

CREATE INDEX IF NOT EXISTS chunks_doc_id_idx ON chunks (doc_id);
"""

_HNSW_DDL = """
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx
    ON chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
"""

_UPSERT_SQL = """
INSERT INTO chunks
    (chunk_id, doc_id, embedding, text, metadata, page_start, page_end, section_heading)
VALUES %s
ON CONFLICT (chunk_id) DO UPDATE SET
    embedding       = EXCLUDED.embedding,
    text            = EXCLUDED.text,
    metadata        = EXCLUDED.metadata,
    page_start      = EXCLUDED.page_start,
    page_end        = EXCLUDED.page_end,
    section_heading = EXCLUDED.section_heading;
"""

_UPSERT_TEMPLATE = "(%s, %s, %s::vector, %s, %s::jsonb, %s, %s, %s)"


# ── Connection ────────────────────────────────────────────────────────────────


def _pg_connect() -> psycopg2.extensions.connection:
    """Return a sync psycopg2 connection to Postgres."""
    return psycopg2.connect(settings.db_dsn)


# ── Schema management ─────────────────────────────────────────────────────────


def ensure_schema() -> None:
    """Create the chunks table and doc_id index if they don't exist."""
    conn = _pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_TABLE_DDL)
        conn.commit()
    finally:
        conn.close()


def build_hnsw_index() -> None:
    """Build the HNSW cosine index (idempotent — uses CREATE INDEX IF NOT EXISTS)."""
    log.info("building_hnsw_index")
    conn = _pg_connect()
    try:
        with conn.cursor() as cur:
            cur.execute(_HNSW_DDL)
        conn.commit()
        log.info("hnsw_index_ready")
    finally:
        conn.close()


# ── Per-doc upsert ────────────────────────────────────────────────────────────


def _load_chunks(doc_id: str) -> list[Chunk]:
    jsonl_path = CHUNKS_DIR / f"{doc_id}.jsonl"
    if not jsonl_path.exists():
        return []
    chunks: list[Chunk] = []
    for line in jsonl_path.open(encoding="utf-8").readlines():
        line = line.rstrip("\n")
        if line.strip():
            chunks.append(Chunk.model_validate_json(line))
    return chunks


def upsert_doc(doc_id: str, conn: psycopg2.extensions.connection) -> int:
    """Embed and upsert all chunks for one doc. Returns number of rows upserted."""
    chunks = _load_chunks(doc_id)
    if not chunks:
        return 0

    pairs = embed_chunks(chunks)  # [(chunk_id, vector), ...]
    vec_map = {cid: vec for cid, vec in pairs}

    rows = []
    for chunk in chunks:
        vec = vec_map[chunk.chunk_id]
        # pgvector expects string format "[x,x,x,...]" with ::vector cast
        vec_str = "[" + ",".join(f"{v:.8f}" for v in vec) + "]"
        rows.append((
            chunk.chunk_id,
            chunk.doc_id,
            vec_str,
            chunk.text,
            json.dumps(chunk.metadata.model_dump()),
            chunk.page_start,
            chunk.page_end,
            chunk.section_heading,
        ))

    with conn.cursor() as cur:
        psycopg2.extras.execute_values(
            cur,
            _UPSERT_SQL,
            rows,
            template=_UPSERT_TEMPLATE,
        )
    conn.commit()
    return len(rows)


# ── Public API ────────────────────────────────────────────────────────────────


def run(force: bool = False) -> dict[str, int]:
    """Embed and index all chunked documents into pgvector.

    Processes docs with chunk_count > 0.
    With force=True, re-indexes docs already present in Postgres.

    Returns:
        {'indexed': N, 'skipped': N, 'failed': N}
    """
    ensure_schema()

    with get_sqlite_conn(MANIFEST_DB_PATH) as sqlite_conn:
        docs = sqlite_conn.execute(
            "SELECT doc_id, file_name, chunk_count FROM documents "
            "WHERE chunk_count > 0 ORDER BY file_name"
        ).fetchall()

    counts = {"indexed": 0, "skipped": 0, "failed": 0}

    # Determine which docs are already indexed (skip if not forcing)
    already_indexed: set[str] = set()
    if not force:
        pg = _pg_connect()
        try:
            with pg.cursor() as cur:
                cur.execute("SELECT DISTINCT doc_id FROM chunks")
                already_indexed = {row[0] for row in cur.fetchall()}
        finally:
            pg.close()

    pg = _pg_connect()
    try:
        for doc in docs:
            doc_id: str = doc["doc_id"]

            if not force and doc_id in already_indexed:
                counts["skipped"] += 1
                continue

            try:
                n = upsert_doc(doc_id, pg)
                counts["indexed"] += 1
                log.info("vector_indexed", doc_id=doc_id, file=doc["file_name"], chunks=n)
            except Exception as exc:
                counts["failed"] += 1
                pg.rollback()
                log.error(
                    "vector_index_failed",
                    doc_id=doc_id,
                    file=doc["file_name"],
                    error=str(exc),
                )
    finally:
        pg.close()

    # Build HNSW index after all vectors are loaded
    build_hnsw_index()

    log.info("index_vector_complete", **counts)
    return counts
