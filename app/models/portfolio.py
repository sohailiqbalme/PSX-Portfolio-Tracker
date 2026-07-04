"""
app/models/portfolio.py
─────────────────────────────────────────────────────────────────────────────
Portfolio model — a named container that groups a set of stock holdings
for a single user (or entity).

Relationships:
    Portfolio ──< Transaction   (one Portfolio → many Transactions)

Notes:
    - This is a single-tenant local application. All portfolios belong to the 
      sole operator of the application.
─────────────────────────────────────────────────────────────────────────────
"""

import uuid
from datetime import datetime, timezone

from app.extensions import db


class Portfolio(db.Model):
    """
    Represents a named collection of stock positions.

    Each portfolio acts as the top-level grouping unit. The operator may own
    multiple portfolios (e.g. "Long-term", "Trading").
    """

    __tablename__ = "portfolios"

    # ── Primary Key ───────────────────────────────────────────────────────────
    id: db.Mapped[str] = db.mapped_column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key",
    )


    # ── Core Fields ───────────────────────────────────────────────────────────
    name: db.Mapped[str] = db.mapped_column(
        db.String(120),
        nullable=False,
        comment="Human-readable portfolio name (e.g. 'Long-term Holdings')",
    )

    description: db.Mapped[str | None] = db.mapped_column(
        db.Text,
        nullable=True,
        comment="Optional free-text description",
    )

    # Starting cash balance (PKR) at portfolio creation time.
    # Useful for computing overall portfolio return.
    initial_balance: db.Mapped[float] = db.mapped_column(
        db.Numeric(18, 4),
        nullable=False,
        default=0.0,
        comment="Initial cash balance in PKR at portfolio inception",
    )

    # ── Audit Timestamps ──────────────────────────────────────────────────────
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

    # ── Relationships ─────────────────────────────────────────────────────────
    # Cascade delete: removing a portfolio removes all its transactions.
    transactions: db.Mapped[list["Transaction"]] = db.relationship(  # noqa: F821
        "Transaction",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        lazy="dynamic",  # Returns a query object — efficient for large sets
    )

    cash_ledger: db.Mapped[list["CashLedger"]] = db.relationship(  # noqa: F821
        "CashLedger",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    # ── Helpers ───────────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        """Serialize the model to a JSON-safe dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "initial_balance": float(self.initial_balance),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def __repr__(self) -> str:
        return f"<Portfolio id={self.id!r} name={self.name!r}>"
