"""Shared pytest fixtures for the Fund Copilot test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Synchronous TestClient for FastAPI route tests."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def fixtures_dir():
    """Path to tests/fixtures/."""
    from pathlib import Path
    return Path(__file__).parent / "fixtures"
