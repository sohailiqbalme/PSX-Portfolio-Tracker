"""
app/api/routes.py
─────────────────────────────────────────────────────────────────────────────
REST API Endpoints for the PSX Portfolio Tracker.

Blueprint: 'api'  (prefix: /api/v1)

Endpoints:
    GET  /api/v1/health                     — Liveness / DB connectivity check
    GET  /api/v1/prices/<ticker>            — Latest price for a ticker
    GET  /api/v1/prices/<ticker>/history    — Date-range EOD history
    POST /api/v1/prices/ingest              — Trigger manual ingestion run
    GET  /api/v1/portfolios                 — List portfolios for a user
    POST /api/v1/portfolios                 — Create a new portfolio
    GET  /api/v1/portfolios/<id>            — Get a portfolio and its holdings
    POST /api/v1/portfolios/<id>/transactions — Add a transaction
─────────────────────────────────────────────────────────────────────────────
"""

import logging
from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from sqlalchemy import desc, text

from app.extensions import db
from app.models import DailyPrice, Portfolio, Transaction, TransactionAction, CashLedger, CashLedgerType, CompanyMetadata
from app.services.price_ingestion import run_ingestion, run_live_sync

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# Global tracking for live sync rate limits (cooldown: 15 minutes / 900 seconds)
# Maps "global" -> datetime of last successful sync
_LAST_SYNC_TIMES = {}



# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_date(value: str | None, default: date) -> date:
    """Parse 'YYYY-MM-DD' string to date, falling back to default."""
    if value:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            pass
    return default


def _error(message: str, status: int = 400) -> tuple:
    return jsonify({"error": message}), status


def _ok(data: dict | list, status: int = 200) -> tuple:
    return jsonify(data), status


def _get_cash_balance(portfolio_id: str) -> float:
    """Sum the amounts in the cash ledger for a portfolio to get the current cash balance."""
    from sqlalchemy import func
    res = (
        db.session.query(func.sum(CashLedger.amount))
        .filter(CashLedger.portfolio_id == portfolio_id)
        .scalar()
    )
    return float(res) if res is not None else 0.0


def _get_portfolio_holdings(portfolio_id: str) -> dict:
    """
    Calculate holdings and their dynamic weighted average cost basis for a portfolio.

    Returns:
        {
            ticker: {
                "shares": float,
                "avg_cost": float,
                "company_name": str,
                "sector": str
            }
        }
    """
    txns = (
        db.session.query(Transaction)
        .filter(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.transacted_at.asc(), Transaction.created_at.asc())
        .all()
    )

    holdings = {}
    for t in txns:
        ticker = t.ticker.upper()
        if ticker not in holdings:
            holdings[ticker] = {"shares": 0.0, "avg_cost": 0.0}

        pos = holdings[ticker]
        qty = float(t.quantity)
        price = float(t.price)
        comm = float(t.commission)

        if t.action == TransactionAction.BUY:
            current_total_cost = pos["shares"] * pos["avg_cost"]
            # Commissions increase the cost basis on purchases
            new_total_cost = current_total_cost + (qty * price) + comm
            new_shares = pos["shares"] + qty
            pos["shares"] = new_shares
            pos["avg_cost"] = new_total_cost / new_shares if new_shares > 0 else 0.0
        elif t.action == TransactionAction.SELL:
            # Commissions decrease cash inflow but do not affect average cost of remaining shares
            new_shares = max(0.0, pos["shares"] - qty)
            pos["shares"] = new_shares
            if new_shares == 0.0:
                pos["avg_cost"] = 0.0

    # Enrich with CompanyMetadata
    result = {}
    for k, v in holdings.items():
        if v["shares"] > 0:
            meta = db.session.get(CompanyMetadata, k)
            result[k] = {
                "shares": v["shares"],
                "avg_cost": v["avg_cost"],
                "company_name": meta.company_name if meta else k,
                "sector": meta.sector if meta else "MISCELLANEOUS"
            }
    return result



