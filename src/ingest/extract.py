"""Extract per-page text from PDFs using PyMuPDF (fitz).

Input:  manifest.sqlite  (docs with extraction_status = 'pending' or 'failed')
Output: data/extracted/<doc_id>.jsonl  (one ExtractedPage JSON per line)

After extraction, manifest.extraction_status is updated to:
  'extracted'  — text successfully pulled from the PDF
  'needs_ocr'  — PDF is scanned/image-only (average < 50 chars/page)
  'failed'     — PyMuPDF raised an exception
"""

from __future__ import annotations

import warnings
from pathlib import Path

import fitz  # PyMuPDF

from src.common.db import DATA_DIR, MANIFEST_DB_PATH, get_sqlite_conn
from src.common.logging import get_logger
from src.common.schemas import ExtractedPage

# Suppress pymupdf_layout suggestion — we don't need layout analysis
warnings.filterwarnings("ignore", message=".*pymupdf_layout.*")

log = get_logger(__name__)

EXTRACTED_DIR = DATA_DIR / "extracted"

# Pages with fewer average chars than this across the whole doc → flag needs_ocr
_MIN_AVG_CHARS = 50


# ── Core extraction ───────────────────────────────────────────────────────────


def _extract_pdf(doc_id: str, pdf_path: Path) -> tuple[list[ExtractedPage], str]:
    """Extract all pages from a single PDF.

    Returns:
        (pages, status) where status is 'extracted', 'needs_ocr', or 'failed'.
    """
    pages: list[ExtractedPage] = []

    try:
        with fitz.open(str(pdf_path)) as doc:
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text("text")
                char_count = len(text.strip())

                has_tables = False
                try:
                    tabs = page.find_tables()
                    has_tables = len(tabs.tables) > 0
                except Exception:
                    pass  # find_tables may not work on all page types

                pages.append(
                    ExtractedPage(
                        doc_id=doc_id,
                        page_num=page_num,
                        text=text,
                        char_count=char_count,
                        extraction_method="pdf_text",
                        has_tables=has_tables,
                    )
                )
    except Exception as exc:
        log.error("pdf_open_failed", doc_id=doc_id, file=pdf_path.name, error=str(exc))
        return [], "failed"

    if not pages:
        return [], "failed"

    avg_chars = sum(p.char_count for p in pages) / len(pages)
    status = "needs_ocr" if avg_chars < _MIN_AVG_CHARS else "extracted"

    return pages, status


def _write_jsonl(doc_id: str, pages: list[ExtractedPage]) -> Path:
    """Serialise pages to data/extracted/<doc_id>.jsonl, one JSON object per line."""
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXTRACTED_DIR / f"{doc_id}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for page in pages:
            f.write(page.model_dump_json() + "\n")
    return out_path


def _update_manifest_status(doc_id: str, status: str) -> None:
    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        conn.execute(
            "UPDATE documents SET extraction_status = ? WHERE doc_id = ?",
            (status, doc_id),
        )


# ── Public API ────────────────────────────────────────────────────────────────


def run(force: bool = False) -> dict[str, int]:
    """Extract text from all eligible documents in the manifest.

    Processes docs with extraction_status IN ('pending', 'failed').
    With force=True, also re-extracts 'extracted' and 'needs_ocr' docs.

    Returns:
        {'extracted': N, 'needs_ocr': N, 'failed': N, 'skipped': N}
    """
    if force:
        status_filter = ("pending", "failed", "extracted", "needs_ocr")
    else:
        status_filter = ("pending", "failed")

    placeholders = ",".join("?" * len(status_filter))

    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        docs = conn.execute(
            f"SELECT doc_id, file_path, file_name FROM documents "
            f"WHERE extraction_status IN ({placeholders}) ORDER BY file_name",
            status_filter,
        ).fetchall()

    if not docs:
        log.info("extract_nothing_to_do")
        return {"extracted": 0, "needs_ocr": 0, "failed": 0, "skipped": 0}

    counts: dict[str, int] = {"extracted": 0, "needs_ocr": 0, "failed": 0, "skipped": 0}

    for doc in docs:
        doc_id: str = doc["doc_id"]
        pdf_path = DATA_DIR / doc["file_path"]
        out_path = EXTRACTED_DIR / f"{doc_id}.jsonl"

        # Skip if JSONL already exists and we're not forcing
        if not force and out_path.exists():
            counts["skipped"] += 1
            continue

        log.info("extracting", doc_id=doc_id, file=doc["file_name"])

        pages, status = _extract_pdf(doc_id, pdf_path)

        if pages:
            _write_jsonl(doc_id, pages)

        _update_manifest_status(doc_id, status)
        counts[status] += 1

        log.info(
            "extracted_doc",
            doc_id=doc_id,
            file=doc["file_name"],
            pages=len(pages),
            status=status,
        )

    log.info("extract_complete", **counts)
    return counts
