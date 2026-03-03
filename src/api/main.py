"""FastAPI application factory.

Start with:
    uvicorn src.api.main:app --port 8010 --reload
Or via CLI:
    python -m src api --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes_admin import router as admin_router
from src.api.routes_chat import router as chat_router
from src.api.routes_eval import router as eval_router
from src.api.routes_retrieval import router as retrieval_router
from src.common.config import settings
from src.common.logging import get_logger, setup_logging
from src.llm.client import close_client

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    log.info("fund_copilot_api_starting", version="0.1.0", port=settings.api_port)
    yield
    await close_client()
    log.info("fund_copilot_api_stopping")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Fund Copilot API",
        description=(
            "Local-first RAG system for UK/Ireland UCITS fund documents. "
            "Answers questions with mandatory citations — refuses when evidence is missing."
        ),
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:5174",  # Vite dev server (alt port)
            "http://localhost:4173",  # Vite preview
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(admin_router)
    app.include_router(retrieval_router)
    app.include_router(chat_router)
    app.include_router(eval_router)

    return app


app = create_app()
