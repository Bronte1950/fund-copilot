# CLAUDE.md — Fund Copilot

## Project Overview

Fund Copilot is a local-first RAG (Retrieval Augmented Generation) system for UK/Ireland UCITS fund documents. It ingests ~100+ fund PDFs, indexes them with hybrid search (vector + keyword), and answers questions with mandatory citations — or refuses when evidence is missing.

**Builder**: Jack
**Status**: Phase 5 — evaluation (Run 3 pending)
**Repo**: `C:\dev\repos\fund-copilot` · https://github.com/Bronte1950/fund-copilot

This is a separate project from TERMINUS (the systematic crypto trading platform in `C:\dev\repos\systematic-trading`). Different purpose, different stack choices, different frontend aesthetic. Shares some conventions (Git workflow, Pydantic models, FastAPI patterns).

---

## Hardware

```
Machine: GMKtec NUCBOX K12 Mini PC
CPU:     AMD Ryzen 7 H 255 (8 cores) @ 3.80 GHz
RAM:     32 GB DDR5 (2x 16GB, 5600 MT/s)
GPU:     AMD Radeon 780M (3 GB shared VRAM, integrated, NO CUDA)
Storage: 1TB NVMe M.2 SSD (~800 GB free)
Network: Dual 2.5G LAN, WiFi 6E
OS:      Windows 11 Pro
Extras:  OCuLink port (external GPU upgrade path)
```

**Implications**:
- Ollama runs CPU-only. 7B–8B quantised models work well (~10–15 tokens/sec). No CUDA.
- sentence-transformers embeddings run on CPU. Fast enough (~1,000 chunks/min).
- 32GB RAM comfortably holds: Ollama model (~6GB) + Postgres + Python process.
- All development is local. Docker Desktop for Windows.

---

## Architecture — Three Boxes (non-negotiable)

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                │
│           Research Analyst aesthetic · light theme        │
│                                                         │
│   ┌──────────┐  ┌───────────┐  ┌────────────────────┐  │
│   │ QueryBar  │  │ AnswerCard │  │ SourcesPanel       │  │
│   │ + filters │  │ + stream  │  │ (citation cards)   │  │
│   └─────┬─────┘  └─────┬─────┘  └────────┬──────────┘  │
│         └───────────────┴─────────────────┘             │
│                    REST + SSE                            │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┼────────────────────────────────┐
│              API / Orchestrator (FastAPI)                 │
│                                                         │
│   POST /chat        → retrieval + LLM + grounding       │
│   POST /retrieve    → hybrid search + filters            │
│   GET  /docs        → browse indexed documents           │
│   GET  /health      → service status                     │
│   GET  /admin/stats → ingestion metrics                  │
│   POST /admin/reindex → trigger re-indexing              │
└──────┬──────────────────┬───────────────────────────────┘
       │                  │
┌──────┴──────┐   ┌──────┴──────────────────────────────┐
│  Retrieval   │   │  LLM Service                        │
│              │   │                                     │
│  vector      │   │  Ollama (llama3.1:8b, CPU)          │
│  (pgvector)  │   │  System prompt: cite or refuse      │
│      +       │   │  Grounding validation               │
│  keyword     │   │  Prompt injection defence            │
│  (FTS5)      │   │                                     │
│      ↓       │   │                                     │
│  hybrid      │   │                                     │
│  combine     │   │                                     │
└──────────────┘   └─────────────────────────────────────┘
       │
