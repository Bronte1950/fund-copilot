"""CLI entrypoint — `python -m src <command>`.

Usage:
    python -m src api [--port 8010] [--reload]
    python -m src ingest inventory [--force]
    python -m src ingest run [--force]              # full pipeline (Phase 1)
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

    # ── ingest ───────────────────────────────────────────────────────────────
    ingest_parser = subparsers.add_parser("ingest", help="Ingest pipeline commands")
    ingest_sub = ingest_parser.add_subparsers(dest="ingest_command", required=True)

    inv_parser = ingest_sub.add_parser("inventory", help="Scan raw_pdfs/ → manifest.sqlite")
    inv_parser.add_argument("--input", default="data/raw_pdfs/")
    inv_parser.add_argument("--force", action="store_true", help="Re-process all docs")

    ext_parser = ingest_sub.add_parser("extract", help="Extract text from PDFs → data/extracted/")
    ext_parser.add_argument("--force", action="store_true", help="Re-extract all docs")

    clean_parser = ingest_sub.add_parser("clean", help="Remove boilerplate from extracted JSONL")
    clean_parser.add_argument("--force", action="store_true", help="Re-clean all docs")

    chunk_parser = ingest_sub.add_parser("chunk", help="Split cleaned text into token chunks")
    chunk_parser.add_argument("--force", action="store_true", help="Re-chunk all docs")

    embed_parser = ingest_sub.add_parser("embed", help="Embed chunks and upsert into pgvector")
    embed_parser.add_argument("--force", action="store_true", help="Re-index all docs")

    keyword_parser = ingest_sub.add_parser("keyword", help="Index chunks into SQLite FTS5")
    keyword_parser.add_argument("--force", action="store_true", help="Re-index all docs")

    run_parser = ingest_sub.add_parser("run", help="Run full ingest pipeline (Phase 1)")
    run_parser.add_argument("--input", default="data/raw_pdfs/")
    run_parser.add_argument("--force", action="store_true")

    # ── eval ─────────────────────────────────────────────────────────────────
    eval_parser = subparsers.add_parser("eval", help="Evaluation commands")
    eval_sub = eval_parser.add_subparsers(dest="eval_command", required=True)

    eval_run_parser = eval_sub.add_parser("run", help="Run eval question set against live pipeline")
    eval_run_parser.add_argument(
        "--questions", default="data/eval/questions.jsonl",
        help="Path to questions JSONL (default: data/eval/questions.jsonl)"
    )
    eval_run_parser.add_argument("--top-k", type=int, default=10)

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
        from pathlib import Path
        from src.common.logging import setup_logging
        setup_logging(log_format="console")

        if args.ingest_command == "inventory":
            from src.ingest.inventory import run
            docs = run(raw_pdfs_dir=Path(args.input), force=args.force)
            print(f"\nDone — {len(docs)} documents in manifest.")

        elif args.ingest_command == "extract":
            from src.ingest.extract import run
            counts = run(force=args.force)
            print(f"\nDone — {counts}")

        elif args.ingest_command == "clean":
            from src.ingest.clean import run
            counts = run(force=args.force)
            print(f"\nDone — {counts}")

        elif args.ingest_command == "chunk":
            from src.ingest.chunk import run
            counts = run(force=args.force)
            print(f"\nDone — {counts}")

        elif args.ingest_command == "embed":
            from src.ingest.index_vector import run
            counts = run(force=args.force)
            print(f"\nDone — {counts}")

        elif args.ingest_command == "keyword":
            from src.ingest.index_keyword import run
            counts = run(force=args.force)
            print(f"\nDone — {counts}")

        elif args.ingest_command == "run":
            print("Full pipeline: Phase 1 (not yet implemented)", file=sys.stderr)
            sys.exit(1)

    elif args.command == "eval":
        import asyncio
        from pathlib import Path
        from src.common.logging import setup_logging
        setup_logging(log_format="console")

        if args.eval_command == "run":
            from src.eval.runner import run_eval
            results, summary = asyncio.run(
                run_eval(
                    questions_path=Path(args.questions),
                    top_k=args.top_k,
                )
            )
            print(f"\n{'─'*50}")
            print(f"  Questions : {summary['n_questions']}")
            print(f"  Errors    : {summary['n_errors']}")
            print(f"  Hit@{args.top_k}     : {summary.get('hit_at_k', 'N/A')}")
            print(f"  Grounding : {summary.get('grounding_rate', 'N/A')}")
            print(f"  Refusals  : {summary.get('refusal_accuracy', 'N/A')}")
            print(f"  Avg retri.: {summary.get('avg_retrieval_ms', 0):.0f}ms")
            print(f"  Avg gen.  : {summary.get('avg_generation_ms', 0):.0f}ms")
            print(f"{'─'*50}")
            print(f"  Results written to data/eval/results/")


if __name__ == "__main__":
    main()
