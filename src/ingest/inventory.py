"""Scan data/raw_pdfs/ and build/update the document manifest.

Phase 1 implementation.

Output: manifest.sqlite rows (DocumentManifest)
"""

from __future__ import annotations

# TODO Phase 1: walk raw_pdfs/, compute doc_id = SHA256(path+size+mtime)[:16],
#               write DocumentManifest rows to manifest.sqlite