┌──────┴──────────────────────────────────────────────────┐
│              Ingest Pipeline (offline, CLI)               │
│                                                         │
│  download → inventory → extract → clean → chunk          │
│                                    → embed → index       │
│                                                         │
│  Input:  data/raw_pdfs/ + data/sources/fund_sources.csv  │
│  Output: manifest + extracted JSONL + chunks JSONL        │
│          + pgvector index + FTS5 index                   │
└─────────────────────────────────────────────────────────┘
```

**Key rule**: UI knows nothing about embeddings or chunking. Retrieval knows nothing about the LLM. The API orchestrator is the only component that talks to both. All interfaces are stable so you can swap models, swap vector DB, swap UI without re-indexing.

---

## Tech Stack

### Core

| Tech | Role | Notes |
|---|---|---|
| Python 3.10 | Backend | Same as TERMINUS for consistency |
| FastAPI | API layer | REST + SSE streaming |
| Pydantic v2 | Data models | Every schema typed |
| PostgreSQL 15 + pgvector | Vector DB + metadata | Port 5434 (TERMINUS uses 5433) |
| SQLite FTS5 | Keyword search | Ships with Python. Zero-config. |
| SQLite | Manifest DB | `data/manifest.sqlite` |
| React 18 + Vite | Frontend | Research Analyst aesthetic (NOT terminal) |
| Docker Compose | Infrastructure | Postgres + Ollama |

### RAG-specific

| Tech | Role | Notes |
|---|---|---|
| Ollama | Local LLM inference | CPU-only. `llama3.1:8b` default. |
| sentence-transformers | Local embeddings | `all-MiniLM-L6-v2` (384 dims). CPU. |
| PyMuPDF (fitz) | PDF text extraction | Fastest Python PDF lib. MIT. |
| tiktoken | Token counting | Fast, accurate chunk sizing. |

### NOT using (deliberate)

| Tech | Why not |
|---|---|
| LangChain / LlamaIndex | We build every piece to learn the full pipeline |
| ChromaDB / Pinecone / Weaviate | pgvector is sufficient and we already know Postgres |
| OpenSearch / Elasticsearch | Way too heavy for 100–1,000 docs. FTS5 is instant. |
| Next.js | React + Vite is simpler and we already know it |
| OpenAI API | Local-first. Ollama provides the same interface. |
| n8n | No operational workflows needed. Pipeline is a CLI command. |

---

## Repo Structure

```
fund-copilot/
├── README.md
├── CLAUDE.md                        # This file
├── docker-compose.yml
├── .env.example
├── .gitignore
├── pyproject.toml
│
├── data/                            # All data (gitignored)
│   ├── raw_pdfs/                    # Input PDFs by provider/
│   │   ├── vanguard/
│   │   ├── ishares/
│   │   └── ...
│   ├── sources/
│   │   └── fund_sources.csv         # URLs + metadata for downloads
│   ├── extracted/                   # JSONL per doc (per-page text)
│   ├── chunks/                      # JSONL per doc (chunked text)
│   ├── indices/                     # SQLite FTS5 database
│   ├── manifest.sqlite
│   └── eval/
│       ├── questions.jsonl
│       └── results/
│
├── src/
│   ├── __init__.py
│   ├── __main__.py                  # CLI entrypoint
│   │
│   ├── common/
│   │   ├── __init__.py
│   │   ├── config.py                # Pydantic Settings from .env
│   │   ├── logging.py               # Structured JSON logging
│   │   ├── schemas.py               # ALL Pydantic models
│   │   └── db.py                    # SQLite + Postgres connections
│   │
│   ├── ingest/
│   │   ├── __init__.py
│   │   ├── download.py              # Fetch PDFs from source CSV
│   │   ├── inventory.py             # Scan folder, build manifest
│   │   ├── extract.py               # PDF → per-page JSONL (PyMuPDF)
│   │   ├── clean.py                 # Boilerplate removal, normalisation
│   │   ├── chunk.py                 # Text → token-sized chunks
│   │   ├── embed.py                 # Chunks → vectors (sentence-transformers)
│   │   ├── index_vector.py          # Upsert into pgvector
│   │   ├── index_keyword.py         # Upsert into SQLite FTS5
│   │   └── pipeline.py              # Orchestrates full ingest
│   │
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── vector_search.py         # pgvector cosine similarity
│   │   ├── keyword_search.py        # SQLite FTS5 BM25
│   │   ├── hybrid.py                # Combine + normalise + dedup
│   │   ├── filters.py               # Metadata filtering
│   │   └── service.py               # High-level retrieval interface
│   │
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py                # Ollama HTTP client (swappable)
│   │   ├── prompts.py               # System prompts — cite or refuse
│   │   └── grounding.py             # Citation validation + refusal
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app factory
│   │   ├── routes_retrieval.py      # POST /retrieve, GET /docs
│   │   ├── routes_chat.py           # POST /chat (with SSE streaming)
│   │   └── routes_admin.py          # GET /health, GET /stats
│   │
│   └── eval/
│       ├── __init__.py
│       ├── runner.py                # Run eval question set
│       └── metrics.py               # Recall@k, precision, grounding
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── main.jsx
│       ├── api/
│       │   └── client.js
│       ├── components/
│       │   ├── QueryBar.jsx
│       │   ├── AnswerCard.jsx
│       │   ├── SourceCard.jsx
│       │   ├── SourcesPanel.jsx
│       │   ├── DocumentBrowser.jsx
│       │   ├── FilterBar.jsx
│       │   └── shared/
│       │       ├── Badge.jsx
│       │       ├── LoadingDots.jsx
│       │       └── Panel.jsx
│       ├── hooks/
│       │   ├── useChat.js
│       │   └── useDocuments.js
│       └── styles/
│           └── globals.css
│
└── tests/
    ├── conftest.py
    ├── test_extract.py
    ├── test_chunk.py
    ├── test_clean.py
    ├── test_hybrid_search.py
    ├── test_grounding.py
    └── fixtures/
        ├── sample_factsheet.pdf
        ├── sample_kid.pdf
        └── expected_chunks.jsonl
