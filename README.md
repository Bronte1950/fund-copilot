# Fund Copilot

A local-first RAG (Retrieval Augmented Generation) system for UK/Ireland UCITS fund documents.

Ingests ~100+ fund PDFs (factsheets, KIDs, prospectuses), indexes them with hybrid search (vector + keyword), and answers questions with mandatory citations — or refuses when evidence is missing.

## What it does

- **Ingest**: Download PDFs → extract text → chunk → embed → index (pgvector + SQLite FTS5)
- **Retrieve**: Hybrid search combining vector similarity and BM25 keyword scoring
- **Answer**: Ollama LLM generates answers with inline citations. No citation → no answer.
- **Browse**: React UI for querying and browsing indexed documents

## Stack

| Layer | Tech |
|---|---|
| LLM | Ollama (`llama3.1:8b`, CPU-only) |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU) |
| Vector DB | PostgreSQL 15 + pgvector |
| Keyword search | SQLite FTS5 (BM25) |
| API | FastAPI + SSE streaming |
| Frontend | React 18 + Vite + Tailwind |
| PDF extraction | PyMuPDF |

No LangChain. No LlamaIndex. Every piece built from scratch.

## Hardware target

Runs entirely on a local machine — no cloud required.

- AMD Ryzen 7 (8-core) + 32 GB DDR5
- AMD integrated GPU (no CUDA) — Ollama runs on CPU
- ~10–15 tokens/sec for `llama3.1:8b`

## Quick start

```bash
# Start infrastructure
docker compose up -d

# Pull the LLM model (first time)
docker exec copilot-ollama ollama pull llama3.1:8b

# Install Python deps
pip install -e ".[dev]"

# Start the API
python -m src api --reload

# Start the frontend
cd frontend && npm run dev
```

API runs at `http://localhost:8010`. Frontend at `http://localhost:5173`.

## Architecture

```
Frontend (React + Vite)
    ↕  REST + SSE
API / Orchestrator (FastAPI)
    ↕               ↕
Retrieval           LLM Service
(pgvector + FTS5)   (Ollama)
    ↑
Ingest Pipeline (offline CLI)
(download → extract → chunk → embed → index)
```

Three-box separation: ingest, retrieval, and LLM are independent. Swap any component without touching the others.

## Status

- [x] Phase 0 — project scaffold, Docker, FastAPI skeleton
- [ ] Phase 1 — ingest pipeline (download → extract → chunk → embed → index)
- [ ] Phase 2 — retrieval API + hybrid search
- [ ] Phase 3 — LLM integration + cite-or-refuse
- [ ] Phase 4 — React frontend (Research Analyst aesthetic)
- [ ] Phase 5 — evaluation + tuning

## Design principles

1. **Cite or refuse** — the LLM must cite every claim or decline to answer. No hallucination.
2. **Local-first** — everything runs on localhost. No cloud APIs, no external dependencies.
3. **Stable interfaces** — swap embedding model, LLM, or UI independently without re-architecting.
4. **Learn by building** — no RAG frameworks. Every piece built from scratch to understand the full pipeline.
5. **Incremental processing** — re-running the pipeline only processes new/changed documents.
