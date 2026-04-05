from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.database import get_db
from backend.models.portfolio import Portfolio, Position
from backend.models.trade import Trade
from backend.schemas.portfolio import PortfolioOut, PositionOut, PerformanceOut, RiskControlsIn
from backend.services.paper_trading import get_or_create_portfolio
from backend.services.risk_manager import calculate_metrics
from backend.core.config import settings

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioOut)
async def get_portfolio(db: AsyncSession = Depends(get_db)):
    portfolio = await get_or_create_portfolio(db, 1)
    result = await db.execute(select(Position).where(Position.portfolio_id == 1))
    positions = list(result.scalars().all())

    pos_out = []
    for p in positions:
        market_value = p.quantity * p.current_price
        pnl_pct = ((p.current_price - p.avg_entry_price) / p.avg_entry_price * 100) if p.avg_entry_price else 0.0
        pos_out.append(PositionOut(
            id=p.id, portfolio_id=p.portfolio_id, symbol=p.symbol,
            quantity=p.quantity, avg_entry_price=p.avg_entry_price,
            current_price=p.current_price, unrealized_pnl=p.unrealized_pnl,
            realized_pnl=p.realized_pnl, stop_loss=p.stop_loss,
            take_profit=p.take_profit, opened_at=p.opened_at, updated_at=p.updated_at,
            market_value=round(market_value, 2), pnl_pct=round(pnl_pct, 2),
        ))

    total_pnl = portfolio.total_value - portfolio.initial_balance
    total_pnl_pct = (total_pnl / portfolio.initial_balance * 100) if portfolio.initial_balance else 0

    return PortfolioOut(
        id=portfolio.id, name=portfolio.name,
        initial_balance=portfolio.initial_balance,
        cash_balance=portfolio.cash_balance,
        total_value=portfolio.total_value,
        positions=pos_out,
        created_at=portfolio.created_at, updated_at=portfolio.updated_at,
        total_pnl=round(total_pnl, 2), total_pnl_pct=round(total_pnl_pct, 2),
    )


@router.get("/positions", response_model=list[PositionOut])
async def get_positions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Position).where(Position.portfolio_id == 1))
    positions = list(result.scalars().all())
    out = []
    for p in positions:
        market_value = p.quantity * p.current_price
        pnl_pct = ((p.current_price - p.avg_entry_price) / p.avg_entry_price * 100) if p.avg_entry_price else 0.0
        out.append(PositionOut(
            id=p.id, portfolio_id=p.portfolio_id, symbol=p.symbol,
            quantity=p.quantity, avg_entry_price=p.avg_entry_price,
            current_price=p.current_price, unrealized_pnl=p.unrealized_pnl,
            realized_pnl=p.realized_pnl, stop_loss=p.stop_loss,
            take_profit=p.take_profit, opened_at=p.opened_at, updated_at=p.updated_at,
            market_value=round(market_value, 2), pnl_pct=round(pnl_pct, 2),
        ))
    return out


@router.get("/performance", response_model=PerformanceOut)
async def get_performance(db: AsyncSession = Depends(get_db)):
    portfolio = await get_or_create_portfolio(db, 1)
    result = await db.execute(
        select(Trade).where(Trade.portfolio_id == 1).order_by(Trade.executed_at)
    )
    trades = list(result.scalars().all())

    trade_dicts = [{"pnl": t.pnl} for t in trades]

    # Build simple equity curve from trades
    equity_curve = [portfolio.initial_balance]
    running = portfolio.initial_balance
    equity_points = []
    for t in trades:
        if t.pnl is not None:
            running += t.pnl
        equity_curve.append(running)
        equity_points.append({
            "timestamp": t.executed_at.isoformat(),
            "value": round(running, 2),
            "drawdown": 0.0,
        })

    # Add current value as last point
    equity_curve.append(portfolio.total_value)
    equity_points.append({
        "timestamp": portfolio.updated_at.isoformat(),
        "value": portfolio.total_value,
        "drawdown": 0.0,
    })

    # Calculate drawdown per point
    peak = portfolio.initial_balance
    for i, pt in enumerate(equity_points):
        if pt["value"] > peak:
            peak = pt["value"]
        dd = (peak - pt["value"]) / peak * 100 if peak else 0
        equity_points[i]["drawdown"] = round(dd, 2)

    metrics = calculate_metrics(trade_dicts, equity_curve)

    return PerformanceOut(
        equity_curve=equity_points,
        total_return=metrics["total_return"],
        total_return_pct=metrics["total_return_pct"],
        max_drawdown=metrics["max_drawdown"],
        sharpe_ratio=metrics["sharpe_ratio"],
        win_rate=metrics["win_rate"],
        total_trades=metrics["total_trades"],
        winning_trades=metrics["winning_trades"],
    )


@router.post("/reset")
async def reset_portfolio(
    initial_balance: float | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Reset portfolio to initial balance (wipes all positions and trades).

    Optionally pass `initial_balance` as a query param to override the default.
    Example: POST /api/portfolio/reset?initial_balance=20000
    """
    balance = initial_balance if initial_balance and initial_balance > 0 else settings.initial_balance

    result = await db.execute(select(Portfolio).where(Portfolio.id == 1))
    portfolio = result.scalar_one_or_none()

    from sqlalchemy import delete as sa_delete
    await db.execute(sa_delete(Position).where(Position.portfolio_id == 1))
    await db.execute(sa_delete(Trade).where(Trade.portfolio_id == 1))

    if portfolio:
        portfolio.initial_balance = balance
        portfolio.cash_balance = balance
        portfolio.total_value = balance
    else:
        portfolio = Portfolio(
            id=1, name="Default",
            initial_balance=balance,
            cash_balance=balance,
            total_value=balance,
        )
        db.add(portfolio)

    await db.commit()
    return {"message": "Portfolio reset successfully", "balance": balance}


@router.post("/positions/{position_id}/controls")
async def set_risk_controls(
    position_id: int,
    controls: RiskControlsIn,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Position).where(Position.id == position_id))
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    position.stop_loss = controls.stop_loss
    position.take_profit = controls.take_profit
    return {"message": "Risk controls updated", "stop_loss": controls.stop_loss, "take_profit": controls.take_profit}