```

---

## Data Models (must be consistent across the system)

All models live in `src/common/schemas.py`. Every component imports from there.

### Document Manifest

```python
class DocumentManifest(BaseModel):
    doc_id: str              # SHA256(filepath + filesize + mtime)[:16]
    file_path: str           # Relative to data/raw_pdfs/
    file_name: str
    provider: str | None     # e.g., "Vanguard", "iShares"
    fund_name: str | None
    doc_type: str            # factsheet | kid | prospectus | annual_report | other
    isin: str | None
    ticker: str | None
    language: str            # Default: "en"
    published_date: date | None
    page_count: int
    file_size_bytes: int
    checksum: str            # SHA256 of file content
    ingested_at: datetime
    extraction_status: str   # pending | extracted | failed | needs_ocr
    chunk_count: int         # Updated after chunking
```

### Extracted Page (JSONL)

```python
class ExtractedPage(BaseModel):
    doc_id: str
    page_num: int            # 1-indexed
    text: str
    char_count: int
    extraction_method: str   # pdf_text | ocr
    has_tables: bool
```

### Chunk (JSONL)

```python
class Chunk(BaseModel):
    doc_id: str
    chunk_id: str            # f"{doc_id}_{seq:04d}"
    page_start: int
    page_end: int
    section_heading: str | None
    text: str
    token_count: int
    chunk_hash: str          # SHA256(text)[:12]
    metadata: ChunkMetadata

class ChunkMetadata(BaseModel):
    provider: str | None
    fund_name: str | None
    doc_type: str
    isin: str | None
    ticker: str | None
    as_of_date: date | None
```

### Retrieval Result

```python
class RetrievalResult(BaseModel):
    chunk_id: str
    doc_id: str
    score: float             # Normalised 0–1
    text: str
    page_start: int
    page_end: int
    section_heading: str | None
    source_file: str
    provider: str | None
    fund_name: str | None
    search_type: str         # vector | keyword | hybrid
```

### Chat Response

```python
class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: str          # high | medium | low | refused
    refusal_reason: str | None
    chunks_used: list[str]
    chunks_cited: list[str]
    model: str
    retrieval_time_ms: float
    generation_time_ms: float

class Citation(BaseModel):
    doc_id: str
    file_name: str
    page_start: int
    page_end: int
    section: str | None
    snippet: str
```

---

## Configuration

All config via environment variables loaded by Pydantic Settings. Never hardcode.

```env
# Database (pgvector) — port 5434, separate from TERMINUS (5433)
DB_PASSWORD=changeme
DB_HOST=localhost
DB_PORT=5434
DB_NAME=fund_copilot
DB_USER=copilot

# Ollama (CPU-only)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Embeddings
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384
EMBEDDING_BATCH_SIZE=64

# Retrieval
DEFAULT_TOP_K=10
HYBRID_VECTOR_WEIGHT=0.6
HYBRID_KEYWORD_WEIGHT=0.4
MAX_CONTEXT_CHUNKS=12

# Chunking
CHUNK_SIZE_TOKENS=700
CHUNK_OVERLAP_TOKENS=100

# API
API_HOST=0.0.0.0
API_PORT=8010

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
```

---

## Frontend Design — Research Analyst Aesthetic

NOT a terminal. This is a research workstation. Light, editorial, trustworthy.

**Typography**:
- Headings: Playfair Display (serif, editorial)
- Body: Source Sans 3 (clean sans-serif)
- Code/identifiers: IBM Plex Mono (ISINs, chunk IDs)
- Base size: 14px, line-height: 1.6

**Colours**:
- Background: `#FAFAF8` (warm off-white)
- Surface/cards: `#FFFFFF` with subtle shadow
- Text primary: `#1A1A2E`
- Text secondary: `#6B7280`
- Accent primary: `#1E3A5F` (deep navy)
- Accent secondary: `#C9A84C` (muted gold)
- Confidence high: `#166534` (green)
- Confidence medium: `#92400E` (amber)
- Confidence refused: `#991B1B` (red)
- Border: `#E5E7EB`

