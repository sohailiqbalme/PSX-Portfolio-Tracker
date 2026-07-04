"""
tests/test_models.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for SQLAlchemy models.

Tests use an in-memory SQLite database (TestingConfig) — no Supabase needed.
DB-level constraints (CheckConstraint) are skipped for SQLite since SQLite
does not enforce them at the driver level; those are validated at the
application layer and tested separately.

Run:
    pytest tests/test_models.py -v
─────────────────────────────────────────────────────────────────────────────
"""

import pytest
from datetime import date, datetime, timezone

from app import create_app
from app.extensions import db as _db
from app.models import Portfolio, Transaction, TransactionAction, DailyPrice


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Create a test Flask app using the in-memory SQLite config."""
    flask_app = create_app("testing")
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture(scope="function")
def db_session(app):
    """
    Provide a clean DB session per test using savepoints (nested transactions).
    Each test rolls back its changes — no residual state between tests.
    """
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        _db.session.bind = connection

        yield _db.session

        _db.session.remove()
        transaction.rollback()
        connection.close()


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestPortfolio:

    def test_create_portfolio(self, db_session):
        """Portfolio can be created with required fields."""
        p = Portfolio(
            name="Tech Stocks",
            initial_balance=100_000.0,
        )
        db_session.add(p)
        db_session.flush()

        assert p.id is not None
        assert p.name == "Tech Stocks"
        assert float(p.initial_balance) == 100_000.0
        assert p.created_at is not None

    def test_portfolio_to_dict(self, db_session):
        """Portfolio.to_dict() returns a JSON-safe dict with all expected keys."""
        p = Portfolio(name="Serialization Test")
        db_session.add(p)
        db_session.flush()

        d = p.to_dict()
        assert d["name"] == "Serialization Test"
        assert "created_at" in d
        assert "id" in d

    def test_portfolio_repr(self, db_session):
        p = Portfolio(name="REPR Test")
        assert "REPR Test" in repr(p)


# ─────────────────────────────────────────────────────────────────────────────
# Transaction Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestTransaction:

    @pytest.fixture
    def portfolio(self, db_session):
        p = Portfolio(name="TXN Portfolio")
        db_session.add(p)
        db_session.flush()
        return p

    def test_create_buy_transaction(self, db_session, portfolio):
        """BUY transaction is created with correct fields."""
        txn = Transaction(
            portfolio_id=portfolio.id,
            ticker="ENGRO",
            action=TransactionAction.BUY,
            quantity=100,
            price=312.50,
            commission=250.0,
            transacted_at=datetime(2024, 6, 1, 10, 30, tzinfo=timezone.utc),
        )
        db_session.add(txn)
        db_session.flush()

        assert txn.id is not None
        assert txn.action == TransactionAction.BUY
        assert float(txn.quantity) == 100.0
        assert float(txn.price) == 312.50

    def test_transaction_total_value(self, db_session, portfolio):
        """total_value = quantity × price."""
        txn = Transaction(
            portfolio_id=portfolio.id,
            ticker="HUBC",
            action=TransactionAction.BUY,
            quantity=200,
            price=150.0,
            transacted_at=datetime.now(timezone.utc),
        )
        assert txn.total_value == pytest.approx(30_000.0)

    def test_transaction_net_value_buy(self, db_session, portfolio):
        """Net value for BUY = -(total_value + commission)."""
        txn = Transaction(
            portfolio_id=portfolio.id,
            ticker="LUCK",
            action=TransactionAction.BUY,
            quantity=100,
            price=200.0,
            commission=500.0,
            transacted_at=datetime.now(timezone.utc),
        )
        assert txn.net_value == pytest.approx(-20_500.0)

    def test_transaction_net_value_sell(self, db_session, portfolio):
        """Net value for SELL = total_value - commission."""
        txn = Transaction(
            portfolio_id=portfolio.id,
            ticker="LUCK",
            action=TransactionAction.SELL,
            quantity=100,
            price=200.0,
            commission=500.0,
            transacted_at=datetime.now(timezone.utc),
        )
        assert txn.net_value == pytest.approx(19_500.0)

    def test_transaction_to_dict(self, db_session, portfolio):
        """to_dict() contains all required keys."""
        txn = Transaction(
            portfolio_id=portfolio.id,
            ticker="OGDC",
            action=TransactionAction.BUY,
            quantity=50,
            price=100.0,
            transacted_at=datetime.now(timezone.utc),
        )
        db_session.add(txn)
        db_session.flush()
        d = txn.to_dict()

        for key in ["id", "ticker", "action", "quantity", "price",
                    "total_value", "net_value", "transacted_at"]:
            assert key in d, f"Missing key in to_dict(): {key}"


# ─────────────────────────────────────────────────────────────────────────────
# DailyPrice Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestDailyPrice:

    def test_create_daily_price(self, db_session):
        """DailyPrice is created with required fields."""
        dp = DailyPrice(
            ticker="ENGRO",
            date=date(2024, 6, 1),
            close_price=312.50,
            open_price=308.0,
            high_price=315.0,
            low_price=305.0,
            volume=1_500_000,
        )
        db_session.add(dp)
        db_session.flush()

        assert dp.id is not None
        assert dp.ticker == "ENGRO"
        assert float(dp.close_price) == 312.50

    def test_price_range(self, db_session):
        """price_range returns high - low."""
        dp = DailyPrice(
            ticker="HUBC",
            date=date(2024, 6, 2),
            close_price=150.0,
            high_price=155.0,
            low_price=145.0,
        )
        assert dp.price_range == pytest.approx(10.0)

    def test_price_range_none_when_missing(self, db_session):
        """price_range is None when high or low is missing."""
        dp = DailyPrice(
            ticker="LUCK",
            date=date(2024, 6, 3),
            close_price=200.0,
        )
        assert dp.price_range is None

    def test_daily_price_to_dict(self, db_session):
        """to_dict() contains all expected keys and correct types."""
        dp = DailyPrice(
            ticker="MCB",
            date=date(2024, 6, 4),
            close_price=250.0,
        )
        db_session.add(dp)
        db_session.flush()
        d = dp.to_dict()

        for key in ["ticker", "date", "close", "created_at", "updated_at"]:
            assert key in d
        assert d["ticker"] == "MCB"
        assert d["close"] == 250.0
