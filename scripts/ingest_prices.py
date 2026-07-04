"""
scripts/ingest_prices.py
─────────────────────────────────────────────────────────────────────────────
CLI Runner — PSX EOD Price Ingestion

Standalone command-line script to trigger a price ingestion run.
Can be executed directly from the terminal or scheduled via cron / Windows
Task Scheduler for nightly data refreshes.

Usage:
    # Ingest last 30 days for default tickers (from .env)
    python scripts/ingest_prices.py

    # Ingest specific tickers for last 7 days
    python scripts/ingest_prices.py --tickers ENGRO HUBC LUCK --days 7

    # Ingest a specific date range
    python scripts/ingest_prices.py --tickers OGDC --from 2024-01-01 --to 2024-06-30

    # Dry-run: fetch data but don't write to DB
    python scripts/ingest_prices.py --dry-run

Requirements:
    - .env file must exist in the project root (or DATABASE_URL set in env)
    - psxdata must be installed: pip install psxdata
─────────────────────────────────────────────────────────────────────────────
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# ── Ensure the project root is on sys.path ────────────────────────────────────
# Allows importing `app` from any working directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env", override=True)

from app import create_app
from app.config import get_config

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    cfg = get_config()

    parser = argparse.ArgumentParser(
        description="Ingest PSX End-of-Day prices into the Supabase database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=cfg.DEFAULT_TICKERS,
        help=(
            "Space-separated list of PSX ticker symbols. "
            f"Default (from .env): {cfg.DEFAULT_TICKERS}"
        ),
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Start date for data fetch. Overrides --days.",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        default=None,
        metavar="YYYY-MM-DD",
        help="End date for data fetch. Default: today.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=cfg.INGESTION_LOOKBACK_DAYS,
        help=f"Lookback window in days. Default: {cfg.INGESTION_LOOKBACK_DAYS}.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Fetch data from psxdata but do NOT write to the database.",
    )
    parser.add_argument(
        "--output",
        choices=["text", "json"],
        default="text",
        help="Output format for the ingestion result. Default: text.",
    )
    return parser.parse_args()


def main() -> int:
    """
    Entry point. Returns exit code:
        0 — all tickers succeeded
        1 — at least one ticker failed
        2 — argument / config error
    """
    args = parse_args()

    # ── Resolve dates ─────────────────────────────────────────────────────────
    today = date.today()

    try:
        to_date = (
            date.fromisoformat(args.to_date) if args.to_date else today
        )
        from_date = (
            date.fromisoformat(args.from_date)
            if args.from_date
            else today - timedelta(days=args.days)
        )
    except ValueError as exc:
        logger.error("Invalid date format: %s", exc)
        return 2

    if from_date > to_date:
        logger.error("--from date (%s) must not be after --to date (%s).", from_date, to_date)
        return 2

    tickers = [t.strip().upper() for t in args.tickers]
    logger.info(
        "PSX Ingestion CLI | tickers=%s | range=[%s, %s] | dry_run=%s",
        tickers, from_date, to_date, args.dry_run,
    )

    # ── Dry-run mode ──────────────────────────────────────────────────────────
    if args.dry_run:
        from app.services.price_ingestion import fetch_eod_prices
        logger.info("DRY RUN — fetching data only, no DB writes.")
        ticker_data = fetch_eod_prices(
            tickers=tickers,
            from_date=from_date,
            to_date=to_date,
        )
        total_rows = sum(len(df) for df in ticker_data.values())
        logger.info(
            "DRY RUN complete | fetched %d rows across %d tickers.",
            total_rows, len(ticker_data),
        )
        print(f"\n[DRY RUN] Would have upserted {total_rows} rows for: "
              f"{list(ticker_data.keys())}")
        return 0

    # ── Live ingestion (requires Flask app context for SQLAlchemy) ────────────
    flask_app = create_app()
    with flask_app.app_context():
        from app.services.price_ingestion import run_ingestion

        result = run_ingestion(
            tickers=tickers,
            from_date=from_date,
            to_date=to_date,
        )

    # ── Output ────────────────────────────────────────────────────────────────
    if args.output == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print("\n" + "-" * 60)
        print(f"  PSX Price Ingestion Result")
        print("-" * 60)
        print(f"  Tickers requested : {result.tickers_requested}")
        print(f"  Succeeded         : {result.tickers_succeeded}")
        print(f"  Failed            : {result.tickers_failed}")
        print(f"  Rows upserted     : {result.rows_upserted}")
        print(f"  Duration          : {result.duration_seconds:.2f}s")
        if result.errors:
            print(f"  Errors:")
            for ticker, err in result.errors.items():
                print(f"    {ticker}: {err}")
        print("-" * 60 + "\n")

    # Exit 1 if any ticker failed, 0 if all succeeded
    return 1 if result.tickers_failed else 0


if __name__ == "__main__":
    sys.exit(main())
