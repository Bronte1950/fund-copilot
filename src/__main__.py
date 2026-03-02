"""CLI entrypoint — `python -m src <command>`.

Usage:
    python -m src api [--port 8010] [--reload]
    python -m src ingest [--input data/raw_pdfs/]   # Phase 1
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fund-copilot",
        description="Fund Copilot — local RAG for UCITS fund documents",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── api ──────────────────────────────────────────────────────────────────
    api_parser = subparsers.add_parser("api", help="Start the FastAPI server")
    api_parser.add_argument("--port", type=int, default=8010)
    api_parser.add_argument("--host", default="0.0.0.0")
    api_parser.add_argument("--reload", action="store_true")

    # ── ingest (Phase 1) ─────────────────────────────────────────────────────
    ingest_parser = subparsers.add_parser("ingest", help="Run the ingest pipeline")
    ingest_parser.add_argument("--input", default="data/raw_pdfs/")
    ingest_parser.add_argument("--force", action="store_true", help="Re-index all docs")

    args = parser.parse_args()

    if args.command == "api":
        import uvicorn

        uvicorn.run(
            "src.api.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )

    elif args.command == "ingest":
        print("Ingest pipeline: Phase 1 (not yet implemented)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
