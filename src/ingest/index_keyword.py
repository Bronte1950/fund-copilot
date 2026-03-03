"""Populate SQLite FTS5 for BM25 keyword search.

Two tables in data/indices/fts.sqlite:

    chunks_kw   — metadata (no text, links by rowid to FTS)
    fts         — virtual FTS5 table (text, Porter-stemmed)

They share rowids: when a chunk is inserted, we write to chunks_kw first
(getting its auto rowid) then insert into fts with the same rowid.
This lets us join them for filtered searches and delete by doc_id cleanly.

Input:  data/chunks/<doc_id>.jsonl
Output: data/indices/fts.sqlite
"""

from __future__ import annotations

from src.common.db import DATA_DIR, FTS_DB_PATH, MANIFEST_DB_PATH, get_sqlite_conn
from src.common.logging import get_logger
from src.common.schemas import Chunk

log = get_logger(__name__)

CHUNKS_DIR = DATA_DIR / "chunks"

# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS chunks_kw (
    chunk_id        TEXT PRIMARY KEY,
    doc_id          TEXT NOT NULL,
    page_start      INT  NOT NULL,
    page_end        INT  NOT NULL,
    section_heading TEXT,
    provider        TEXT,
    doc_type        TEXT,
    isin            TEXT,
    token_count     INT  NOT NULL
);

CREATE INDEX IF NOT EXISTS chunks_kw_doc_id_idx ON chunks_kw(doc_id);

CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(
    text,
    tokenize = 'porter unicode61'
);
"""


# ── Helpers ───────────────────────────────────────────────────────────────────


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


def _delete_doc(doc_id: str, conn) -> None:
    """Remove all FTS + metadata rows for a doc (for re-indexing)."""
    cur = conn.cursor()
    cur.execute("SELECT rowid FROM chunks_kw WHERE doc_id = ?", (doc_id,))
    rowids = [r[0] for r in cur.fetchall()]
    for rowid in rowids:
        cur.execute("DELETE FROM fts WHERE rowid = ?", (rowid,))
    cur.execute("DELETE FROM chunks_kw WHERE doc_id = ?", (doc_id,))


def _insert_doc(doc_id: str, chunks: list[Chunk], conn) -> int:
    """Insert chunk metadata + FTS rows. Returns number of rows inserted."""
    cur = conn.cursor()
    for chunk in chunks:
        cur.execute(
            """
            INSERT INTO chunks_kw
                (chunk_id, doc_id, page_start, page_end, section_heading,
                 provider, doc_type, isin, token_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.chunk_id,
                chunk.doc_id,
                chunk.page_start,
                chunk.page_end,
                chunk.section_heading,
                chunk.metadata.provider,
                chunk.metadata.doc_type,
                chunk.metadata.isin,
                chunk.token_count,
            ),
        )
        kw_rowid = cur.lastrowid
        cur.execute(
            "INSERT INTO fts(rowid, text) VALUES (?, ?)",
            (kw_rowid, chunk.text),
        )
    return len(chunks)


# ── Public API ────────────────────────────────────────────────────────────────


def ensure_schema() -> None:
    with get_sqlite_conn(FTS_DB_PATH) as conn:
        conn.executescript(_DDL)


def run(force: bool = False) -> dict[str, int]:
    """Index all chunked documents into SQLite FTS5.

    Processes docs with chunk_count > 0.
    With force=True, re-indexes docs already present in fts.sqlite.

    Returns:
        {'indexed': N, 'skipped': N, 'failed': N}
    """
    ensure_schema()

    with get_sqlite_conn(MANIFEST_DB_PATH) as mconn:
        docs = mconn.execute(
            "SELECT doc_id, file_name, chunk_count FROM documents "
            "WHERE chunk_count > 0 ORDER BY file_name"
        ).fetchall()

    counts = {"indexed": 0, "skipped": 0, "failed": 0}

    with get_sqlite_conn(FTS_DB_PATH) as fconn:
        # Determine which docs are already indexed
        already_indexed: set[str] = set()
        if not force:
            rows = fconn.execute(
                "SELECT DISTINCT doc_id FROM chunks_kw"
            ).fetchall()
            already_indexed = {r[0] for r in rows}

        for doc in docs:
            doc_id: str = doc["doc_id"]

            if not force and doc_id in already_indexed:
                counts["skipped"] += 1
                continue

            try:
                chunks = _load_chunks(doc_id)
                if not chunks:
                    counts["skipped"] += 1
                    continue

                if force and doc_id in already_indexed:
                    _delete_doc(doc_id, fconn)

                n = _insert_doc(doc_id, chunks, fconn)
                counts["indexed"] += 1
                log.info("keyword_indexed", doc_id=doc_id, file=doc["file_name"], chunks=n)

            except Exception as exc:
                counts["failed"] += 1
                log.error(
                    "keyword_index_failed",
                    doc_id=doc_id,
                    file=doc["file_name"],
                    error=str(exc),
                )

    log.info("index_keyword_complete", **counts)
    return counts