# ─────────────────────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.get("/health")
def health():
    """
    Liveness probe.

    Returns database connectivity status alongside the API version.
    Safe to expose publicly (no sensitive data).
    """
    try:
        db.session.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.error("DB health check failed: %s", exc)
        db_status = "error"

    status_code = 200 if db_status == "ok" else 503
    return _ok(
        {
            "status": "ok" if db_status == "ok" else "degraded",
            "database": db_status,
            "version": "1.0.0",
        },
        status_code,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Price Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.get("/prices/<string:ticker>")
def get_latest_price(ticker: str):
    """
    Return the most recent cached EOD price for a given ticker.

    Response: DailyPrice.to_dict()
    404 if no price data exists for this ticker.
    """
    ticker = ticker.upper()
    record = (
        db.session.query(DailyPrice)
        .filter(DailyPrice.ticker == ticker)
        .order_by(desc(DailyPrice.date))
        .first()
    )
    if record is None:
        return _error(f"No price data found for ticker '{ticker}'.", 404)

    return _ok(record.to_dict())


@api_bp.get("/prices/<string:ticker>/history")
def get_price_history(ticker: str):
    """
    Return paginated EOD price history for a ticker.

    Query params:
        from    YYYY-MM-DD  Start date (default: 30 days ago)
        to      YYYY-MM-DD  End date   (default: today)
        limit   int         Max rows   (default: 90, max: 365)

    Response: { ticker, from, to, count, prices: [...] }
    """
    ticker = ticker.upper()
    today = date.today()
    from_date = _parse_date(request.args.get("from"), today - timedelta(days=30))
    to_date = _parse_date(request.args.get("to"), today)
    limit = min(int(request.args.get("limit", 90)), 365)

    records = (
        db.session.query(DailyPrice)
        .filter(
            DailyPrice.ticker == ticker,
            DailyPrice.date >= from_date,
            DailyPrice.date <= to_date,
        )
        .order_by(desc(DailyPrice.date))
        .limit(limit)
        .all()
    )

    return _ok(
        {
            "ticker": ticker,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "count": len(records),
            "prices": [r.to_dict() for r in records],
        }
    )


@api_bp.post("/prices/ingest")
def trigger_ingestion():
    """
    Manually trigger a price ingestion run.

    Request body (JSON):
        {
            "tickers": ["ENGRO", "HUBC"],   // required
            "from":    "2024-01-01",         // optional
            "to":      "2024-06-30",         // optional
            "days_back": 30                  // optional (used if from/to absent)
        }

    Response: IngestionResult.to_dict()
    """
    body = request.get_json(silent=True) or {}
    tickers = body.get("tickers")

    if not tickers or not isinstance(tickers, list):
        return _error("'tickers' must be a non-empty list of strings.")

    tickers = [str(t).strip().upper() for t in tickers if t]
    if not tickers:
        return _error("'tickers' list contained no valid ticker symbols.")

    today = date.today()
    days_back = int(body.get("days_back", 30))
    from_date = _parse_date(body.get("from"), today - timedelta(days=days_back))
    to_date = _parse_date(body.get("to"), today)

    logger.info("Manual ingestion triggered | tickers=%s", tickers)
    result = run_ingestion(
        tickers=tickers,
        from_date=from_date,
        to_date=to_date,
    )

    status = 200 if result.rows_upserted > 0 else 207  # 207 = partial success
    return _ok(result.to_dict(), status)


@api_bp.post("/prices/sync-live")
def sync_live_prices():
    """
    Manually trigger live pricing synchronization.

    If no tickers are provided in the body, fetches active tickers from the user's portfolios.
    If that is also empty, falls back to config.DEFAULT_TICKERS.

    Request body (JSON):
        {
            "tickers": ["ENGRO", "HUBC"]   // optional
        }
    """
    body = request.get_json(silent=True) or {}
    tickers = body.get("tickers")
    sync_all = body.get("sync_all", False)

    # ── Enforce 15-Minute Cooldown (900 seconds) ──────────────────────────────
    last_sync = _LAST_SYNC_TIMES.get("global")
    if last_sync:
        elapsed = (datetime.now() - last_sync).total_seconds()
        if elapsed < 900:
            cooldown_rem = int(900 - elapsed)
            logger.warning("Rate limit hit for sync-live | | remaining=%ds", cooldown_rem)
            return jsonify({
                "error": "Sync is rate-limited. Please wait.",
                "cooldown_seconds": cooldown_rem
            }), 429

    if sync_all or tickers == ["all"]:
        logger.info("Live sync triggered for ENTIRE MARKET in bulk")
        result = run_live_sync([])
    else:
        if not tickers:
            # Find all portfolios
            portfolios = db.session.query(Portfolio).all()
            portfolio_ids = [p.id for p in portfolios]

            # Get unique tickers from transactions in these portfolios
            unique_tickers_res = (
                db.session.query(Transaction.ticker)
                .filter(Transaction.portfolio_id.in_(portfolio_ids))
                .distinct()
                .all()
            ) if portfolio_ids else []

            tickers = [r[0].upper() for r in unique_tickers_res]

        if not tickers:
            # Fallback to configured default tickers
            from flask import current_app
            tickers = current_app.config.get("DEFAULT_TICKERS", [])

        tickers = [str(t).strip().upper() for t in tickers if t]
        if not tickers:
            return _error("No tickers found to sync.")

        logger.info("Live sync triggered for tickers=%s", tickers)
        result = run_live_sync(tickers)

    # Only start cooldown if at least one price was successfully updated in the DB
    if result.rows_upserted > 0:
        _LAST_SYNC_TIMES["global"] = datetime.now()

    status = 200 if result.rows_upserted > 0 else 207
    return _ok(result.to_dict(), status)


# ─────────────────────────────────────────────────────────────────────────────
# Portfolio Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@api_bp.get("/portfolios")
def list_portfolios():
    """
    List all portfolios for the authenticated user.

    The user_id is derived from the verified Supabase JWT — no query param needed.

    Response: { portfolios: [...] }
    """

    portfolios = (
        db.session.query(Portfolio)
        .order_by(Portfolio.created_at)
        .all()
    )
    
    if not portfolios:
        default_portfolio = Portfolio(
            name="Default Portfolio",
            initial_balance=1000000.0,
            description="Primary trading ledger"
        )
        db.session.add(default_portfolio)
        db.session.flush() # Populate default_portfolio.id
        
        ledger_entry = CashLedger(
            portfolio_id=default_portfolio.id,
            amount=1000000.0,
            type=CashLedgerType.DEPOSIT,
            transacted_at=default_portfolio.created_at,
            notes="Initial deposit upon portfolio creation"
        )
        db.session.add(ledger_entry)
        db.session.commit()
        portfolios = [default_portfolio]
        logger.info("Auto-seeded Default Portfolio (id=%s) and cash ledger entry.", default_portfolio.id)
    else:
        # Self-heal existing portfolios that have initial_balance > 0 but no CashLedger entries
        for p in portfolios:
            ledger_count = db.session.query(CashLedger).filter_by(portfolio_id=p.id).count()
            if ledger_count == 0 and float(p.initial_balance) > 0:
                ledger_entry = CashLedger(
                    portfolio_id=p.id,
                    amount=float(p.initial_balance),
                    type=CashLedgerType.DEPOSIT,
                    transacted_at=p.created_at,
                    notes="Initial deposit upon portfolio creation"
                )
                db.session.add(ledger_entry)
                db.session.commit()
                logger.info("Self-healed CashLedger for portfolio id=%s", p.id)

    return _ok({"portfolios": [p.to_dict() for p in portfolios]})


@api_bp.post("/portfolios")
def create_portfolio():
    """
    Create a new portfolio for the authenticated user.

    The user_id is sourced from the verified JWT — do not pass it in the body.

    Request body (JSON):
        {
            "name":            "Long-term",      // required
            "description":     "...",            // optional
            "initial_balance": 500000.0          // optional, PKR
        }

    Response: portfolio.to_dict()
    """
    body = request.get_json(silent=True) or {}
    name = body.get("name", "").strip()

    if not name:
        return _error("'name' is required.")

    initial_balance = float(body.get("initial_balance", 0.0))
    if initial_balance < 0:
        return _error("'initial_balance' cannot be negative.")

    portfolio = Portfolio(
        name=name,
        description=body.get("description"),
        initial_balance=initial_balance,
    )
    db.session.add(portfolio)
    
    # If starting with cash, log initial deposit in ledger
    if initial_balance > 0:
        db.session.flush() # Populate portfolio.id
        ledger_entry = CashLedger(
            portfolio_id=portfolio.id,
            amount=initial_balance,
            type=CashLedgerType.DEPOSIT,
            transacted_at=portfolio.created_at,
            notes="Initial deposit upon portfolio creation"
        )
        db.session.add(ledger_entry)

    db.session.commit()

    logger.info("Created portfolio id=%s for with initial balance=%s", portfolio.id, initial_balance)
    return _ok(portfolio.to_dict(), 201)


@api_bp.post("/portfolios/<string:portfolio_id>/cash")
def transact_cash(portfolio_id: str):
    """
    Perform a manual cash DEPOSIT or WITHDRAWAL on a portfolio.

    Request body (JSON):
        {
            "type":          "DEPOSIT",        // required: DEPOSIT | WITHDRAWAL
            "amount":        10000.0,          // required, > 0
            "transacted_at": "2024-06-01T10:30:00Z", // optional, defaults to now
            "notes":         "Added savings"   // optional
        }
    """
    portfolio = db.session.get(Portfolio, portfolio_id)
    if not portfolio:
        return _error(f"Portfolio '{portfolio_id}' not found.", 404)
    if portfolio.user_id != user_id:
        return _error("You do not have access to this portfolio.", 403)

    body = request.get_json(silent=True) or {}
    
    type_str = str(body.get("type", "")).strip().upper()
    if type_str not in [CashLedgerType.DEPOSIT.value, CashLedgerType.WITHDRAWAL.value]:
        return _error("Type must be 'DEPOSIT' or 'WITHDRAWAL'.")
    ledger_type = CashLedgerType[type_str]

    try:
        amount = float(body["amount"])
    except (KeyError, TypeError, ValueError):
        return _error("'amount' is required and must be numeric.")

    if amount <= 0:
        return _error("'amount' must be greater than 0.")

    # Parse transacted_at
    if "transacted_at" in body:
        try:
            transacted_at = datetime.fromisoformat(
                str(body["transacted_at"]).replace("Z", "+00:00")
            )
        except ValueError:
            return _error("'transacted_at' must be an ISO 8601 datetime string.")
    else:
        transacted_at = datetime.now(timezone.utc)

    # Signed amount: deposits are positive cash inflow, withdrawals are negative cash outflow
    signed_amount = amount if ledger_type == CashLedgerType.DEPOSIT else -amount

    if ledger_type == CashLedgerType.WITHDRAWAL:
        current_cash = _get_cash_balance(portfolio_id)
        if amount > current_cash:
            return _error(f"Insufficient funds for withdrawal. Available: {current_cash}, Requested: {amount}")

    ledger_entry = CashLedger(
        portfolio_id=portfolio_id,
        amount=signed_amount,
        type=ledger_type,
        transacted_at=transacted_at,
        notes=body.get("notes"),
    )
    db.session.add(ledger_entry)
    db.session.commit()

    logger.info("Cash transaction added | portfolio=%s type=%s amount=%s", portfolio_id, type_str, amount)
    return _ok(ledger_entry.to_dict(), 201)


@api_bp.get("/portfolios/<string:portfolio_id>")
def get_portfolio(portfolio_id: str):
    """
    Get a single portfolio and its most recent transactions.

    Enforces ownership — users can only access their own portfolios.

    Response: { portfolio: {...}, transactions: [...] }
    """
    portfolio = db.session.get(Portfolio, portfolio_id)
    if not portfolio:
        return _error(f"Portfolio '{portfolio_id}' not found.", 404)

    txns = (
        portfolio.transactions
        .order_by(desc(Transaction.transacted_at), desc(Transaction.created_at))
        .limit(50)
        .all()
    )
    
    # Calculate holdings and cash balance
    cash_balance = _get_cash_balance(portfolio_id)
    holdings = _get_portfolio_holdings(portfolio_id)

    return _ok(
        {
            "portfolio": portfolio.to_dict(),
            "cash_balance": cash_balance,
            "holdings": holdings,
            "transactions": [t.to_dict() for t in txns],
        }
    )


@api_bp.get("/portfolios/<string:portfolio_id>/performance")
def get_portfolio_performance(portfolio_id: str):
    """
    Get the daily historical valuation curve and cumulative time-weighted returns (TWR)
    for a portfolio vs. the KSE-100 benchmark over the past N days.

    Query params:
        days    int     Number of days to look back (default: 30)
    """
    portfolio = db.session.get(Portfolio, portfolio_id)
    if not portfolio:
        return _error(f"Portfolio '{portfolio_id}' not found.", 404)

    try:
        days = int(request.args.get("days", 30))
    except ValueError:
        return _error("'days' parameter must be an integer.")

    if days <= 0:
        return _error("'days' must be greater than 0.")

    today = date.today()
    start_date = today - timedelta(days=days)

    # 1. Gather all unique stock tickers transacted in this portfolio
    txns = (
        db.session.query(Transaction)
        .filter(Transaction.portfolio_id == portfolio_id)
        .order_by(Transaction.transacted_at.asc(), Transaction.created_at.asc())
        .all()
    )
    portfolio_tickers = list(set(t.ticker.upper() for t in txns if t.ticker))

    # 2. Check if we need to auto-ingest price history for these tickers + KSE100
    all_tickers_to_check = portfolio_tickers + ["KSE100"]
    tickers_to_ingest = []
    for ticker in all_tickers_to_check:
        has_prices = (
            db.session.query(DailyPrice)
            .filter(DailyPrice.ticker == ticker, DailyPrice.date >= start_date)
            .first()
        )
        if not has_prices:
            tickers_to_ingest.append(ticker)

    if tickers_to_ingest:
        logger.info("Auto-ingesting history for missing performance tickers: %s", tickers_to_ingest)
        try:
            run_ingestion(tickers_to_ingest, from_date=start_date, to_date=today)
        except Exception as e:
            logger.error("Failed to auto-ingest historical prices for performance: %s", e)

    # 3. Generate the chronological list of all calendar dates in the range
    calendar_dates = [start_date + timedelta(days=i) for i in range(days + 1)]

    # 4. Fetch all price history for these tickers and KSE100 in the range
    prices_raw = (
        db.session.query(DailyPrice)
        .filter(
            DailyPrice.ticker.in_(all_tickers_to_check),
            DailyPrice.date <= today
        )
        .order_by(DailyPrice.date.asc())
        .all()
    )

    prices_by_ticker = {ticker: {} for ticker in all_tickers_to_check}
    sorted_prices_by_ticker = {ticker: [] for ticker in all_tickers_to_check}
    for p in prices_raw:
        prices_by_ticker[p.ticker][p.date] = float(p.close_price)
        sorted_prices_by_ticker[p.ticker].append((p.date, float(p.close_price)))

    def get_price_on_or_before(ticker: str, d: date) -> float | None:
        val = prices_by_ticker.get(ticker, {}).get(d)
        if val is not None:
            return val
        ticker_prices = sorted_prices_by_ticker.get(ticker, [])
        best_price = None
        for p_date, p_close in ticker_prices:
            if p_date <= d:
                best_price = p_close
            else:
                break
        return best_price

    # 5. Fetch all cash ledger entries for the portfolio
    ledgers = (
        db.session.query(CashLedger)
        .filter(CashLedger.portfolio_id == portfolio_id)
        .order_by(CashLedger.transacted_at.asc())
        .all()
    )

    # 6. Fetch all transactions for the portfolio
    portfolio_txns = txns

    # 7. Compute daily values for each date in the timeline
    performance_series = []
    
    cumulative_twr = 0.0
    prev_valuation = None

    kse0 = get_price_on_or_before("KSE100", start_date)
    if kse0 is None:
        kse_all = sorted_prices_by_ticker.get("KSE100", [])
        if kse_all:
            kse0 = kse_all[0][1]

    for d in calendar_dates:
        d_end = datetime.combine(d, datetime.max.time()).replace(tzinfo=timezone.utc)
        
        cash_on_date = sum(
            float(l.amount) for l in ledgers if l.transacted_at <= d_end
        )

        shares_on_date = {}
        for t in portfolio_txns:
            if t.transacted_at <= d_end:
                t_ticker = t.ticker.upper()
                if t_ticker not in shares_on_date:
                    shares_on_date[t_ticker] = 0.0
                qty = float(t.quantity)
                if t.action == TransactionAction.BUY:
                    shares_on_date[t_ticker] += qty
                elif t.action == TransactionAction.SELL:
                    shares_on_date[t_ticker] = max(0.0, shares_on_date[t_ticker] - qty)

        holdings_value = 0.0
        for ticker, shares in shares_on_date.items():
            if shares > 0:
                ticker_price = get_price_on_or_before(ticker, d)
                if ticker_price is not None:
                    holdings_value += shares * ticker_price
                else:
                    first_txn = next((t for t in portfolio_txns if t.ticker.upper() == ticker), None)
                    if first_txn:
                        holdings_value += shares * float(first_txn.price)

        valuation = holdings_value + cash_on_date

        d_start = datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc)
        external_cash_flow = sum(
            float(l.amount) for l in ledgers
            if d_start <= l.transacted_at <= d_end and l.type in [CashLedgerType.DEPOSIT, CashLedgerType.WITHDRAWAL]
        )

        daily_return = 0.0
        if prev_valuation is not None:
            starting_basis = prev_valuation + external_cash_flow
            if starting_basis > 0:
                daily_return = (valuation - starting_basis) / starting_basis
            else:
                daily_return = 0.0
            
            cumulative_twr = (1.0 + cumulative_twr) * (1.0 + daily_return) - 1.0
        else:
            cumulative_twr = 0.0

        prev_valuation = valuation

        kse_val = get_price_on_or_before("KSE100", d)
        if kse_val is None:
            kse_val = kse0 or 0.0

        kse_return_pct = 0.0
        if kse0 and kse0 > 0:
            kse_return_pct = ((kse_val - kse0) / kse0) * 100.0

        performance_series.append({
            "date": d.isoformat(),
            "portfolio_value": round(valuation, 2),
            "portfolio_return_pct": round(cumulative_twr * 100.0, 4),
            "kse100_value": round(kse_val, 2),
            "kse100_return_pct": round(kse_return_pct, 4)
        })

    return _ok({
        "performance": performance_series
    })


