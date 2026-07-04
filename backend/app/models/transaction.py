"""
app/models/transaction.py
─────────────────────────────────────────────────────────────────────────────
Transaction model — records a single BUY or SELL event for a stock ticker
within a portfolio.

Key constraints (enforced at the DB level, not just application level):
    - quantity  MUST be > 0
    - price     MUST be > 0

Relationships:
    Transaction >── Portfolio   (many Transactions → one Portfolio)
─────────────────────────────────────────────────────────────────────────────
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index

from app.extensions import db


class TransactionAction(enum.Enum):
    """Allowed transaction directions."""
    BUY = "BUY"
    SELL = "SELL"


class Transaction(db.Model):
    """
    Represents a single stock trade event (buy or sell) within a portfolio.

    DB-level constraints prevent negative quantities and prices from ever
    being persisted, regardless of the application layer's behaviour.
    """

    __tablename__ = "transactions"

    # ── Table-level constraints and indexes ───────────────────────────────────
    __table_args__ = (
        # Enforce valid quantity at the database level (not just application layer)
        CheckConstraint("quantity > 0", name="ck_transactions_quantity_positive"),
        # Enforce valid price at the database level
        CheckConstraint("price > 0", name="ck_transactions_price_positive"),
        # Enforce valid commission (zero is allowed for commission-free brokers)
        CheckConstraint("commission >= 0", name="ck_transactions_commission_nonneg"),
        # Composite index: fast queries for "all trades of ticker X in portfolio Y"
        Index("ix_transactions_portfolio_ticker_ts", "portfolio_id", "ticker", "transacted_at"),
    )

    # ── Primary Key ───────────────────────────────────────────────────────────
    id: db.Mapped[str] = db.mapped_column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key",
    )

    # ── Foreign Key ───────────────────────────────────────────────────────────
    portfolio_id: db.Mapped[str] = db.mapped_column(
        db.String(36),
        db.ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent portfolio UUID",
    )

    # ── Ticker ────────────────────────────────────────────────────────────────
    # PSX tickers are typically 3–6 uppercase letters (e.g. ENGRO, HUBC, MCB)
    ticker: db.Mapped[str] = db.mapped_column(
        db.String(10),
        nullable=False,
        comment="PSX stock ticker symbol (uppercase, e.g. 'ENGRO')",
    )

    # ── Action ────────────────────────────────────────────────────────────────
    action: db.Mapped[TransactionAction] = db.mapped_column(
        db.Enum(TransactionAction, name="transaction_action"),
        nullable=False,
        comment="BUY or SELL",
    )

    # ── Quantity ──────────────────────────────────────────────────────────────
    # Number of shares. Must be > 0 (enforced by CheckConstraint above).
    # Using Numeric to avoid floating-point rounding issues with share counts.
    quantity: db.Mapped[float] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=False,
        comment="Number of shares traded. Must be > 0.",
    )

    # ── Price ─────────────────────────────────────────────────────────────────
    # Trade execution price per share in PKR. Must be > 0.
    price: db.Mapped[float] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=False,
        comment="Price per share in PKR at execution. Must be > 0.",
    )

    # ── Commission ────────────────────────────────────────────────────────────
    # Broker commission paid on this transaction (PKR). Defaults to 0.
    commission: db.Mapped[float] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=False,
        default=0.0,
        comment="Broker commission in PKR (>= 0). Default is 0.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    # The actual trade date/time (user-supplied, may differ from insert time)
    transacted_at: db.Mapped[datetime] = db.mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        comment="UTC datetime when the trade was executed",
    )

    created_at: db.Mapped[datetime] = db.mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        comment="UTC timestamp of record creation",
    )

    updated_at: db.Mapped[datetime] = db.mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        comment="UTC timestamp of last update",
    )

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes: db.Mapped[str | None] = db.mapped_column(
        db.Text,
        nullable=True,
        comment="Optional trade note or rationale",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    portfolio: db.Mapped["Portfolio"] = db.relationship(  # noqa: F821
        "Portfolio",
        back_populates="transactions",
    )

    cash_entry: db.Mapped["CashLedger | None"] = db.relationship(  # noqa: F821
        "CashLedger",
        back_populates="transaction",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # ── Computed Properties ───────────────────────────────────────────────────
    @property
    def total_value(self) -> float:
        """
        Gross trade value before commission (quantity × price).

        For a BUY  → cash outflow (positive cost)
        For a SELL → cash inflow (positive revenue)
        """
        return float(self.quantity) * float(self.price)

    @property
    def net_value(self) -> float:
        """
        Net cash impact of this transaction including commission.

        BUY  → -(total_value + commission)  [cash out]
        SELL → +(total_value - commission)  [cash in]
        """
        gross = self.total_value
        comm = float(self.commission)
        if self.action == TransactionAction.BUY:
            return -(gross + comm)
        return gross - comm

    # ── Helpers ───────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Serialize the model to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "portfolio_id": self.portfolio_id,
            "ticker": self.ticker,
            "action": self.action.value,
            "quantity": float(self.quantity),
            "price": float(self.price),
            "commission": float(self.commission),
            "total_value": self.total_value,
            "net_value": self.net_value,
            "transacted_at": self.transacted_at.isoformat(),
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return (
            f"<Transaction id={self.id!r} "
            f"{self.action.value} {self.quantity}x{self.ticker} @ {self.price}>"
        )
