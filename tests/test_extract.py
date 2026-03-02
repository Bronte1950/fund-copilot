"""Tests for PDF text extraction (Phase 1).

Fixtures: tests/fixtures/sample_factsheet.pdf, sample_kid.pdf
"""

from __future__ import annotations

import pytest

# TODO Phase 1: import extract module and test ExtractedPage output


@pytest.mark.skip(reason="Phase 1 not yet implemented")
def test_extract_factsheet(fixtures_dir) -> None:
    pdf_path = fixtures_dir / "sample_factsheet.pdf"
    assert pdf_path.exists(), "Add a sample factsheet PDF to tests/fixtures/"
    # pages = extract_pdf(pdf_path)
    # assert len(pages) > 0
    # assert all(p.char_count > 0 for p in pages)
