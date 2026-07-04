"""
tests/test_live_sync.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for the Persistent Live Pricing Sync logic.

Tests use an in-memory SQLite database.
Run:
    pytest tests/test_live_sync.py -v
─────────────────────────────────────────────────────────────────────────────
"""

import pytest
from datetime import date, datetime, timezone
import pandas as pd
from unittest.mock import patch, MagicMock

from app import create_app
from app.extensions import db as _db
from app.models import DailyPrice, Portfolio, Transaction, TransactionAction
from app.services.price_ingestion import fetch_live_quotes, run_live_sync


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
    """Clean database session wrapper."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        _db.session.bind = connection

        yield _db.session

        _db.session.remove()
        transaction.rollback()
        connection.close()


@pytest.fixture
def client(app):
    return app.test_client()


class TestLiveSync:

    @patch("psxdata.quote")
    def test_fetch_live_quotes_success(self, mock_quote):
        """fetch_live_quotes maps psxdata.quote output to the database schema."""
        # Set up the mock to return a single-row screener DataFrame
        mock_quote.return_value = pd.DataFrame([{
            "symbol": "ENGRO",
            "sector": 809.0,
            "listed_in": "",
            "market_cap": float('nan'),
            "price": 310.50,
            "change_pct": 1.48,
            "change_1y_pct": 0.0,
            "pe_ratio": 0.0,
            "dividend_yield": 0.0,
            "free_float": float('nan'),
            "volume_avg_30d": 2272600.0
        }])

        results = fetch_live_quotes(["ENGRO"])
        assert "ENGRO" in results
        
        df = results["ENGRO"]
        assert len(df) == 1
        assert df.iloc[0]["ticker"] == "ENGRO"
        assert df.iloc[0]["date"] == date.today()
        assert df.iloc[0]["close_price"] == 310.50
        assert df.iloc[0]["volume"] == 2272600
        assert df.iloc[0]["open_price"] is None
        assert df.iloc[0]["high_price"] is None
        assert df.iloc[0]["low_price"] is None

    @patch("psxdata.quote")
    def test_run_live_sync_commits_to_db(self, mock_quote, db_session):
        """run_live_sync saves the live quote directly into the daily_prices table."""
        mock_quote.return_value = pd.DataFrame([{
            "symbol": "HUBC",
            "sector": 809.0,
            "listed_in": "",
            "market_cap": float('nan'),
            "price": 145.20,
            "change_pct": -0.80,
            "change_1y_pct": 0.0,
            "pe_ratio": 0.0,
            "dividend_yield": 0.0,
            "free_float": float('nan'),
            "volume_avg_30d": 5000000.0
        }])

        # Verify no price row exists for today yet
        today = date.today()
        existing = db_session.query(DailyPrice).filter_by(ticker="HUBC", date=today).first()
        assert existing is None

        # Run sync
        result = run_live_sync(["HUBC"])
        assert "HUBC" in result.tickers_succeeded
        assert result.rows_upserted == 1

        # Check DB has the updated record
        record = db_session.query(DailyPrice).filter_by(ticker="HUBC", date=today).first()
        assert record is not None
        assert float(record.close_price) == 145.20
        assert record.volume == 5000000

    @patch("psxdata.quote")
    def test_sync_rate_limiting(self, mock_quote, client):
        """Endpoint sync-live enforces 15-minute rate limit cooldown."""
        mock_quote.return_value = pd.DataFrame([{
            "symbol": "HUBC",
            "sector": 809.0,
            "listed_in": "",
            "market_cap": float('nan'),
            "price": 145.20,
            "change_pct": -0.80,
            "change_1y_pct": 0.0,
            "pe_ratio": 0.0,
            "dividend_yield": 0.0,
            "free_float": float('nan'),
            "volume_avg_30d": 5000000.0
        }])

        # Clear any existing limits
        from app.api.routes import _LAST_SYNC_TIMES
        _LAST_SYNC_TIMES.pop("global", None)

        # First request should succeed (200)
        res1 = client.post("/api/v1/prices/sync-live", json={"tickers": ["HUBC"]})
        assert res1.status_code == 200

        # Second request should be rate-limited (429)
        res2 = client.post("/api/v1/prices/sync-live", json={"tickers": ["HUBC"]})
        assert res2.status_code == 429
        data = res2.get_json()
        assert "cooldown_seconds" in data
        assert data["cooldown_seconds"] > 0