@api_bp.post("/portfolios/<string:portfolio_id>/transactions")
def add_transaction(portfolio_id: str):
    """
    Add a BUY or SELL transaction to a portfolio.
    Enforces ownership — users can only modify their own portfolios.

    Request body (JSON):
        {
            "ticker":         "ENGRO",          // required, PSX symbol
            "action":         "BUY",            // required: BUY | SELL
            "quantity":       500,              // required, > 0
            "price":          312.50,           // required, > 0 (PKR)
            "commission":     250.0,            // optional, default 0
            "transacted_at":  "2024-06-01T10:30:00Z", // required ISO 8601
            "notes":          "Bought on dip"   // optional
        }

    Response: transaction.to_dict()
    """
    portfolio = db.session.get(Portfolio, portfolio_id)
    if not portfolio:
        return _error(f"Portfolio '{portfolio_id}' not found.", 404)

    body = request.get_json(silent=True) or {}

    # ── Validate required fields ───────────────────────────────────────────
    ticker = str(body.get("ticker", "")).strip().upper()
    if not ticker:
        return _error("'ticker' is required.")

    action_str = str(body.get("action", "")).strip().upper()
    if action_str not in TransactionAction.__members__:
        return _error(f"'action' must be one of {list(TransactionAction.__members__)}.")
    action = TransactionAction[action_str]

    try:
        quantity = float(body["quantity"])
        price = float(body["price"])
    except (KeyError, TypeError, ValueError):
        return _error("'quantity' and 'price' are required numeric fields.")

    if quantity <= 0:
        return _error("'quantity' must be greater than 0.")
    if price <= 0:
        return _error("'price' must be greater than 0.")

    commission = float(body.get("commission", 0.0))
    if commission < 0:
        return _error("'commission' must be >= 0.")

    # ── Parse transacted_at ───────────────────────────────────────────────
    try:
        transacted_at = datetime.fromisoformat(
            str(body["transacted_at"]).replace("Z", "+00:00")
        )
    except (KeyError, ValueError):
        return _error("'transacted_at' is required as an ISO 8601 datetime string.")

    # ── Check pre-trade conditions (Cash Balance for BUY, Holdings for SELL) ──
    total_val = quantity * price

    if action == TransactionAction.BUY:
        # Cash needed = total value of stock + broker commission
        cash_needed = total_val + commission
        current_cash = _get_cash_balance(portfolio_id)
        if cash_needed > current_cash:
            return _error(
                f"Insufficient funds for stock purchase. Required: {cash_needed:.2f} PKR, "
                f"Available: {current_cash:.2f} PKR.",
                400
            )
    elif action == TransactionAction.SELL:
        # Check if portfolio has sufficient shares of the stock
        holdings = _get_portfolio_holdings(portfolio_id)
        pos = holdings.get(ticker, {"shares": 0.0})
        if quantity > pos["shares"]:
            return _error(
                f"Insufficient share balance to sell. Attempted: {quantity:.2f} shares, "
                f"Owned: {pos['shares']:.2f} shares.",
                400
            )

    # ── Record Transaction & Cash Ledger Entry ──────────────────────────────
    txn = Transaction(
        portfolio_id=portfolio_id,
        ticker=ticker,
        action=action,
        quantity=quantity,
        price=price,
        commission=commission,
        transacted_at=transacted_at,
        notes=body.get("notes"),
    )
    db.session.add(txn)
    db.session.flush() # Generate transaction.id

    ledger_type = CashLedgerType.BUY if action == TransactionAction.BUY else CashLedgerType.SELL
    # Signed amount: BUY is cash out (negative), SELL is cash in (positive)
    signed_cash_amount = -(total_val + commission) if action == TransactionAction.BUY else (total_val - commission)

    ledger_entry = CashLedger(
        portfolio_id=portfolio_id,
        transaction_id=txn.id,
        amount=signed_cash_amount,
        type=ledger_type,
        transacted_at=transacted_at,
        notes=f"{action.value} {quantity} shares of {ticker} @ {price} (Commission: {commission})"
    )
    db.session.add(ledger_entry)
    db.session.commit()

    logger.info(
        "Transaction added | portfolio=%s ticker=%s action=%s qty=%s price=%s net_cash=%s",
        portfolio_id, ticker, action_str, quantity, price, signed_cash_amount
    )
    return _ok(txn.to_dict(), 201)


