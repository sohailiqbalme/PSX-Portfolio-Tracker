"""
app/models/cash_ledger.py
─────────────────────────────────────────────────────────────────────────────
CashLedger model — records all cash inflows and outflows for a portfolio.

Cash flow types:
    - DEPOSIT: Cash injected by the user (positive amount).
    - WITHDRAWAL: Cash withdrawn by the user (negative amount).
    - BUY: Outflow for stock purchase (negative amount, includes commission).
    - SELL: Inflow from stock sale (positive amount, net of commission).

Relationships:
    CashLedger >── Portfolio (many entries → one Portfolio)
    CashLedger ──? Transaction (one entry → optionally one Transaction)
─────────────────────────────────────────────────────────────────────────────
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint

from app.extensions import db


class CashLedgerType(enum.Enum):
    """Allowed cash ledger flow directions."""
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    BUY = "BUY"
    SELL = "SELL"


class CashLedger(db.Model):
    """
    Represents a single cash transaction event within a portfolio.
    
    A negative amount represents cash leaving the portfolio (withdrawals, purchases).
    A positive amount represents cash entering the portfolio (deposits, sales).
    """

    __tablename__ = "cash_ledger"

    __table_args__ = (
        # Ensure non-zero transactions in the ledger
        CheckConstraint("amount != 0", name="ck_cash_ledger_amount_nonzero"),
    )

    # ── Primary Key ───────────────────────────────────────────────────────────
    id: db.Mapped[str] = db.mapped_column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key",
    )

    # ── Foreign Key (Portfolio) ───────────────────────────────────────────────
    portfolio_id: db.Mapped[str] = db.mapped_column(
        db.String(36),
        db.ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent portfolio UUID",
    )

    # ── Foreign Key (Transaction) ─────────────────────────────────────────────
    # Set only for BUY/SELL cash events. Null for manual deposits/withdrawals.
    transaction_id: db.Mapped[str | None] = db.mapped_column(
        db.String(36),
        db.ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Associated trade UUID (if any)",
    )

    # ── Amount ────────────────────────────────────────────────────────────────
    # Value is signed: positive for cash-in, negative for cash-out.
    amount: db.Mapped[float] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=False,
        comment="Signed transaction amount in PKR (positive = cash-in, negative = cash-out)",
    )

    # ── Type ──────────────────────────────────────────────────────────────────
    type: db.Mapped[CashLedgerType] = db.mapped_column(
        db.Enum(CashLedgerType, name="cash_ledger_type"),
        nullable=False,
        comment="Type of cash movement (DEPOSIT, WITHDRAWAL, BUY, SELL)",
    )

    # ── Timestamps ────────────────────────────────────────────────────────────
    transacted_at: db.Mapped[datetime] = db.mapped_column(
        db.DateTime(timezone=True),
        nullable=False,
        comment="UTC datetime when the cash transaction occurred",
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
        comment="Optional description or details",
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    portfolio: db.Mapped["Portfolio"] = db.relationship(  # noqa: F821
        "Portfolio",
        back_populates="cash_ledger",
    )

    transaction: db.Mapped["Transaction | None"] = db.relationship(  # noqa: F821
        "Transaction",
        back_populates="cash_entry",
    )

    # ── Helpers ───────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Serialize the model to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "portfolio_id": self.portfolio_id,
            "transaction_id": self.transaction_id,
            "amount": float(self.amount),
            "type": self.type.value,
            "notes": self.notes,
            "transacted_at": self.transacted_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<CashLedger id={self.id!r} {self.type.value} amount={self.amount}>"
