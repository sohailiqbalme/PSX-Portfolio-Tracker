"""
tests/test_ingestion.py
─────────────────────────────────────────────────────────────────────────────
Unit tests for the price ingestion service.

psxdata is mocked via pytest's monkeypatch so these tests run without
any network access or PSX API credentials.

Run:
    pytest tests/test_ingestion.py -v
─────────────────────────────────────────────────────────────────────────────
"""

import pytest
import pandas as pd
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from app import create_app
from app.extensions import db as _db
from app.models import DailyPrice


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    flask_app = create_app("testing")
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture
def mock_psxdata_df() -> pd.DataFrame:
    """
    A realistic mock DataFrame matching psxdata's output format.

    psxdata returns title-cased columns with a DatetimeIndex.
    """
    idx = pd.to_datetime(["2024-06-03", "2024-06-04", "2024-06-05"])
    df = pd.DataFrame(
        {
            "Open":   [300.0, 302.5, 305.0],
            "High":   [310.0, 312.0, 315.0],
            "Low":    [298.0, 300.0, 302.0],
            "Close":  [308.0, 310.5, 313.0],
            "Volume": [1_200_000, 1_500_000, 900_000],
        },
        index=idx,
    )
    df.index.name = "Date"
    return df


# ─────────────────────────────────────────────────────────────────────────────
# fetch_eod_prices Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestFetchEodPrices:

    def test_fetch_returns_normalised_dataframe(self, app, mock_psxdata_df):
        """fetch_eod_prices returns a normalised DataFrame for a valid ticker."""
        with app.app_context():
            with patch(
                "app.services.price_ingestion.psxdata",
                create=True,
            ) as mock_psx:
                # Simulate psxdata module-level import
                import sys
                fake_module = MagicMock()
                fake_module.stocks.return_value = mock_psxdata_df
                sys.modules["psxdata"] = fake_module

                from app.services.price_ingestion import fetch_eod_prices
                result = fetch_eod_prices(
                    tickers=["ENGRO"],
                    from_date=date(2024, 6, 1),
                    to_date=date(2024, 6, 30),
                )

                assert "ENGRO" in result
                df = result["ENGRO"]
                assert "close_price" in df.columns
                assert "ticker" in df.columns
                assert len(df) == 3  # 3 rows in mock data
                assert list(df["ticker"].unique()) == ["ENGRO"]

    def test_fetch_returns_empty_on_no_data(self, app):
        """fetch_eod_prices silently skips tickers with no data."""
        with app.app_context():
            import sys
            fake_module = MagicMock()
            fake_module.stocks.return_value = pd.DataFrame()  # Empty DF
            sys.modules["psxdata"] = fake_module

            from app.services.price_ingestion import fetch_eod_prices
            result = fetch_eod_prices(
                tickers=["FAKE"],
                from_date=date(2024, 6, 1),
                to_date=date(2024, 6, 30),
            )
            assert "FAKE" not in result

    def test_fetch_handles_exception_gracefully(self, app):
        """fetch_eod_prices does not raise when psxdata throws an exception."""
        with app.app_context():
            import sys
            fake_module = MagicMock()
            fake_module.stocks.side_effect = ConnectionError("Network unavailable")
            sys.modules["psxdata"] = fake_module

            from app.services.price_ingestion import fetch_eod_prices
            result = fetch_eod_prices(
                tickers=["HUBC"],
                from_date=date(2024, 6, 1),
                to_date=date(2024, 6, 30),
            )
            # Should return empty dict — no raise
            assert result == {}


# ─────────────────────────────────────────────────────────────────────────────
# IngestionResult Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestIngestionResult:

    def test_duration_before_finish_is_none(self):
        from app.services.price_ingestion import IngestionResult
        result = IngestionResult(tickers_requested=["ENGRO"])
        assert result.duration_seconds is None

    def test_duration_after_finish(self):
        from app.services.price_ingestion import IngestionResult
        result = IngestionResult(tickers_requested=["ENGRO"])
        result.mark_finished()
        assert result.duration_seconds is not None
        assert result.duration_seconds >= 0

    def test_to_dict_has_all_keys(self):
        from app.services.price_ingestion import IngestionResult
        result = IngestionResult(tickers_requested=["ENGRO", "HUBC"])
        result.tickers_succeeded = ["ENGRO"]
        result.tickers_failed = ["HUBC"]
        result.rows_upserted = 5
        result.mark_finished()

        d = result.to_dict()
        for key in [
            "tickers_requested", "tickers_succeeded", "tickers_failed",
            "rows_upserted", "errors", "started_at", "finished_at",
            "duration_seconds",
        ]:
            assert key in d, f"Missing key: {key}"
