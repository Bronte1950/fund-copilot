"""Ollama HTTP client — thin async wrapper over the Ollama REST API.

Supports:
    - /api/chat  (chat completion, streaming and non-streaming)
    - /api/tags  (list available models)

Designed to be swappable: same interface works with any OpenAI-compatible
endpoint — just change the base_url and adjust the payload shape.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from src.common.config import settings
from src.common.logging import get_logger

log = get_logger(__name__)

# Shared async client — created lazily, reused across requests.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=httpx.Timeout(connect=5.0, read=600.0, write=30.0, pool=5.0),
        )
    return _client


async def close_client() -> None:
    """Close the shared HTTP client. Call during application shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None


async def list_models() -> list[str]:
    """Return names of models currently available in Ollama."""
    client = _get_client()
    resp = await client.get("/api/tags")
    resp.raise_for_status()
    return [m["name"] for m in resp.json().get("models", [])]


async def generate(
    messages: list[dict],
    model: str | None = None,
) -> str:
    """Run a non-streaming chat completion and return the full response text.

    Args:
        messages: list of {"role": ..., "content": ...} dicts.
        model: Ollama model name; defaults to settings.ollama_model.

    Returns:
        The assistant's full response text.
    """
    model = model or settings.ollama_model
    client = _get_client()
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        # Cap generation length.  Without this, llama3.1:8b can produce 1,000+
        # token answers on verbose topics (bond fund methodologies, etc.) which
        # pushes total time past the 600s read timeout.  512 tokens ≈ 3–4 dense
        # paragraphs — plenty for a fund document Q&A answer.
        "options": {"num_predict": 512},
    }

    log.debug("ollama_generate_start", model=model, n_messages=len(messages))
    try:
        resp = await client.post("/api/chat", json=payload)
        resp.raise_for_status()
    except httpx.ReadTimeout:
        # Force-close the stale connection so the next call gets a fresh one.
        # Without this, the asyncio event loop blocks for hours draining the
        # socket while Ollama continues generating on the other end.
        await close_client()
        raise

    data = resp.json()
    return data["message"]["content"]


async def stream_generate(
    messages: list[dict],
    model: str | None = None,
) -> AsyncIterator[str]:
    """Stream a chat completion, yielding incremental text tokens.

    Args:
        messages: list of {"role": ..., "content": ...} dicts.
        model: Ollama model name; defaults to settings.ollama_model.

    Yields:
        Incremental text strings as the model generates them.
    """
    model = model or settings.ollama_model
    client = _get_client()
    payload = {"model": model, "messages": messages, "stream": True}

    log.debug("ollama_stream_start", model=model, n_messages=len(messages))
    async with client.stream("POST", "/api/chat", json=payload) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                log.warning("ollama_stream_bad_line", line=line[:120])
                continue
            content = chunk.get("message", {}).get("content", "")
            if content:
                yield content
            if chunk.get("done"):
                break
