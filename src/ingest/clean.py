"""Remove boilerplate and normalise extracted page text.

Reads from  data/extracted/<doc_id>.jsonl  (ExtractedPage per line)
Writes back to the same files with cleaned text fields.

Two-pass approach:
  1. Per-page: fix encoding artifacts, remove regex-matched boilerplate, normalise whitespace.
  2. Cross-page: find paragraphs that repeat across 3+ pages of the same doc and strip them
     (catches repeated headers/footers that pattern-matching misses).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

from src.common.db import DATA_DIR, MANIFEST_DB_PATH, get_sqlite_conn
from src.common.logging import get_logger
from src.common.schemas import ExtractedPage

log = get_logger(__name__)

EXTRACTED_DIR = DATA_DIR / "extracted"

# ── Unicode / encoding fixes ──────────────────────────────────────────────────

# PDF ligature artifacts and common mojibake
_LIGATURES = str.maketrans({
    "\ufb01": "fi",   # ﬁ
    "\ufb02": "fl",   # ﬂ
    "\ufb00": "ff",   # ﬀ
    "\ufb03": "ffi",  # ﬃ
    "\ufb04": "ffl",  # ﬄ
    "\u2019": "'",    # right single quote
    "\u2018": "'",    # left single quote
    "\u201c": '"',    # left double quote
    "\u201d": '"',    # right double quote
    "\u2013": "-",    # en dash
    "\u2014": "-",    # em dash
    "\u2022": "*",    # bullet
    "\u00a0": " ",    # non-breaking space
    "\u200b": "",     # zero-width space
    "\ufffd": "",     # replacement character (encoding garbage)
})

# ── Boilerplate patterns ──────────────────────────────────────────────────────
# Each pattern is applied per-page, case-insensitive, over the full text block.
# Keep patterns specific enough not to destroy useful content.

_BOILERPLATE: list[re.Pattern] = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in [
    # Page numbering
    r"^\s*\d{1,3}\s+of\s+\d{1,3}\s*$",           # "2 of 4"
    r"^\s*-\s*\d{1,3}\s*-\s*$",                   # "- 2 -"
    r"^\s*page\s+\d{1,3}\s*(of\s+\d{1,3})?\s*$",  # "Page 2 of 4"

    # UCITS legal disclaimers
    r"past performance does not (predict|guarantee) future returns?\.?",
    r"the figures are calculated in the share class base currency[^.\n]*\.",
    r"this (document|communication) is (intended for|marketing material)[^.\n]*\.",
    r"this is a marketing communication[^.\n]*\.",
    r"please refer to the (prospectus|kiid|kid|priips)[^.\n]*\.",
    r"investors? should read the (kiid|kid|priips)[^.\n]*\.",
    r"for definition of terms[^.\n]*\.",
    r"capital (at risk|is at risk)[^.\n]*\.",

    # Source / data attribution lines
    r"^(all data )?source:?\s*[^.\n]{0,60}\bdata as at\b[^.\n]*\.$",
    r"^all data source[^.\n]*unless otherwise stated[^.\n]*\.$",
    r"^performance,\s*portfolio breakdowns[^.\n]*\.$",

    # Contact blocks (iShares / BlackRock style)
    r"contact us[\s\S]{0,10}for emea[^.\n]*\.",
    r"\+44[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{4}",    # UK phone numbers
    r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}",     # email addresses
    r"www\.[a-z0-9.-]+\.[a-z]{2,}",               # URLs

    # Decorative lines
    r"^[-_=]{4,}\s*$",
]]


# ── Step 1: per-page cleaning ─────────────────────────────────────────────────


def clean_text(text: str) -> str:
    """Apply all per-page cleaning rules to a single text string."""
    # Fix ligatures and encoding artifacts
    text = text.translate(_LIGATURES)

    # NFKC normalisation — decomposes compatibility characters
    text = unicodedata.normalize("NFKC", text)

    # Strip non-printable control chars (keep \n and \t)
    text = re.sub(r"[^\S\n\t]+", " ", text)        # collapse inline whitespace
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)  # trailing spaces per line

    # Apply boilerplate patterns
    for pattern in _BOILERPLATE:
        text = pattern.sub("", text)

    # Standalone page numbers on their own line (after boilerplate removal)
    text = re.sub(r"^\s*\d{1,3}\s*$", "", text, flags=re.MULTILINE)

    # Collapse excessive blank lines (max 2 consecutive)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ── Step 2: cross-page deduplication ─────────────────────────────────────────


def _get_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs (separated by blank lines), normalised for comparison."""
    paras = re.split(r"\n\s*\n", text)
    return [" ".join(p.split()) for p in paras if len(p.strip()) >= 30]


