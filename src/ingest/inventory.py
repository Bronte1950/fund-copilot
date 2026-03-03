"""Scan data/raw_pdfs/ and build/update the document manifest in manifest.sqlite.

Runs as the first step of the ingest pipeline. Every subsequent step
(extract, chunk, embed, index) reads from manifest.sqlite to know what to process.

Incremental: files whose checksum hasn't changed are skipped unless --force.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import fitz  # PyMuPDF

from src.common.db import MANIFEST_DB_PATH, get_sqlite_conn
from src.common.logging import get_logger
from src.common.schemas import DocumentManifest

log = get_logger(__name__)

RAW_PDFS_DIR = Path("data/raw_pdfs")

# ── Provider display names ────────────────────────────────────────────────────

PROVIDER_NAMES: dict[str, str] = {
    "baillie_gifford": "Baillie Gifford",
    "fidelity": "Fidelity",
    "fundsmith": "Fundsmith",
    "hamiltonlane": "Hamilton Lane",
    "hanetf": "HANetf",
    "hsbc": "HSBC",
    "invesco": "Invesco",
    "ishares": "iShares",
    "jupiter": "Jupiter",
    "lansdowne": "Lansdowne",
    "lgim": "LGIM",
    "ritcap": "RIT Capital",
    "vaneck": "VanEck",
    "vanguard": "Vanguard",
    "wisdomtree": "WisdomTree",
}

# ── ISIN pattern — GB/IE/LU/US/FR/DE are common UCITS domiciles ──────────────

_ISIN_RE = re.compile(r"\b(GB|IE|LU|US|FR|DE)[A-Z0-9]{10}\b", re.IGNORECASE)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _compute_doc_id(rel_path: str, size: int, mtime: float) -> str:
    """Stable 16-char ID: changes only when the file moves or its content changes."""
    raw = f"{rel_path}|{size}|{mtime:.0f}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _compute_checksum(file_path: Path) -> str:
    """SHA256 of the full file content."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for block in iter(lambda: f.read(65_536), b""):
            h.update(block)
    return h.hexdigest()


def _infer_provider(folder_name: str) -> str:
    return PROVIDER_NAMES.get(folder_name.lower(), folder_name.replace("_", " ").title())


def _infer_doc_type(filename: str) -> str:
    name = filename.lower()
    if "factsheet" in name or "fact-sheet" in name:
        return "factsheet"
    if "kiid" in name or "kid" in name:
        return "kid"
    if "prospectus" in name:
        return "prospectus"
    if "annual" in name or "report" in name:
        return "annual_report"
    # Vanguard/HSBC style: {isin}-{lang}.pdf  e.g. gb00b3tyhh97-en.pdf
    stem = name.rsplit(".", 1)[0]
    if re.match(r"^[a-z]{2}[0-9a-z]{10}-[a-z]{2}$", stem):
        return "factsheet"
    return "other"


def _extract_isin(stem: str) -> str | None:
    """Try to extract an ISIN from the filename stem (without extension)."""
    m = _ISIN_RE.search(stem)
    return m.group(0).upper() if m else None


def _get_page_count(file_path: Path) -> int:
    try:
        with fitz.open(str(file_path)) as doc:
            return len(doc)
    except Exception as exc:
        log.warning("page_count_failed", file=file_path.name, error=str(exc))
        return 0


def _iter_pdfs(raw_pdfs_dir: Path) -> Iterator[tuple[Path, str]]:
    """Yield (absolute_path, provider_display_name) for every PDF in the tree."""
    for pdf_path in sorted(raw_pdfs_dir.rglob("*.pdf")):
        parts = pdf_path.relative_to(raw_pdfs_dir).parts
        provider_folder = parts[0] if parts else "unknown"
        yield pdf_path, _infer_provider(provider_folder)


# ── Database ──────────────────────────────────────────────────────────────────


