"""Download PDFs from fund_sources.csv.

Phase 1 implementation.

Input:  data/sources/fund_sources.csv  (url, provider, fund_name, doc_type, isin, ...)
Output: data/raw_pdfs/<provider>/<filename>.pdf
"""

from __future__ import annotations

# TODO Phase 1: implement download with httpx, skip already-downloaded (checksum)