def find_repeated_blocks(pages: list[ExtractedPage]) -> set[str]:
    """Return paragraph texts that appear on 3+ pages (likely headers/footers)."""
    if len(pages) < 3:
        return set()

    counts: Counter[str] = Counter()
    for page in pages:
        seen_this_page: set[str] = set()
        for para in _get_paragraphs(page.text):
            if para not in seen_this_page:
                counts[para] += 1
                seen_this_page.add(para)

    threshold = min(3, len(pages))
    return {para for para, n in counts.items() if n >= threshold}


def remove_repeated_blocks(text: str, repeated: set[str]) -> str:
    """Strip repeated paragraphs from text."""
    if not repeated:
        return text
    paras = re.split(r"(\n\s*\n)", text)  # preserve separators
    result_parts = []
    for part in paras:
        normalised = " ".join(part.split())
        if normalised in repeated:
            result_parts.append("")
        else:
            result_parts.append(part)
    return re.sub(r"\n{3,}", "\n\n", "".join(result_parts)).strip()


# ── Public API ────────────────────────────────────────────────────────────────


def clean_doc(doc_id: str) -> int:
    """Clean all pages of a single document. Returns number of pages cleaned."""
    jsonl_path = EXTRACTED_DIR / f"{doc_id}.jsonl"
    if not jsonl_path.exists():
        log.warning("clean_missing_jsonl", doc_id=doc_id)
        return 0

    pages: list[ExtractedPage] = []
    # Use readlines() not splitlines() — splitlines() splits on bare \r too,
    # which breaks JSON lines that contain carriage-return characters in text fields.
    for line in jsonl_path.open(encoding="utf-8").readlines():
        line = line.rstrip("\n")
        if line.strip():
            pages.append(ExtractedPage.model_validate_json(line))

    # Pass 1 — per-page cleaning
    for page in pages:
        page.text = clean_text(page.text)
        page.char_count = len(page.text.strip())

    # Pass 2 — cross-page dedup
    repeated = find_repeated_blocks(pages)
    if repeated:
        log.debug("removing_repeated_blocks", doc_id=doc_id, count=len(repeated))
        for page in pages:
            page.text = remove_repeated_blocks(page.text, repeated)
            page.char_count = len(page.text.strip())

    # Write back
    with jsonl_path.open("w", encoding="utf-8") as f:
        for page in pages:
            f.write(page.model_dump_json() + "\n")

    return len(pages)


def run(force: bool = False) -> dict[str, int]:
    """Clean extracted JSONL files for all documents in the manifest.

    Processes all docs with extraction_status = 'extracted'.
    With force=True also re-cleans docs already cleaned.

    Returns:
        {'cleaned': N, 'skipped': N, 'failed': N}
    """
    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        docs = conn.execute(
            "SELECT doc_id, file_name FROM documents "
            "WHERE extraction_status IN ('extracted', 'needs_ocr') "
            "ORDER BY file_name"
        ).fetchall()

    counts = {"cleaned": 0, "skipped": 0, "failed": 0}

    for doc in docs:
        doc_id: str = doc["doc_id"]
        try:
            n = clean_doc(doc_id)
            counts["cleaned"] += 1
            log.info("cleaned", doc_id=doc_id, file=doc["file_name"], pages=n)
        except Exception as exc:
            counts["failed"] += 1
            log.error("clean_failed", doc_id=doc_id, file=doc["file_name"], error=str(exc))

    log.info("clean_complete", **counts)
    return counts
