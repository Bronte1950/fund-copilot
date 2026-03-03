"""SQLite FTS5 BM25 keyword search.

bm25() in FTS5 returns negative values — we negate to get a positive score
(higher = more relevant), consistent with the vector score convention.
"""

from __future__ import annotations

import re
import sqlite3

from src.common.db import FTS_DB_PATH
from src.common.schemas import RetrievalRequest, RetrievalResult

_KW_SQL = """
SELECT
    kw.chunk_id,
    kw.doc_id,
    -bm25(fts)  AS score,
    fts.text,
    kw.page_start,
    kw.page_end,
    kw.section_heading,
    kw.provider,
    kw.doc_type,
    kw.isin
FROM fts
JOIN chunks_kw kw ON fts.rowid = kw.rowid
WHERE fts MATCH ?
  AND (kw.doc_type = ? OR ? IS NULL)
  AND (kw.provider = ? OR ? IS NULL)
  AND (kw.isin     = ? OR ? IS NULL)
ORDER BY bm25(fts)
LIMIT ?
"""


def _fts_query(text: str) -> str:
    """Convert free text to a safe FTS5 MATCH expression.

    Each whitespace-separated token is double-quoted so FTS5 treats it as a
    literal term rather than interpreting it as an operator.
    Internal double-quotes are escaped by doubling them.
    """
    tokens = re.split(r"\s+", text.strip())
    tokens = [t for t in tokens if t]
    if not tokens:
        return '""'
    return " ".join('"' + t.replace('"', '""') + '"' for t in tokens)


def keyword_search(
    query: str,
    top_k: int,
    request: RetrievalRequest,
) -> list[RetrievalResult]:
    """Run a BM25 FTS5 search and return scored RetrievalResults."""
    fts_q = _fts_query(query)

    conn = sqlite3.connect(str(FTS_DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            _KW_SQL,
            (
                fts_q,
                request.doc_type, request.doc_type,
                request.provider, request.provider,
                request.isin,     request.isin,
                top_k,
            ),
        ).fetchall()
    except sqlite3.OperationalError:
        # FTS5 raises OperationalError when the query matches no tokens at all
        rows = []
    finally:
        conn.close()

    results = []
    for row in rows:
        results.append(
            RetrievalResult(
                chunk_id=row["chunk_id"],
                doc_id=row["doc_id"],
                score=float(row["score"]),
                text=row["text"],
                page_start=row["page_start"],
                page_end=row["page_end"],
                section_heading=row["section_heading"],
                source_file="",  # enriched in service.py
                provider=row["provider"],
                fund_name=None,  # not stored in FTS index, enriched later
                search_type="keyword",
            )
        )
    return results
