from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.core.database import get_db
from backend.models.trade import Trade
from backend.models.signal import Signal
from backend.schemas.trade import OrderIn, TradeOut
from backend.services.paper_trading import place_order

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("", response_model=list[TradeOut])
async def list_trades(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    symbol: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Trade).where(Trade.portfolio_id == 1).order_by(desc(Trade.executed_at))
    if symbol:
        query = query.where(Trade.symbol == symbol.upper())
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{trade_id}", response_model=TradeOut)
async def get_trade(trade_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Trade).where(Trade.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.post("/order", response_model=TradeOut)
async def place_paper_order(order: OrderIn, db: AsyncSession = Depends(get_db)):
    try:
        trade, exec_price = await place_order(
            db,
            portfolio_id=1,
            symbol=order.symbol.upper(),
            side=order.side.upper(),
            quantity=order.quantity,
            price=order.price,
        )
        await db.commit()
        return trade
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Order failed: {str(e)}")
