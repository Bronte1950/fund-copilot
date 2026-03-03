"""Evaluation runner — execute the question set against the live pipeline.

Input:  data/eval/questions.jsonl
Output: data/eval/results/<timestamp>.jsonl  +  summary.json

Run via CLI:
    python -m src eval run
    python -m src eval run --questions data/eval/questions.jsonl
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from src.common.db import MANIFEST_DB_PATH
from src.common.logging import get_logger
from src.common.schemas import RetrievalRequest
from src.eval.metrics import (
    EvalResult,
    compute_grounding_ok,
    compute_hit_at_k,
    compute_refusal_correct,
    summarise,
)
from src.llm.client import close_client, generate
from src.llm.grounding import ground_response
from src.llm.prompts import assemble_prompt
from src.retrieval.service import retrieve

log = get_logger(__name__)

QUESTIONS_PATH = Path("data/eval/questions.jsonl")
RESULTS_DIR = Path("data/eval/results")


# ── Question loading ───────────────────────────────────────────────────────────


def load_questions(path: Path = QUESTIONS_PATH) -> list[dict]:
    questions = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


# ── Manifest ISIN → doc_id lookup ─────────────────────────────────────────────


def _isin_to_doc_id(isin: str) -> str | None:
    """Look up doc_id for an ISIN from the manifest. Case-insensitive."""
    try:
        conn = sqlite3.connect(str(MANIFEST_DB_PATH))
        row = conn.execute(
            "SELECT doc_id FROM documents WHERE UPPER(isin) = UPPER(?)",
            (isin,),
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def _isin_to_doc_ids_from_filename(isin: str) -> list[str]:
    """Fallback: find docs whose file_name contains the ISIN substring."""
    try:
        conn = sqlite3.connect(str(MANIFEST_DB_PATH))
        rows = conn.execute(
            "SELECT doc_id FROM documents WHERE LOWER(file_name) LIKE LOWER(?)",
            (f"%{isin.lower()}%",),
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def resolve_expected_doc_id(isin: str | None) -> str | None:
    if not isin:
        return None
    doc_id = _isin_to_doc_id(isin)
    if doc_id:
        return doc_id
    # Fallback: search filename
    ids = _isin_to_doc_ids_from_filename(isin)
    return ids[0] if ids else None


# ── Single question evaluation ─────────────────────────────────────────────────


async def _eval_question(q: dict, top_k: int = 10) -> EvalResult:
    result = EvalResult(
        question_id=q["question_id"],
        query=q["query"],
        category=q["category"],
        should_refuse=q["should_refuse"],
        expected_answer=q.get("expected_answer"),
        expected_isin=q.get("expected_isin"),
    )

    expected_doc_id = resolve_expected_doc_id(q.get("expected_isin"))

    try:
        # ── Retrieval ──────────────────────────────────────────────────────────
        t0 = time.perf_counter()
        retrieval_req = RetrievalRequest(query=q["query"], top_k=top_k, isin=q.get("expected_isin"))
        chunks = await retrieve(retrieval_req)
        result.retrieval_ms = (time.perf_counter() - t0) * 1000

        result.retrieved_doc_ids  = list(dict.fromkeys(c.doc_id for c in chunks))
        result.retrieved_chunk_ids = [c.chunk_id for c in chunks]
        result.hit_at_k = compute_hit_at_k(result.retrieved_doc_ids, expected_doc_id)

        # ── Generation ────────────────────────────────────────────────────────
        messages, chunks_used = assemble_prompt(q["query"], chunks)

        t0 = time.perf_counter()
        answer_text = await generate(messages)
        result.generation_ms = (time.perf_counter() - t0) * 1000

        response = ground_response(
            answer_text=answer_text,
            chunks_used=chunks_used,
            results=chunks,
            retrieval_time_ms=result.retrieval_ms,
            generation_time_ms=result.generation_ms,
            model="llama3.1:8b",
        )

        result.answer       = response.answer
        result.confidence   = response.confidence
        result.chunks_cited = response.chunks_cited
        result.chunks_used  = chunks_used
        result.grounding_ok = compute_grounding_ok(response.chunks_cited, chunks_used)
        result.refusal_correct = compute_refusal_correct(response.confidence, q["should_refuse"])

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        log.error("eval_question_error", question_id=q["question_id"], error=err_msg)
        result.error = err_msg

    log.info(
        "eval_question_done",
        qid=result.question_id,
        hit=result.hit_at_k,
        grounding=result.grounding_ok,
        refusal_ok=result.refusal_correct,
        confidence=result.confidence,
        retrieval_ms=round(result.retrieval_ms, 1),
        generation_ms=round(result.generation_ms, 1),
    )
    return result


# ── Full eval run ──────────────────────────────────────────────────────────────


async def run_eval(
    questions_path: Path = QUESTIONS_PATH,
    results_dir: Path = RESULTS_DIR,
    top_k: int = 10,
    on_question_start: Callable[[str], None] | None = None,
    on_question_done: Callable[[EvalResult], None] | None = None,
) -> tuple[list[EvalResult], dict]:
    """Run all questions sequentially and write results + summary.

    Returns (results, summary_metrics).
    """
    # Reset the shared httpx client before each run to clear any stale TCP
    # connections left over from previous requests or timed-out eval runs.
    await close_client()

    questions = load_questions(questions_path)
    log.info("eval_start", n_questions=len(questions), top_k=top_k)

    results: list[EvalResult] = []
    for i, q in enumerate(questions, 1):
        log.info("eval_progress", current=i, total=len(questions), qid=q["question_id"])
        if on_question_start:
            on_question_start(q["question_id"])

        # Hard wall-clock timeout per question.  asyncio.wait_for() cancels the
        # coroutine if Ollama enters a runaway generation loop or the event loop
        # stalls.  480s is well under the 600s httpx read timeout, so Ollama has
        # time to finish normally but we escape cleanly if something goes wrong.
        try:
            result = await asyncio.wait_for(_eval_question(q, top_k=top_k), timeout=480.0)
        except asyncio.TimeoutError:
            log.error("eval_question_wall_timeout", question_id=q["question_id"])
            # Force-close the Ollama client so any stale sockets are released
            # before the next question runs.
            await close_client()
            result = EvalResult(
                question_id=q["question_id"],
                query=q["query"],
                category=q["category"],
                should_refuse=q["should_refuse"],
                expected_answer=q.get("expected_answer"),
                expected_isin=q.get("expected_isin"),
                error="TimeoutError: exceeded 480s wall-clock limit",
            )

        results.append(result)
        if on_question_done:
            on_question_done(result)

    summary = summarise(results)

    # ── Write outputs ──────────────────────────────────────────────────────────
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    results_path = results_dir / f"{ts}.jsonl"
    with results_path.open("w") as f:
        for r in results:
            f.write(json.dumps(asdict(r)) + "\n")

    summary_path = results_dir / f"{ts}_summary.json"
    with summary_path.open("w") as f:
        json.dump({"timestamp": ts, "top_k": top_k, **summary}, f, indent=2)

    # Always overwrite the "latest" pointers for the API
    (results_dir / "latest.jsonl").write_text(results_path.read_text())
    (results_dir / "latest_summary.json").write_text(summary_path.read_text())

    log.info("eval_complete", **{k: v for k, v in summary.items() if not isinstance(v, dict)})
    return results, summary
