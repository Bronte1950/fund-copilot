"""Yahoo Finance cache layer — fetch and store live fund market data.

All external network calls are isolated here. The rest of the application
reads only from the fund_live_data SQLite table (co-located in manifest.sqlite).

Public API:
    init_live_data_table()              — create table on first use (called at startup)
    get_all_cached()                    — return all cached rows (GET /funds/live)
    get_live_data(isins)                — async; return cached rows, refresh stale ones
    refresh_all(isins)                  — bulk refresh (POST /funds/live/refresh)
    get_all_manifest_isins()            — list all ISINs from the documents table
"""

from __future__ import annotations

import asyncio
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

import yfinance as yf

from src.common.config import settings
from src.common.db import LIVE_DATA_DB_PATH, get_sqlite_conn
from src.common.logging import get_logger
from src.common.schemas import FundLiveData, LiveDataRefreshResult

log = get_logger(__name__)

# ── Table setup ───────────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS fund_live_data (
    isin                TEXT PRIMARY KEY,
    resolved_ticker     TEXT,
    fund_name           TEXT,
    currency            TEXT,
    price               REAL,
    price_change_pct    REAL,
    nav                 REAL,
    aum_millions        REAL,
    ytd_return_pct      REAL,
    one_year_return_pct REAL,
    expense_ratio_pct   REAL,
    dividend_yield_pct  REAL,
    yahoo_url           TEXT,
    fetched_at          TEXT NOT NULL,
    fetch_status        TEXT NOT NULL DEFAULT 'ok'
);
"""


def init_live_data_table() -> None:
    """Create the fund_live_data table if it doesn't exist. Call once at startup."""
    with get_sqlite_conn(LIVE_DATA_DB_PATH) as conn:
        conn.execute(_CREATE_TABLE_SQL)
    log.info("live_data_table_ready")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _safe_mul(val: Any, factor: float) -> float | None:
    """Multiply val by factor, return None if val is None or non-numeric."""
    if val is None:
        return None
    try:
        return round(float(val) * factor, 4)
    except (TypeError, ValueError):
        return None


def _safe_div(val: Any, divisor: float) -> float | None:
    """Divide val by divisor, return None if val is None or non-numeric."""
    if val is None or divisor == 0:
        return None
    try:
        return round(float(val) / divisor, 2)
    except (TypeError, ValueError):
        return None


def _is_stale(fetched_at_iso: str) -> bool:
    """Return True if the cached entry is older than yahoo_cache_max_age_hours."""
    try:
        fetched_at = datetime.fromisoformat(fetched_at_iso)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - fetched_at).total_seconds() / 3600
        return age_hours >= settings.yahoo_cache_max_age_hours
    except (ValueError, TypeError):
        return True  # malformed timestamp → treat as stale


def _row_to_model(row: sqlite3.Row) -> FundLiveData:
    """Convert a sqlite3.Row from fund_live_data to a FundLiveData model."""
    fetched_at = datetime.fromisoformat(row["fetched_at"])
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return FundLiveData(
        isin=row["isin"],
        resolved_ticker=row["resolved_ticker"],
        fund_name=row["fund_name"],
        currency=row["currency"],
        price=row["price"],
        price_change_pct=row["price_change_pct"],
        nav=row["nav"],
        aum_millions=row["aum_millions"],
        ytd_return_pct=row["ytd_return_pct"],
        one_year_return_pct=row["one_year_return_pct"],
        expense_ratio_pct=row["expense_ratio_pct"],
        dividend_yield_pct=row["dividend_yield_pct"],
        yahoo_url=row["yahoo_url"],
        fetched_at=fetched_at,
        fetch_status=row["fetch_status"],
    )


# ── Ticker resolution ─────────────────────────────────────────────────────────


