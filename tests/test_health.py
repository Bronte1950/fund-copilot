"""Tests for the /health endpoint.

These run against the FastAPI test client without requiring live services.
The endpoint is expected to return 200 even when services are degraded.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200


def test_health_schema(client: TestClient) -> None:
    data = client.get("/health").json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert "timestamp" in data
    assert "version" in data
    assert "services" in data
    assert "postgres" in data["services"]
    assert "ollama" in data["services"]