**Layout**:
- Two-column desktop: 60% query+answer (left), 40% sources (right)
- Card-based source citations with provider label, fund name, page badge, snippet
- Top nav: "Ask" | "Documents" | "Evaluation"
- Generous whitespace

---

## Coding Conventions

### Python
- Pydantic models for all data structures in `src/common/schemas.py`
- Type hints on all functions: `from __future__ import annotations`
- Config via Pydantic Settings from `.env`. Never hardcode.
- Logging: `structlog` or standard `logging` to stderr. Never `print()`.
- Error handling: log and continue for transient failures.

### Frontend
- React 18 + Vite
- Tailwind CSS for styling
- Google Fonts: Playfair Display, Source Sans 3, IBM Plex Mono
- No direct API calls from components — use hooks (`useChat`, `useDocuments`)

### Testing
- pytest with fixtures in `tests/fixtures/`
- Small test dataset (5–10 PDFs) for fast iteration

### Git
- Branch naming: `issue/<number>-<short-description>`
- Commit prefixes: `feat:`, `fix:`, `refactor:`, `test:`, `chore:`, `docs:`
- PRs reference issue numbers
- GitHub Project board: Backlog → Ready → In Progress → Done

---

## Phase Plan

### Phase 0: Skeleton + Infrastructure (half day)
- Docker Compose: Postgres+pgvector (port 5434) + Ollama
- Python project: pyproject.toml, venv, deps
- Skeleton src/ with all __init__.py files
- FastAPI /health endpoint
- Pull Ollama model: `ollama pull llama3.1:8b`
- Enable pgvector extension

### Phase 1: Ingest Pipeline (4–5 days)
- Download ~100 PDFs from curated source CSV
- Inventory + manifest (SQLite)
- Extract per-page text (PyMuPDF)
- Clean boilerplate
- Chunk (700 tokens, 100 overlap)
- Embed (sentence-transformers)
- Index: pgvector + SQLite FTS5
- Pipeline orchestrator with incremental processing

### Phase 2: Retrieval API + Hybrid Search (2–3 days)
- Vector search (pgvector cosine similarity)
- Keyword search (FTS5 BM25)
- Hybrid combination (normalise + weight + dedup)
- Metadata filters
- FastAPI routes: /retrieve, /docs, /admin/stats

### Phase 3: LLM Integration + Cite-or-Refuse (3–4 days)
- Ollama HTTP client
- System prompt for cite-or-refuse
- Context assembly (token budgeting)
- Grounding validation (citation checking)
- Refusal logic
- Prompt injection defence
- SSE streaming via FastAPI

### Phase 4: Frontend UI (4–5 days)
- React + Vite + Tailwind
- QueryBar, AnswerCard, SourcesPanel, DocumentBrowser
- SSE streaming integration
- Research Analyst aesthetic

### Phase 5: Evaluation + Tuning (3–5 days)
- 50–100 question eval set
- Metrics: Recall@k, Precision@k, grounding accuracy
- Failure diagnosis: extraction / chunking / retrieval / prompting
- Tuning experiments: chunk size, overlap, hybrid weights, model comparison

---

## Docker

```bash
# Start infrastructure
docker compose up -d    # Postgres+pgvector + Ollama

# Pull LLM model (first time only)
docker exec copilot-ollama ollama pull llama3.1:8b

# Run API (development)
python -m uvicorn src.api.main:app --port 8010 --reload

# Run ingest pipeline
python -m src.ingest.pipeline --input data/raw_pdfs/

# Run frontend
cd frontend && npm run dev
```

---

## Key Design Rules

1. **Three-box separation**: Ingest pipeline, retrieval service, and LLM service are independent. UI only talks to the API. API orchestrates everything.
2. **Cite or refuse**: The LLM must cite every claim or refuse. No hallucination tolerated. This is the whole point of the system.
3. **Local-first**: Everything runs on localhost. No cloud dependencies. Ollama for LLM, sentence-transformers for embeddings, Postgres for vectors.
4. **Stable interfaces**: Swap the embedding model → re-embed and re-index, but retrieval/LLM code doesn't change. Swap the LLM → change one config value. Swap the UI → API stays the same.
5. **Incremental processing**: Re-running the pipeline only processes new or changed documents (checksum-based).
6. **Learn by building**: No frameworks (LangChain, LlamaIndex). Every piece built from scratch to understand how RAG works end to end.
