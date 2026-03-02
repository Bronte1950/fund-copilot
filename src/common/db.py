"""Database connection helpers — Postgres (asyncpg) and SQLite.

Usage:
    # Postgres
    async with get_postgres_conn() as conn:
        rows = await conn.fetch("SELECT ...")

    # SQLite (manifest, FTS5)
    with get_sqlite_conn(MANIFEST_DB_PATH) as conn:
        conn.execute("INSERT INTO ...")
"""

from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import AsyncGenerator, Generator

import asyncpg

from src.common.config import settings

# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path("data")
MANIFEST_DB_PATH = DATA_DIR / "manifest.sqlite"
FTS_DB_PATH = DATA_DIR / "indices" / "fts.sqlite"


# ── Postgres ──────────────────────────────────────────────────────────────────


@asynccontextmanager
async def get_postgres_conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Async context manager yielding a single Postgres connection."""
    conn: asyncpg.Connection = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        database=settings.db_name,
        user=settings.db_user,
        password=settings.db_password,
    )
    try:
        yield conn
    finally:
        await conn.close()


async def check_postgres() -> dict:
    """Return a status dict for the Postgres / pgvector service."""
    try:
        async with get_postgres_conn() as conn:
            version_row = await conn.fetchval("SELECT version()")
            pgvector_ver = await conn.fetchval(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
            )
        return {
            "status": "ok",
            "postgres_version": version_row.split()[1] if version_row else "unknown",
            "pgvector_version": pgvector_ver or "not installed",
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── SQLite ────────────────────────────────────────────────────────────────────


@contextmanager
def get_sqlite_conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Sync context manager yielding a SQLite connection with row_factory set."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
