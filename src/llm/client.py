"""Ollama HTTP client — thin wrapper over the Ollama REST API.

Phase 3 implementation.

Supports:
    - /api/generate  (completion, streaming)
    - /api/chat      (chat, streaming)
    - /api/tags      (list models)

Designed to be swappable: same interface works with any OpenAI-compatible endpoint.
"""

from __future__ import annotations

# TODO Phase 3: implement async generate() and stream_generate() using httpx