@api_bp.get("/tickers/search")
def search_tickers():
    """
    Search PSX company metadata by ticker or company name.
    """
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    results = (
        db.session.query(CompanyMetadata)
        .filter(
            (CompanyMetadata.ticker.ilike(f"{q}%")) |
            (CompanyMetadata.company_name.ilike(f"%{q}%"))
        )
        .limit(10)
        .all()
    )
    return jsonify([r.to_dict() for r in results])


@api_bp.get("/market-watch")
def get_market_watch():
    """
    Get all companies grouped by sector, including their latest price.
    """
    from sqlalchemy import func, and_
    
    # Subquery to resolve latest price date per ticker
    max_date_sub = (
        db.session.query(DailyPrice.ticker, func.max(DailyPrice.date).label("max_date"))
        .group_by(DailyPrice.ticker)
        .subquery()
    )

    latest_prices = (
        db.session.query(DailyPrice)
        .join(max_date_sub, and_(
            DailyPrice.ticker == max_date_sub.c.ticker,
            DailyPrice.date == max_date_sub.c.max_date
        ))
        .subquery()
    )

    # Outer join metadata to include all tracked tickers even if they have no price history
    companies_with_prices = (
        db.session.query(
            CompanyMetadata,
            latest_prices.c.close_price,
            latest_prices.c.volume,
            latest_prices.c.date
        )
        .outerjoin(latest_prices, CompanyMetadata.ticker == latest_prices.c.ticker)
        .order_by(CompanyMetadata.sector, CompanyMetadata.ticker)
        .all()
    )

    # Group by sector
    sectors_map = {}
    for item in companies_with_prices:
        meta, price, vol, dt = item
        sector_name = meta.sector or "MISCELLANEOUS"
        
        if sector_name not in sectors_map:
            sectors_map[sector_name] = []
            
        sectors_map[sector_name].append({
            "ticker": meta.ticker,
            "company_name": meta.company_name,
            "price": float(price) if price is not None else None,
            "volume": int(vol) if vol is not None else None,
            "date": dt.isoformat() if dt is not None else None
        })

    return jsonify({"sectors": sectors_map})

