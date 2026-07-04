"""
app/models/daily_price.py
─────────────────────────────────────────────────────────────────────────────
DailyPrice model — caches End-of-Day (EOD) OHLCV data fetched from the PSX
via the psxdata library.

Design decisions:
    - UniqueConstraint on (ticker, date) enables true upsert semantics:
      re-running ingestion is idempotent (it updates, never duplicates).
    - Descending index on (ticker, date DESC) makes "latest price" queries
      O(log n) regardless of table size.
    - OHLCV values use Numeric(18,4) to avoid IEEE 754 float rounding.
─────────────────────────────────────────────────────────────────────────────
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Index, UniqueConstraint

from app.extensions import db


class DailyPrice(db.Model):
    """
    Cached End-of-Day OHLCV price record for a single PSX ticker on a single date.

    Ingested by app/services/price_ingestion.py using an upsert strategy
    (INSERT … ON CONFLICT DO UPDATE) so the table stays current without
    duplicating rows.
    """

    __tablename__ = "daily_prices"

    # ── Table-level constraints and indexes ───────────────────────────────────
    __table_args__ = (
        # Core upsert key: one row per (ticker, date) pair.
        UniqueConstraint("ticker", "date", name="uq_daily_prices_ticker_date"),
        # Descending composite index: blazing-fast "latest N prices for ticker X" queries.
        Index("ix_daily_prices_ticker_date_desc", "ticker", db.text("date DESC")),
    )

    # ── Primary Key ───────────────────────────────────────────────────────────
    id: db.Mapped[str] = db.mapped_column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key",
    )

    # ── Ticker ────────────────────────────────────────────────────────────────
    ticker: db.Mapped[str] = db.mapped_column(
        db.String(10),
        nullable=False,
        comment="PSX stock ticker symbol (uppercase, e.g. 'ENGRO')",
    )

    # ── Trading Date ──────────────────────────────────────────────────────────
    # Stored as a DATE (no time component) since PSX is a single-session exchange.
    date: db.Mapped[date] = db.mapped_column(
        db.Date,
        nullable=False,
        comment="Trading session date (PST, no time component)",
    )

    # ── OHLCV Data ────────────────────────────────────────────────────────────
    open_price: db.Mapped[float | None] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=True,
        comment="Opening price in PKR",
    )

    high_price: db.Mapped[float | None] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=True,
        comment="Intraday high price in PKR",
    )

    low_price: db.Mapped[float | None] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=True,
        comment="Intraday low price in PKR",
    )

    close_price: db.Mapped[float] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=False,
        comment="Closing price in PKR (required)",
    )

    volume: db.Mapped[int | None] = db.mapped_column(
        db.BigInteger,
        nullable=True,
        comment="Total shares traded on this date",
    )

    # ── Audit Timestamps ──────────────────────────────────────────────────────
    created_at: db.Mapped[datetime] = db.mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="UTC timestamp when this record was first inserted",
    )

    updated_at: db.Mapped[datetime] = db.mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="UTC timestamp of the last upsert for this record",
    )

    # ── Computed Properties ───────────────────────────────────────────────────
    @property
    def price_range(self) -> float | None:
        """Intraday price range (high - low). Returns None if data unavailable."""
        if self.high_price is not None and self.low_price is not None:
            return float(self.high_price) - float(self.low_price)
        return None

    # ── Helpers ───────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Serialize the model to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "date": self.date.isoformat(),
            "open": float(self.open_price) if self.open_price is not None else None,
            "high": float(self.high_price) if self.high_price is not None else None,
            "low": float(self.low_price) if self.low_price is not None else None,
            "close": float(self.close_price),
            "volume": self.volume,
            "price_range": self.price_range,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<DailyPrice ticker={self.ticker!r} "
            f"date={self.date} close={self.close_price}>"
        )
