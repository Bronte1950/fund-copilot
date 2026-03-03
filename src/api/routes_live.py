"""Live market data routes — GET /funds/live, POST /funds/live/refresh.

Data is served from the fund_live_data SQLite cache (in manifest.sqlite).
Stale entries (older than YAHOO_CACHE_MAX_AGE_HOURS) are refreshed automatically
by GET /funds/live. POST /funds/live/refresh forces a refresh of all or specific ISINs.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from fastapi import APIRouter

from src.common.logging import get_logger
from src.common.schemas import LiveDataRefreshResult, LiveFundsResponse
from src.data_sources.yahoo_finance import (
    get_all_cached,
    get_all_manifest_isins,
    refresh_all,
)

log = get_logger(__name__)
router = APIRouter(prefix="/funds", tags=["live-data"])


@router.get("/live", summary="Return cached Yahoo Finance fund data")
async def get_live_funds() -> LiveFundsResponse:
    """Return the current cache of Yahoo Finance market data for all indexed funds.

    Data is served from the local SQLite cache — no live network call is made here.
    Use `POST /funds/live/refresh` to force a fetch from Yahoo Finance.

    The `cache_age_hours` field reports the age of the oldest cached entry.
    Entries are refreshed automatically when GET /funds/live/refresh is called
    or when the chat endpoint detects a market-data query.
    """
    rows = await asyncio.to_thread(get_all_cached)

    cache_age: float | None = None
    ok_rows = [r for r in rows if r.fetch_status == "ok" and r.fetched_at]
    if ok_rows:
        oldest = min(r.fetched_at for r in ok_rows)
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        cache_age = round(
            (datetime.now(timezone.utc) - oldest).total_seconds() / 3600, 2
        )

    log.info("live_funds_fetched", total=len(rows), cache_age_hours=cache_age)
    return LiveFundsResponse(funds=rows, cache_age_hours=cache_age, total=len(rows))


@router.post("/live/refresh", summary="Force-refresh Yahoo Finance data")
async def refresh_live_funds(isins: list[str] | None = None) -> LiveDataRefreshResult:
    """Fetch fresh data from Yahoo Finance for all (or specified) fund ISINs.

    - If `isins` is provided in the request body, only those ISINs are refreshed.
    - Otherwise, all ISINs found in the documents manifest are refreshed.

    Each ISIN is looked up via a 3-tier ticker resolution chain:
    1. `documents.ticker` column (from fund_sources.csv)
    2. Yahoo Finance search by ISIN
    3. Direct ISIN-as-ticker attempt

    ISINs where no ticker can be resolved are counted in `skipped`.
    Network errors are counted in `failed`. Both are non-fatal.
    """
    if not isins:
        isins = await asyncio.to_thread(get_all_manifest_isins)
        log.info("live_refresh_all", n_isins=len(isins))
    else:
        log.info("live_refresh_selective", n_isins=len(isins))

    t0 = time.perf_counter()
    result = await asyncio.to_thread(refresh_all, isins)
    result.duration_ms = round((time.perf_counter() - t0) * 1000, 1)

    log.info(
        "live_refresh_complete",
        refreshed=result.refreshed,
        skipped=result.skipped,
        failed=result.failed,
        duration_ms=result.duration_ms,
    )
    return result
