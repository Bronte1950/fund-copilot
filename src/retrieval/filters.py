"""Metadata filtering for retrieval queries.

Phase 2 implementation.

Supported filters (all optional, AND-combined):
    - provider    (e.g. "Vanguard", "iShares")
    - doc_type    (factsheet | kid | prospectus | annual_report)
    - isin        (e.g. "IE00B3RBWM25")
    - fund_name   (partial match)
"""

from __future__ import annotations

# TODO Phase 2: build SQL WHERE clauses and FTS5 filter expressions from RetrievalRequest