def _resolve_ticker(isin: str, conn: sqlite3.Connection) -> str | None:
    """Find the Yahoo Finance ticker for an ISIN using a 3-tier resolution chain.

    Tier 1: documents.ticker column (populated from fund_sources.csv)
    Tier 2: yfinance search by ISIN — pick first ETF/MUTUALFUND result
    Tier 3: try ISIN directly as a yfinance ticker
    """
    # Tier 1 — manifest documents table
    row = conn.execute(
        "SELECT ticker FROM documents WHERE isin = ? AND ticker IS NOT NULL LIMIT 1",
        (isin,),
    ).fetchone()
    if row and row["ticker"]:
        log.debug("ticker_resolved_tier1", isin=isin, ticker=row["ticker"])
        return row["ticker"]

    # Tier 2 — yfinance search
    try:
        search_results = yf.Search(isin, max_results=5).quotes
        for result in search_results:
            quote_type = result.get("quoteType", "")
            symbol = result.get("symbol", "")
            if quote_type in ("ETF", "MUTUALFUND", "EQUITY") and symbol:
                log.debug("ticker_resolved_tier2", isin=isin, ticker=symbol)
                return symbol
    except Exception as exc:
        log.debug("ticker_search_failed", isin=isin, error=str(exc))

    # Tier 3 — try ISIN directly
    try:
        ticker_obj = yf.Ticker(isin)
        price = ticker_obj.fast_info.last_price
        if price is not None:
            log.debug("ticker_resolved_tier3", isin=isin, ticker=isin)
            return isin
    except Exception as exc:
        log.debug("ticker_direct_failed", isin=isin, error=str(exc))

    return None


# ── Yahoo Finance fetch ───────────────────────────────────────────────────────


def _fetch_from_yahoo(ticker: str, isin: str) -> FundLiveData:
    """Fetch live data for a single ticker from Yahoo Finance.

    Runs synchronously — call inside asyncio.to_thread() from async context.
    """
    ticker_obj = yf.Ticker(ticker)
    info: dict = {}
    try:
        info = ticker_obj.info or {}
    except Exception as exc:
        log.warning("yfinance_info_failed", ticker=ticker, error=str(exc))

    fast = ticker_obj.fast_info

    price = None
    try:
        price = fast.last_price
    except Exception:
        pass
    if price is None:
        price = info.get("regularMarketPrice") or info.get("currentPrice")

    return FundLiveData(
        isin=isin,
        resolved_ticker=ticker,
        fund_name=info.get("shortName") or info.get("longName"),
        currency=info.get("currency") or getattr(fast, "currency", None),
        price=price,
        price_change_pct=info.get("regularMarketChangePercent"),
        nav=info.get("navPrice"),
        aum_millions=_safe_div(info.get("totalAssets"), 1_000_000),
        ytd_return_pct=_safe_mul(info.get("ytdReturn"), 100),
        one_year_return_pct=_safe_mul(info.get("52WeekChange"), 100),
        expense_ratio_pct=_safe_mul(info.get("annualReportExpenseRatio"), 100),
        dividend_yield_pct=_safe_mul(info.get("dividendYield"), 100),
        yahoo_url=f"https://finance.yahoo.com/quote/{ticker}",
        fetched_at=datetime.now(timezone.utc),
        fetch_status="ok",
    )


# ── Upsert ────────────────────────────────────────────────────────────────────

_UPSERT_SQL = """
INSERT INTO fund_live_data (
    isin, resolved_ticker, fund_name, currency, price, price_change_pct,
    nav, aum_millions, ytd_return_pct, one_year_return_pct,
    expense_ratio_pct, dividend_yield_pct, yahoo_url, fetched_at, fetch_status
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(isin) DO UPDATE SET
    resolved_ticker     = excluded.resolved_ticker,
    fund_name           = excluded.fund_name,
    currency            = excluded.currency,
    price               = excluded.price,
    price_change_pct    = excluded.price_change_pct,
    nav                 = excluded.nav,
    aum_millions        = excluded.aum_millions,
    ytd_return_pct      = excluded.ytd_return_pct,
    one_year_return_pct = excluded.one_year_return_pct,
    expense_ratio_pct   = excluded.expense_ratio_pct,
    dividend_yield_pct  = excluded.dividend_yield_pct,
    yahoo_url           = excluded.yahoo_url,
    fetched_at          = excluded.fetched_at,
    fetch_status        = excluded.fetch_status
"""


def _upsert(conn: sqlite3.Connection, data: FundLiveData) -> None:
    conn.execute(
        _UPSERT_SQL,
        (
            data.isin,
            data.resolved_ticker,
            data.fund_name,
            data.currency,
            data.price,
            data.price_change_pct,
            data.nav,
            data.aum_millions,
            data.ytd_return_pct,
            data.one_year_return_pct,
            data.expense_ratio_pct,
            data.dividend_yield_pct,
            data.yahoo_url,
            data.fetched_at.isoformat(),
            data.fetch_status,
        ),
    )


