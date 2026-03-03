"""Split cleaned page text into token-sized chunks.

Reads from  data/extracted/<doc_id>.jsonl  (ExtractedPage per line)
Writes to   data/chunks/<doc_id>.jsonl     (one Chunk JSON per line)

Strategy: sliding window over the concatenated token stream of the whole doc.
  - Encode all page text to tokens, tracking which page each token came from.
  - Step forward by (chunk_size - overlap) tokens per chunk.
  - Record page_start / page_end from the token→page map.

Parameters come from Settings (chunk_size_tokens=700, chunk_overlap_tokens=100).
Token encoding: tiktoken cl100k_base (same vocab as GPT-4 / text-embedding-3-*).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import tiktoken

from src.common.config import settings
from src.common.db import DATA_DIR, MANIFEST_DB_PATH, get_sqlite_conn
from src.common.logging import get_logger
from src.common.schemas import Chunk, ChunkMetadata, ExtractedPage

log = get_logger(__name__)

EXTRACTED_DIR = DATA_DIR / "extracted"
CHUNKS_DIR = DATA_DIR / "chunks"

# Shared encoder — cl100k_base is the GPT-4 / ada-002 encoding
_ENC = tiktoken.get_encoding("cl100k_base")

# Heading detector: a line is a section heading if it is ≤ 80 chars AND either
# ALL-CAPS (with optional trailing punctuation) or ends with a colon.
_HEADING_RE = re.compile(
    r"^(?:[A-Z0-9][A-Z0-9 &/()\-]{0,78}[A-Z0-9)%]\.?|[^\n]{1,79}:)\s*$"
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _detect_heading(text: str) -> str | None:
    """Return the first line of text if it looks like a section heading."""
    first_line = text.lstrip("\n").split("\n")[0].strip()
    if first_line and _HEADING_RE.match(first_line):
        return first_line
    return None


def _load_pages(doc_id: str) -> list[ExtractedPage]:
    jsonl_path = EXTRACTED_DIR / f"{doc_id}.jsonl"
    if not jsonl_path.exists():
        return []
    pages: list[ExtractedPage] = []
    for line in jsonl_path.open(encoding="utf-8").readlines():
        line = line.rstrip("\n")
        if line.strip():
            pages.append(ExtractedPage.model_validate_json(line))
    return pages


def _load_doc_metadata(doc_id: str) -> dict:
    """Fetch provider, fund_name, doc_type, isin, ticker from manifest."""
    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        row = conn.execute(
            "SELECT provider, fund_name, doc_type, isin, ticker "
            "FROM documents WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
    if row is None:
        return {}
    return dict(row)


def _update_chunk_count(doc_id: str, count: int) -> None:
    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        conn.execute(
            "UPDATE documents SET chunk_count = ? WHERE doc_id = ?",
            (count, doc_id),
        )


# ── Core chunking logic ───────────────────────────────────────────────────────


def chunk_doc(doc_id: str) -> int:
    """Chunk all pages of a single document. Returns number of chunks written."""
    pages = _load_pages(doc_id)
    if not pages:
        log.warning("chunk_missing_jsonl", doc_id=doc_id)
        return 0

    # Skip empty docs (e.g. needs_ocr)
    if all(not p.text.strip() for p in pages):
        log.warning("chunk_empty_doc", doc_id=doc_id)
        return 0

    # ── Build token stream with page provenance ───────────────────────────────
    # token_pages[i] = page_num for token at position i
    all_tokens: list[int] = []
    token_pages: list[int] = []

    for page in pages:
        if not page.text.strip():
            continue
        tokens = _ENC.encode(page.text)
        all_tokens.extend(tokens)
        token_pages.extend([page.page_num] * len(tokens))

    if not all_tokens:
        return 0

    chunk_size = settings.chunk_size_tokens
    overlap = settings.chunk_overlap_tokens
    step = chunk_size - overlap

    # ── Fetch doc metadata once ───────────────────────────────────────────────
    meta_row = _load_doc_metadata(doc_id)
    meta = ChunkMetadata(
        provider=meta_row.get("provider"),
        fund_name=meta_row.get("fund_name"),
        doc_type=meta_row.get("doc_type", "other"),
        isin=meta_row.get("isin"),
        ticker=meta_row.get("ticker"),
    )

    # ── Sliding window ────────────────────────────────────────────────────────
    chunks: list[Chunk] = []
    start = 0
    seq = 0

    while start < len(all_tokens):
        end = min(start + chunk_size, len(all_tokens))
        window_tokens = all_tokens[start:end]
        text = _ENC.decode(window_tokens)

        page_start = token_pages[start]
        page_end = token_pages[end - 1]

        chunk = Chunk(
            doc_id=doc_id,
            chunk_id=f"{doc_id}_{seq:04d}",
            page_start=page_start,
            page_end=page_end,
            section_heading=_detect_heading(text),
            text=text,
            token_count=len(window_tokens),
            chunk_hash=_chunk_hash(text),
            metadata=meta,
        )
        chunks.append(chunk)
        seq += 1

        if end == len(all_tokens):
            break
        start += step

    # ── Write output ──────────────────────────────────────────────────────────
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CHUNKS_DIR / f"{doc_id}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(chunk.model_dump_json() + "\n")

    _update_chunk_count(doc_id, len(chunks))

    return len(chunks)


# ── Public API ────────────────────────────────────────────────────────────────


def run(force: bool = False) -> dict[str, int]:
    """Chunk extracted JSONL files for all cleaned documents.

    Processes docs with extraction_status IN ('extracted', 'needs_ocr').
    With force=True, re-chunks docs that already have chunk_count > 0.

    Returns:
        {'chunked': N, 'skipped': N, 'failed': N}
    """
    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        docs = conn.execute(
            "SELECT doc_id, file_name, chunk_count FROM documents "
            "WHERE extraction_status IN ('extracted', 'needs_ocr') "
            "ORDER BY file_name"
        ).fetchall()

    counts = {"chunked": 0, "skipped": 0, "failed": 0}

    for doc in docs:
        doc_id: str = doc["doc_id"]
        already_chunked = (doc["chunk_count"] or 0) > 0
        out_path = CHUNKS_DIR / f"{doc_id}.jsonl"

        if not force and already_chunked and out_path.exists():
            counts["skipped"] += 1
            continue

        try:
            n = chunk_doc(doc_id)
            counts["chunked"] += 1
            log.info("chunked", doc_id=doc_id, file=doc["file_name"], chunks=n)
        except Exception as exc:
            counts["failed"] += 1
            log.error("chunk_failed", doc_id=doc_id, file=doc["file_name"], error=str(exc))

    log.info("chunk_complete", **counts)
    return counts
