from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.core.database import get_db, AsyncSessionLocal
from backend.models.backtest import Backtest
from backend.schemas.backtest import BacktestIn, BacktestOut, BacktestResultOut
from backend.services.paper_trading import get_or_create_portfolio
from backend.api.websocket import manager

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestOut, status_code=202)
async def start_backtest(
    body: BacktestIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    await get_or_create_portfolio(db, body.portfolio_id)

    bt = Backtest(
        portfolio_id=body.portfolio_id,
        symbol=body.symbol.upper(),
        start_date=body.start_date,
        end_date=body.end_date,
        initial_balance=body.initial_balance,
        status="RUNNING",
    )
    db.add(bt)
    await db.commit()
    await db.refresh(bt)

    from backend.services.backtesting import run_backtest
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def db_factory():
        async with AsyncSessionLocal() as session:
            yield session

    background_tasks.add_task(
        run_backtest,
        backtest_id=bt.id,
        symbol=body.symbol.upper(),
        start_date=str(body.start_date),
        end_date=str(body.end_date),
        initial_balance=body.initial_balance,
        signal_every_n_bars=body.signal_every_n_bars,
        max_position_pct=body.max_position_pct,
        ws_manager=manager,
        db_factory=db_factory,
    )
    return bt


@router.get("", response_model=list[BacktestOut])
async def list_backtests(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Backtest).where(Backtest.portfolio_id == 1).order_by(desc(Backtest.created_at))
    )
    return list(result.scalars().all())


@router.get("/{backtest_id}", response_model=BacktestResultOut)
async def get_backtest(backtest_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Backtest).where(Backtest.id == backtest_id))
    bt = result.scalar_one_or_none()
    if not bt:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return bt


@router.delete("/{backtest_id}")
async def delete_backtest(backtest_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Backtest).where(Backtest.id == backtest_id))
    bt = result.scalar_one_or_none()
    if not bt:
        raise HTTPException(status_code=404, detail="Backtest not found")
    await db.delete(bt)
    return {"message": "Backtest deleted"}
