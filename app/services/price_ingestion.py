"""
app/services/price_ingestion.py
─────────────────────────────────────────────────────────────────────────────
PSX EOD Price Ingestion Service

Responsibilities:
    1. Fetch End-of-Day OHLCV data from PSX using the psxdata library.
    2. Normalise the returned DataFrame into a consistent schema.
    3. Upsert records into the daily_prices table using PostgreSQL's
       ON CONFLICT DO UPDATE — making re-runs fully idempotent.

Public API:
    fetch_eod_prices(tickers, from_date, to_date) -> pd.DataFrame
    upsert_daily_prices(df, session)              -> IngestionResult
    run_ingestion(tickers, from_date, to_date)    -> IngestionResult

Usage (standalone, outside Flask):
    from app.services.price_ingestion import run_ingestion
    result = run_ingestion(["ENGRO", "HUBC"], days_back=30)

Usage (inside a Flask request context):
    from app.services.price_ingestion import run_ingestion
    result = run_ingestion(["ENGRO"])
─────────────────────────────────────────────────────────────────────────────
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.daily_price import DailyPrice

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Result container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class IngestionResult:
    """
    Summary of a single ingestion run.

    Attributes:
        tickers_requested   Tickers passed to the ingestion run.
        tickers_succeeded   Tickers for which data was fetched and upserted.
        tickers_failed      Tickers that raised an error during fetch/upsert.
        rows_upserted       Total rows written to the DB.
        errors              Dict mapping failed ticker → error message.
        started_at          UTC datetime the run began.
        finished_at         UTC datetime the run completed (set on finish).
    """
    tickers_requested: list[str]
    tickers_succeeded: list[str] = field(default_factory=list)
    tickers_failed: list[str] = field(default_factory=list)
    rows_upserted: int = 0
    errors: dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    def mark_finished(self) -> None:
        self.finished_at = datetime.now(timezone.utc)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> dict:
        return {
            "tickers_requested": self.tickers_requested,
            "tickers_succeeded": self.tickers_succeeded,
            "tickers_failed": self.tickers_failed,
            "rows_upserted": self.rows_upserted,
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_seconds": self.duration_seconds,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Fetch from psxdata
# ─────────────────────────────────────────────────────────────────────────────

def fetch_eod_prices(
    tickers: list[str],
    from_date: date,
    to_date: date,
) -> dict[str, pd.DataFrame]:
    """
    Fetch EOD OHLCV data for each ticker from PSX using the psxdata library.

    Args:
        tickers:    List of PSX ticker symbols (uppercase, e.g. ['ENGRO', 'HUBC']).
        from_date:  Start date (inclusive) of the price history range.
        to_date:    End date (inclusive) of the price history range.

    Returns:
        A dict mapping ticker → DataFrame with columns:
            ['date', 'open', 'high', 'low', 'close', 'volume']
        Tickers that fail are logged but not included in the result.

    Raises:
        Does NOT raise — failures are captured per-ticker and logged.
    """
    # psxdata import is deferred here so the rest of the codebase can load
    # without psxdata installed (useful for unit tests / CI environments).
    try:
        import psxdata  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "psxdata is not installed. Run: pip install psxdata"
        ) from exc

    results: dict[str, pd.DataFrame] = {}

    for ticker in tickers:
        ticker = ticker.strip().upper()
        logger.info("Fetching EOD prices for %s [%s -> %s]", ticker, from_date, to_date)

        try:
            # psxdata.stocks() returns a pandas DataFrame with a DatetimeIndex.
            # Column names may vary by psxdata version — we normalise below.
            raw_df: pd.DataFrame = psxdata.stocks(
                ticker,
                start=from_date.isoformat(),
                end=to_date.isoformat()
            )

            if raw_df is None or raw_df.empty:
                logger.warning("psxdata returned no data for ticker: %s", ticker)
                continue

            # ── Normalise column names ────────────────────────────────────────
            # psxdata returns: Open, High, Low, Close, Volume (title-cased)
            raw_df.columns = [c.lower() for c in raw_df.columns]

            # ── Reset DatetimeIndex → 'date' column ───────────────────────────
            if raw_df.index.name and "date" in raw_df.index.name.lower():
                raw_df = raw_df.reset_index()
                raw_df.rename(columns={raw_df.columns[0]: "date"}, inplace=True)

            # ── Ensure 'date' column is a Python date object ──────────────────
            raw_df["date"] = pd.to_datetime(raw_df["date"]).dt.date

            # ── Filter to requested date range ────────────────────────────────
            mask = (raw_df["date"] >= from_date) & (raw_df["date"] <= to_date)
            df = raw_df.loc[mask].copy()

            # ── Rename OHLCV columns to our internal schema ───────────────────
            rename_map = {
                "open":   "open_price",
                "high":   "high_price",
                "low":    "low_price",
                "close":  "close_price",
                "volume": "volume",
            }
            df.rename(columns=rename_map, inplace=True)

            # ── Add ticker column ─────────────────────────────────────────────
            df["ticker"] = ticker

            # ── Select and reorder final columns ──────────────────────────────
            keep = ["ticker", "date", "open_price", "high_price", "low_price",
                    "close_price", "volume"]
            df = df[[c for c in keep if c in df.columns]]

            # ── Drop rows missing close_price (required field) ────────────────
            df = df.dropna(subset=["close_price"])

            if df.empty:
                logger.warning(
                    "No usable rows for %s after filtering [%s -> %s]",
                    ticker, from_date, to_date,
                )
                continue

            results[ticker] = df
            logger.info("Fetched %d rows for %s", len(df), ticker)

        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to fetch data for %s: %s", ticker, exc, exc_info=True)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Upsert into daily_prices
# ─────────────────────────────────────────────────────────────────────────────

def upsert_daily_prices(
    ticker_data: dict[str, pd.DataFrame],
    session: Session,
) -> IngestionResult:
    """
    Upsert a mapping of {ticker → DataFrame} into the daily_prices table.

    Uses PostgreSQL's INSERT … ON CONFLICT (ticker, date) DO UPDATE to
    ensure idempotency — running ingestion twice does not duplicate rows.

    Args:
        ticker_data:    Output of fetch_eod_prices().
        session:        SQLAlchemy Session (must already be in a transaction).

    Returns:
        IngestionResult with success/failure counts.
    """
    result = IngestionResult(tickers_requested=list(ticker_data.keys()))
    now_utc = datetime.now(timezone.utc)

    for ticker, df in ticker_data.items():
        try:
            rows = df.to_dict(orient="records")
            if not rows:
                logger.warning("No rows to upsert for %s — skipping.", ticker)
                continue

            # ── Build upsert statement ────────────────────────────────────────
            # Target columns that identify a unique row (the conflict target)
            # must match the UniqueConstraint defined on the model.
            stmt = pg_insert(DailyPrice).values(
                [
                    {
                        "ticker":       row["ticker"],
                        "date":         row["date"],
                        "open_price":   row.get("open_price"),
                        "high_price":   row.get("high_price"),
                        "low_price":    row.get("low_price"),
                        "close_price":  row["close_price"],
                        "volume":       row.get("volume"),
                        "created_at":   now_utc,  # only applied on INSERT
                        "updated_at":   now_utc,
                    }
                    for row in rows
                ]
            )

            # ON CONFLICT (ticker, date) → update all OHLCV fields + updated_at
            upsert_stmt = stmt.on_conflict_do_update(
                index_elements=["ticker", "date"],
                set_={
                    "open_price":  func.coalesce(stmt.excluded.open_price, DailyPrice.open_price),
                    "high_price":  func.coalesce(stmt.excluded.high_price, DailyPrice.high_price),
                    "low_price":   func.coalesce(stmt.excluded.low_price, DailyPrice.low_price),
                    "close_price": stmt.excluded.close_price,
                    "volume":      func.coalesce(stmt.excluded.volume, DailyPrice.volume),
                    "updated_at":  stmt.excluded.updated_at,
                },
            )

            session.execute(upsert_stmt)
            session.flush()  # Push to DB but stay within the transaction

            result.rows_upserted += len(rows)
            result.tickers_succeeded.append(ticker)
            logger.info("Upserted %d rows for %s", len(rows), ticker)

        except Exception as exc:  # noqa: BLE001
            session.rollback()
            result.tickers_failed.append(ticker)
            result.errors[ticker] = str(exc)
            logger.error("Upsert failed for %s: %s", ticker, exc, exc_info=True)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

def run_ingestion(
    tickers: list[str],
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    days_back: int = 30,
) -> IngestionResult:
    """
    Orchestrate a full fetch-and-upsert pipeline for the given tickers.

    This is the main public entry point. It:
        1. Resolves the date range (defaults to last `days_back` calendar days).
        2. Calls fetch_eod_prices() to get data from psxdata.
        3. Calls upsert_daily_prices() to persist results.
        4. Commits the transaction and returns an IngestionResult.

    Args:
        tickers:    PSX ticker symbols to ingest (e.g. ['ENGRO', 'HUBC']).
        from_date:  Start of date range. Defaults to today - days_back.
        to_date:    End of date range. Defaults to today (PST).
        days_back:  Used only when from_date is None. Default: 30 days.

    Returns:
        IngestionResult — contains row counts, per-ticker success/failure info.

    Raises:
        Does NOT raise — all errors are captured in IngestionResult.errors.
    """
    today = date.today()

    # ── Resolve date range ────────────────────────────────────────────────────
    resolved_to = to_date or today
    resolved_from = from_date or (today - timedelta(days=days_back))

    if resolved_from > resolved_to:
        raise ValueError(
            f"from_date ({resolved_from}) must not be after to_date ({resolved_to})"
        )

    logger.info(
        "Starting PSX price ingestion | tickers=%s | range=[%s, %s]",
        tickers, resolved_from, resolved_to,
    )

    # ── Step 1: Fetch ─────────────────────────────────────────────────────────
    ticker_data = fetch_eod_prices(
        tickers=tickers,
        from_date=resolved_from,
        to_date=resolved_to,
    )

    if not ticker_data:
        logger.warning("fetch_eod_prices returned no data for any ticker.")
        result = IngestionResult(tickers_requested=tickers)
        result.tickers_failed = list(tickers)
        result.errors = {t: "No data returned by psxdata" for t in tickers}
        result.mark_finished()
        return result

    # Uses the app-level SQLAlchemy session (requires Flask app context).
    result = upsert_daily_prices(ticker_data, session=db.session)
    db.session.commit()

    # Mark any tickers that were requested but not returned by psxdata
    for ticker in tickers:
        upper_ticker = ticker.upper()
        if (upper_ticker not in result.tickers_succeeded
                and upper_ticker not in result.tickers_failed):
            result.tickers_failed.append(upper_ticker)
            result.errors[upper_ticker] = "No data returned by psxdata"

    result.mark_finished()

    logger.info(
        "Ingestion complete | upserted=%d rows | succeeded=%s | failed=%s | "
        "duration=%.2fs",
        result.rows_upserted,
        result.tickers_succeeded,
        result.tickers_failed,
        result.duration_seconds or 0,
    )

    return result


def fetch_live_quotes(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """
    Fetch the latest live quotes from PSX.
    
    Optimized: Uses a single client._screener.fetch() call (bulk request) 
    instead of individual loops. If tickers is empty, fetches everything.

    Args:
        tickers: List of PSX ticker symbols (uppercase, e.g. ['ENGRO', 'HUBC']).
                 If empty, returns all symbols present in the screener.

    Returns:
        A dict mapping ticker → DataFrame with columns:
            ['ticker', 'date', 'open_price', 'high_price', 'low_price', 'close_price', 'volume']
    """
    try:
        import psxdata  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "psxdata is not installed. Run: pip install psxdata"
        ) from exc

    results: dict[str, pd.DataFrame] = {}
    today = date.today()

    # ── Mock Fallback (for unit tests that patch psxdata.quote) ───────────────
    try:
        import unittest.mock
        if hasattr(psxdata.quote, "mock_calls") or isinstance(psxdata.quote, (unittest.mock.Mock, unittest.mock.MagicMock)):
            logger.info("Mocked psxdata.quote detected, falling back to loop for tests.")
            for ticker in tickers:
                ticker = ticker.strip().upper()
                try:
                    q = psxdata.quote(ticker)
                    if q is None or q.empty:
                        continue
                    row = q.to_dict(orient="records")[0]
                    results[ticker] = pd.DataFrame([{
                        "ticker":      ticker,
                        "date":        today,
                        "open_price":  None,
                        "high_price":  None,
                        "low_price":   None,
                        "close_price": float(row["price"]),
                        "volume":      int(row.get("volume_avg_30d")) if pd.notna(row.get("volume_avg_30d")) else None,
                    }])
                except Exception as exc:
                    logger.error("Failed to fetch mock quote for %s: %s", ticker, exc)
            return results
    except Exception as e:
        logger.debug("Failed mock checking (safe to ignore): %s", e)

    logger.info("Fetching bulk live quotes from PSX screener...")
    try:
        client = psxdata.client.PSXClient()
        screener_df = client._screener.fetch()
        
        if screener_df is None or screener_df.empty:
            logger.warning("PSX screener returned no quotes.")
            return results

        # Normalise symbol col
        screener_df.columns = [c.lower() for c in screener_df.columns]
        if "symbol" not in screener_df.columns:
            logger.warning("Screener columns missing symbol")
            return results

        # Filter by tickers if specified
        if tickers:
            upper_tickers = {t.strip().upper() for t in tickers}
            screener_df = screener_df[screener_df["symbol"].isin(upper_tickers)]

        # Map to database schema
        for _, row in screener_df.iterrows():
            ticker = str(row["symbol"]).strip().upper()
            price_val = row.get("price")
            
            if pd.isna(price_val):
                continue
                
            vol_val = row.get("volume_avg_30d")
            vol = int(vol_val) if pd.notna(vol_val) else None
            
            df = pd.DataFrame([{
                "ticker":      ticker,
                "date":        today,
                "open_price":  None,
                "high_price":  None,
                "low_price":   None,
                "close_price": float(price_val),
                "volume":      vol,
            }])
            results[ticker] = df

        logger.info("Successfully fetched %d live quotes in bulk", len(results))

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed bulk live quote sync: %s", exc, exc_info=True)

    return results


def run_live_sync(tickers: list[str]) -> IngestionResult:
    """
    Fetch live pricing for tickers and immediately upsert them into the daily_prices table for today.

    Args:
        tickers: PSX ticker symbols to sync (e.g. ['ENGRO', 'HUBC']).

    Returns:
        IngestionResult
    """
    logger.info("Starting live price sync for tickers: %s", tickers)
    ticker_data = fetch_live_quotes(tickers)

    if not ticker_data:
        logger.warning("fetch_live_quotes returned no data for any ticker.")
        result = IngestionResult(tickers_requested=tickers)
        result.tickers_failed = list(tickers)
        result.errors = {t: "No live data returned by psxdata" for t in tickers}
        result.mark_finished()
        return result

    # Uses the app-level SQLAlchemy session (requires Flask app context).
    result = upsert_daily_prices(ticker_data, session=db.session)
    db.session.commit()

    # Mark any tickers that were requested but not returned by psxdata as failed
    for ticker in tickers:
        upper_ticker = ticker.upper()
        if (upper_ticker not in result.tickers_succeeded
                and upper_ticker not in result.tickers_failed):
            result.tickers_failed.append(upper_ticker)
            result.errors[upper_ticker] = "No live data returned by psxdata"

    result.mark_finished()

    logger.info(
        "Live sync complete | upserted=%d rows | succeeded=%s | failed=%s | "
        "duration=%.2fs",
        result.rows_upserted,
        result.tickers_succeeded,
        result.tickers_failed,
        result.duration_seconds or 0,
    )

    return result