# ── Refresh one ISIN ──────────────────────────────────────────────────────────


def _refresh_isin_sync(isin: str, conn: sqlite3.Connection) -> FundLiveData | None:
    """Resolve ticker and fetch fresh data for one ISIN. Sync — run in threadpool.

    Returns FundLiveData on success, None if ticker could not be resolved or
    fetch failed (in which case a placeholder row with the error status is upserted).
    """
    ticker = _resolve_ticker(isin, conn)
    if not ticker:
        placeholder = FundLiveData(
            isin=isin,
            fetched_at=datetime.now(timezone.utc),
            fetch_status="no_ticker",
        )
        _upsert(conn, placeholder)
        log.info("live_data_no_ticker", isin=isin)
        return None

    try:
        data = _fetch_from_yahoo(ticker, isin)
        _upsert(conn, data)
        log.info("live_data_refreshed", isin=isin, ticker=ticker, price=data.price)
        return data
    except Exception as exc:
        placeholder = FundLiveData(
            isin=isin,
            resolved_ticker=ticker,
            fetched_at=datetime.now(timezone.utc),
            fetch_status="fetch_error",
        )
        _upsert(conn, placeholder)
        log.warning("live_data_fetch_error", isin=isin, ticker=ticker, error=str(exc))
        return None


# ── Public API ────────────────────────────────────────────────────────────────


def get_all_cached() -> list[FundLiveData]:
    """Return all rows from fund_live_data, ordered by ISIN. Sync."""
    with get_sqlite_conn(LIVE_DATA_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT * FROM fund_live_data ORDER BY isin"
        ).fetchall()
    return [_row_to_model(r) for r in rows]


def get_all_manifest_isins() -> list[str]:
    """Return all distinct ISINs from the documents table. Sync."""
    with get_sqlite_conn(LIVE_DATA_DB_PATH) as conn:
        rows = conn.execute(
            "SELECT DISTINCT isin FROM documents WHERE isin IS NOT NULL"
        ).fetchall()
    return [r["isin"] for r in rows]


def _get_live_data_sync(isins: list[str]) -> list[FundLiveData]:
    """Return live data for the given ISINs, refreshing stale entries. Sync."""
    results: list[FundLiveData] = []
    with get_sqlite_conn(LIVE_DATA_DB_PATH) as conn:
        for isin in isins:
            row = conn.execute(
                "SELECT * FROM fund_live_data WHERE isin = ?", (isin,)
            ).fetchone()

            if row is None or _is_stale(row["fetched_at"]):
                data = _refresh_isin_sync(isin, conn)
                if data and data.fetch_status == "ok":
                    results.append(data)
            elif row["fetch_status"] == "ok":
                results.append(_row_to_model(row))

    return results


async def get_live_data(isins: list[str]) -> list[FundLiveData]:
    """Async entry point: return live data, refreshing stale entries if needed."""
    return await asyncio.to_thread(_get_live_data_sync, isins)


def refresh_all(isins: list[str]) -> LiveDataRefreshResult:
    """Bulk-refresh Yahoo Finance data for the given ISINs. Sync.

    Sleeps 0.1 s between calls to be polite to Yahoo Finance rate limits.
    Respects settings.yahoo_max_live_funds cap.
    """
    isins = isins[: settings.yahoo_max_live_funds * 10]  # generous cap for refresh
    refreshed, skipped, failed = 0, 0, 0
    refreshed_isins: list[str] = []

    with get_sqlite_conn(LIVE_DATA_DB_PATH) as conn:
        for isin in isins:
            data = _refresh_isin_sync(isin, conn)
            if data is None:
                # Distinguish no_ticker vs fetch_error by reading back status
                row = conn.execute(
                    "SELECT fetch_status FROM fund_live_data WHERE isin = ?", (isin,)
                ).fetchone()
                status = row["fetch_status"] if row else "no_ticker"
                if status == "no_ticker":
                    skipped += 1
                else:
                    failed += 1
            else:
                refreshed += 1
                refreshed_isins.append(isin)
            time.sleep(0.1)

    return LiveDataRefreshResult(
        refreshed=refreshed,
        skipped=skipped,
        failed=failed,
        duration_ms=0.0,  # caller sets this
        isins_refreshed=refreshed_isins,
    )
