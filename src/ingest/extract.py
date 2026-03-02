"""Extract per-page text from PDFs using PyMuPDF.

Phase 1 implementation.

Input:  data/raw_pdfs/<provider>/<file>.pdf
Output: data/extracted/<doc_id>.jsonl  (one ExtractedPage per line)
"""

from __future__ import annotations

# TODO Phase 1: open PDF with fitz, iterate pages, detect tables, write JSONL
