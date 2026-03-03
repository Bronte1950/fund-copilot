"""Canonical Pydantic models for the entire system.

All components import from here — never define data models elsewhere.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Ingest ───────────────────────────────────────────────────────────────────


class DocumentManifest(BaseModel):
    doc_id: str  # SHA256(filepath + filesize + mtime)[:16]
    file_path: str  # Relative to data/raw_pdfs/
    file_name: str
    provider: str | None = None  # e.g. "Vanguard", "iShares"
    fund_name: str | None = None
    doc_type: Literal[
        "factsheet", "kid", "prospectus", "annual_report", "other"
    ] = "other"
    isin: str | None = None
    ticker: str | None = None
    language: str = "en"
    published_date: date | None = None
    page_count: int = 0
    file_size_bytes: int = 0
    checksum: str = ""  # SHA256 of file content
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
    extraction_status: Literal[
        "pending", "extracted", "failed", "needs_ocr"
    ] = "pending"
    chunk_count: int = 0  # Updated after chunking


class ExtractedPage(BaseModel):
    doc_id: str
    page_num: int  # 1-indexed
    text: str
    char_count: int
    extraction_method: Literal["pdf_text", "ocr"] = "pdf_text"
    has_tables: bool = False


class ChunkMetadata(BaseModel):
    provider: str | None = None
    fund_name: str | None = None
    doc_type: str = "other"
    isin: str | None = None
    ticker: str | None = None
    as_of_date: date | None = None


class Chunk(BaseModel):
    doc_id: str
    chunk_id: str  # f"{doc_id}_{seq:04d}"
    page_start: int
    page_end: int
    section_heading: str | None = None
    text: str
    token_count: int
    chunk_hash: str  # SHA256(text)[:12]
    metadata: ChunkMetadata


# ── Retrieval ─────────────────────────────────────────────────────────────────


class RetrievalResult(BaseModel):
    chunk_id: str
    doc_id: str
    score: float  # Normalised 0–1
    text: str
    page_start: int
    page_end: int
    section_heading: str | None = None
    source_file: str
    provider: str | None = None
    fund_name: str | None = None
    search_type: Literal["vector", "keyword", "hybrid"] = "hybrid"


class RetrievalRequest(BaseModel):
    query: str
    top_k: int = 10
    provider: str | None = None
    doc_type: str | None = None
    isin: str | None = None


# ── Chat ──────────────────────────────────────────────────────────────────────


class Citation(BaseModel):
    doc_id: str
    file_name: str
    provider: str | None = None
    fund_name: str | None = None
    page_start: int
    page_end: int
    section: str | None = None
    snippet: str
    url: str | None = None  # Yahoo Finance link (live_data citations only)
    citation_type: Literal["document", "live_data"] = "document"


class ChatRequest(BaseModel):
    query: str
    provider: str | None = None
    doc_type: str | None = None
    isin: str | None = None
    top_k: int = 10


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: Literal["high", "medium", "low", "refused"] = "refused"
    refusal_reason: str | None = None
    chunks_used: list[str] = Field(default_factory=list)
    chunks_cited: list[str] = Field(default_factory=list)
    model: str
    retrieval_time_ms: float
    generation_time_ms: float


# ── Live Data ─────────────────────────────────────────────────────────────────


class FundLiveData(BaseModel):
    isin: str
    resolved_ticker: str | None = None
    fund_name: str | None = None
    currency: str | None = None
    price: float | None = None
    price_change_pct: float | None = None
    nav: float | None = None
    aum_millions: float | None = None
    ytd_return_pct: float | None = None
    one_year_return_pct: float | None = None
    expense_ratio_pct: float | None = None
    dividend_yield_pct: float | None = None
    yahoo_url: str | None = None  # https://finance.yahoo.com/quote/{ticker}
    fetched_at: datetime
    fetch_status: Literal["ok", "stale", "no_ticker", "fetch_error"] = "ok"


class LiveDataRefreshResult(BaseModel):
    refreshed: int
    skipped: int
    failed: int
    duration_ms: float
    isins_refreshed: list[str]


class LiveFundsResponse(BaseModel):
    funds: list[FundLiveData]
    cache_age_hours: float | None = None
    total: int


# ── Health ─────────────────────────────────────────────────────────────────────


class ServiceStatus(BaseModel):
    status: Literal["ok", "error"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    timestamp: str
    version: str
    services: dict[str, dict]
