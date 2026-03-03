"""Evaluation API routes.

GET  /eval/questions         — list questions from the eval set
POST /eval/run               — trigger a full eval run (async background task)
GET  /eval/status            — poll current run status
GET  /eval/progress          — live per-question progress (partial results)
GET  /eval/results/latest    — latest summary + per-question results
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.common.logging import get_logger
from src.eval.runner import QUESTIONS_PATH, RESULTS_DIR, load_questions, run_eval

log = get_logger(__name__)

router = APIRouter(prefix="/eval", tags=["eval"])

# ── In-memory run state ────────────────────────────────────────────────────────

_run_state: dict = {
    "status": "idle",          # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "error": None,
    "n_questions": 0,
    "n_complete": 0,
    "current_qid": None,       # question currently being evaluated
    "current_started_at": None,# ISO timestamp when current question started
}

# Partial results accumulated during a run (cleared on each new run)
_partial_results: list[dict] = []

_run_lock = asyncio.Lock()


# ── Callbacks for runner ───────────────────────────────────────────────────────


def _on_question_start(qid: str) -> None:
    _run_state["current_qid"] = qid
    _run_state["current_started_at"] = datetime.now(timezone.utc).isoformat()


def _on_question_done(result) -> None:
    _run_state["n_complete"] += 1
    _run_state["current_qid"] = None
    _run_state["current_started_at"] = None
    _partial_results.append(asdict(result))


# ── Background eval task ───────────────────────────────────────────────────────


async def _do_run(top_k: int) -> None:
    global _run_state, _partial_results
    try:
        questions = load_questions(QUESTIONS_PATH)
        _run_state["n_questions"] = len(questions)
        _run_state["n_complete"] = 0
        _partial_results = []

        _, summary = await run_eval(
            top_k=top_k,
            on_question_start=_on_question_start,
            on_question_done=_on_question_done,
        )

        _run_state["status"] = "done"
        _run_state["finished_at"] = datetime.now(timezone.utc).isoformat()
        _run_state["error"] = None
        log.info("eval_api_run_complete", summary=summary)
    except Exception as exc:
        log.error("eval_api_run_error", error=str(exc))
        _run_state["status"] = "error"
        _run_state["error"] = str(exc)


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get("/questions")
def get_questions():
    """Return the current eval question set."""
    if not QUESTIONS_PATH.exists():
        raise HTTPException(status_code=404, detail="questions.jsonl not found")
    return {"questions": load_questions(QUESTIONS_PATH)}


@router.post("/run")
async def trigger_run(background_tasks: BackgroundTasks, top_k: int = 10):
    """Start an eval run in the background. Returns 409 if already running."""
    async with _run_lock:
        if _run_state["status"] == "running":
            raise HTTPException(status_code=409, detail="Eval run already in progress")

        now = datetime.now(timezone.utc).isoformat()
        _run_state.update({
            "status": "running",
            "started_at": now,
            "finished_at": None,
            "error": None,
            "n_complete": 0,
            "current_qid": None,
            "current_started_at": None,
        })

    background_tasks.add_task(_do_run, top_k)
    return {"message": "Eval run started", "top_k": top_k}


@router.get("/status")
def get_status():
    """Poll the current run status."""
    return _run_state


@router.get("/progress")
def get_progress():
    """Live progress: run state + partial results so far."""
    return {**_run_state, "partial_results": _partial_results}


@router.get("/results")
def list_results():
    """List all past eval run summaries, newest first."""
    if not RESULTS_DIR.exists():
        return {"runs": []}
    runs = []
    for path in sorted(RESULTS_DIR.glob("*_summary.json"), reverse=True):
        if path.name == "latest_summary.json":
            continue
        try:
            runs.append(json.loads(path.read_text()))
        except Exception:
            continue
    return {"runs": runs}


@router.get("/results/latest")
def get_latest_results():
    """Return the latest summary and per-question results."""
    summary_path = RESULTS_DIR / "latest_summary.json"
    results_path = RESULTS_DIR / "latest.jsonl"

    if not summary_path.exists():
        raise HTTPException(status_code=404, detail="No eval results found. Run an eval first.")

    summary = json.loads(summary_path.read_text())

    results = []
    if results_path.exists():
        for line in results_path.read_text().splitlines():
            line = line.strip()
            if line:
                results.append(json.loads(line))

    return {"summary": summary, "results": results}


@router.get("/results/{timestamp}")
def get_result_by_timestamp(timestamp: str):
    """Return per-question results for a specific past run."""
    results_path = RESULTS_DIR / f"{timestamp}.jsonl"
    if not results_path.exists():
        raise HTTPException(status_code=404, detail=f"Results for {timestamp} not found")
    results = []
    for line in results_path.read_text().splitlines():
        line = line.strip()
        if line:
            results.append(json.loads(line))
    return {"results": results}