def init_manifest_db() -> None:
    """Create the documents table if it doesn't exist."""
    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id            TEXT PRIMARY KEY,
                file_path         TEXT NOT NULL UNIQUE,
                file_name         TEXT NOT NULL,
                provider          TEXT,
                fund_name         TEXT,
                doc_type          TEXT NOT NULL DEFAULT 'other',
                isin              TEXT,
                ticker            TEXT,
                language          TEXT NOT NULL DEFAULT 'en',
                published_date    TEXT,
                page_count        INTEGER NOT NULL DEFAULT 0,
                file_size_bytes   INTEGER NOT NULL DEFAULT 0,
                checksum          TEXT NOT NULL DEFAULT '',
                ingested_at       TEXT NOT NULL,
                extraction_status TEXT NOT NULL DEFAULT 'pending',
                chunk_count       INTEGER NOT NULL DEFAULT 0
            )
        """)
    log.info("manifest_db_ready", path=str(MANIFEST_DB_PATH))


def _upsert(conn: sqlite3.Connection, doc: DocumentManifest, force: bool = False) -> bool:
    """Insert or update a document row. Returns True if the row was new or changed."""
    if not force:
        existing = conn.execute(
            "SELECT checksum FROM documents WHERE doc_id = ?", (doc.doc_id,)
        ).fetchone()
        if existing and existing["checksum"] == doc.checksum:
            return False  # Nothing changed

    conn.execute(
        """
        INSERT INTO documents (
            doc_id, file_path, file_name, provider, fund_name, doc_type,
            isin, ticker, language, published_date, page_count,
            file_size_bytes, checksum, ingested_at, extraction_status, chunk_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
            file_path         = excluded.file_path,
            doc_type          = excluded.doc_type,
            isin              = excluded.isin,
            checksum          = excluded.checksum,
            page_count        = excluded.page_count,
            file_size_bytes   = excluded.file_size_bytes,
            ingested_at       = excluded.ingested_at,
            extraction_status = 'pending',
            chunk_count       = 0
        """,
        (
            doc.doc_id, doc.file_path, doc.file_name, doc.provider, doc.fund_name,
            doc.doc_type, doc.isin, doc.ticker, doc.language,
            doc.published_date.isoformat() if doc.published_date else None,
            doc.page_count, doc.file_size_bytes, doc.checksum,
            doc.ingested_at.isoformat(), doc.extraction_status, doc.chunk_count,
        ),
    )
    return True


# ── Public API ────────────────────────────────────────────────────────────────


def run(raw_pdfs_dir: Path = RAW_PDFS_DIR, force: bool = False) -> list[DocumentManifest]:
    """Scan raw_pdfs_dir and upsert all PDFs into manifest.sqlite.

    Args:
        raw_pdfs_dir: Root of the PDF tree. Default: data/raw_pdfs/
        force: Reprocess all docs even if checksums match.

    Returns:
        List of DocumentManifest for every discovered PDF.
    """
    init_manifest_db()

    discovered: list[DocumentManifest] = []
    new_count = 0
    skipped_count = 0

    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        for pdf_path, provider in _iter_pdfs(raw_pdfs_dir):
            stat = pdf_path.stat()
            rel_path = str(pdf_path.relative_to(raw_pdfs_dir.parent))

            doc_id = _compute_doc_id(rel_path, stat.st_size, stat.st_mtime)
            checksum = _compute_checksum(pdf_path)

            doc = DocumentManifest(
                doc_id=doc_id,
                file_path=rel_path,
                file_name=pdf_path.name,
                provider=provider,
                doc_type=_infer_doc_type(pdf_path.name),
                isin=_extract_isin(pdf_path.stem),
                page_count=_get_page_count(pdf_path),
                file_size_bytes=stat.st_size,
                checksum=checksum,
                ingested_at=datetime.now(timezone.utc),
                extraction_status="pending",
            )

            changed = _upsert(conn, doc, force=force)

            if changed:
                new_count += 1
                log.info(
                    "document_discovered",
                    doc_id=doc_id,
                    provider=provider,
                    doc_type=doc.doc_type,
                    isin=doc.isin,
                    pages=doc.page_count,
                    file=pdf_path.name,
                )
            else:
                skipped_count += 1

            discovered.append(doc)

    log.info(
        "inventory_complete",
        total=len(discovered),
        new_or_changed=new_count,
        skipped=skipped_count,
    )
    return discovered
