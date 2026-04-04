from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.models.trade import Trade
from backend.models.portfolio import Portfolio
from backend.services.risk_manager import calculate_metrics, calculate_position_size, is_drawdown_exceeded
from backend.services.paper_trading import get_or_create_portfolio

router = APIRouter(prefix="/risk", tags=["risk"])


@router.get("/metrics")
async def get_risk_metrics(db: AsyncSession = Depends(get_db)):
    portfolio = await get_or_create_portfolio(db, 1)
    result = await db.execute(
        select(Trade).where(Trade.portfolio_id == 1).order_by(Trade.executed_at)
    )
    trades = list(result.scalars().all())
    trade_dicts = [{"pnl": t.pnl} for t in trades]

    # Build equity curve
    equity_curve = [portfolio.initial_balance]
    running = portfolio.initial_balance
    for t in trades:
        if t.pnl is not None:
            running += t.pnl
        equity_curve.append(running)
    equity_curve.append(portfolio.total_value)

    metrics = calculate_metrics(trade_dicts, equity_curve)
    metrics["drawdown_exceeded"] = is_drawdown_exceeded(equity_curve)
    metrics["cash_balance"] = portfolio.cash_balance
    metrics["total_value"] = portfolio.total_value
    metrics["initial_balance"] = portfolio.initial_balance
    return metrics


@router.post("/position-size")
async def compute_position_size(
    symbol: str,
    confidence: float = Query(0.7, ge=0.0, le=1.0),
    max_position_pct: float = Query(0.20, ge=0.01, le=1.0),
    stop_loss_pct: float = Query(0.05, ge=0.001, le=0.50),
    db: AsyncSession = Depends(get_db),
):
    from backend.services.market_data import get_current_price
    portfolio = await get_or_create_portfolio(db, 1)
    current_price = await get_current_price(symbol.upper())
    sizing = calculate_position_size(
        confidence=confidence,
        current_price=current_price,
        cash_balance=portfolio.cash_balance,
        total_value=portfolio.total_value,
        max_position_pct=max_position_pct,
        stop_loss_pct=stop_loss_pct,
    )
    sizing["current_price"] = current_price
    sizing["symbol"] = symbol.upper()
    return sizing
