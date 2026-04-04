import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.core.database import get_db
from backend.models.signal import Signal
from backend.schemas.signal import AnalyzeIn, AutoTradeIn, SignalOut
from backend.services.market_data import get_quote, get_ohlcv
from backend.services.paper_trading import get_or_create_portfolio, place_order
from backend.services.risk_manager import calculate_position_size
from backend.services.claude_agent import get_trading_signal

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("/analyze", response_model=SignalOut)
async def analyze_symbol(body: AnalyzeIn, db: AsyncSession = Depends(get_db)):
    symbol = body.symbol.upper()
    try:
        quote, df, portfolio = await _gather_context(db, symbol, body.portfolio_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch market data: {str(e)}")

    try:
        result = await get_trading_signal(symbol, df, quote, portfolio)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {str(e)}")

    signal = Signal(
        portfolio_id=body.portfolio_id,
        symbol=symbol,
        signal=result.get("signal", "HOLD"),
        confidence=result.get("confidence", 0.5),
        reasoning=result.get("reasoning", ""),
        key_factors=json.dumps(result.get("key_factors", [])),
        risk_assessment=result.get("risk_assessment", "MEDIUM"),
        suggested_entry=result.get("suggested_entry"),
        suggested_stop_loss=result.get("suggested_stop_loss"),
        suggested_take_profit=result.get("suggested_take_profit"),
        suggested_position_size_pct=result.get("suggested_position_size_pct"),
        time_horizon=result.get("time_horizon"),
        sentiment_score=result.get("sentiment_score"),
        price_at_signal=quote["current_price"],
        technical_data=result.get("_technical_data"),
        raw_prompt=result.get("_raw_prompt"),
        raw_response=result.get("_raw_response"),
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)
    return signal


@router.post("/auto-trade")
async def auto_trade(body: AutoTradeIn, db: AsyncSession = Depends(get_db)):
    """Analyze a symbol and execute if signal is BUY or SELL."""
    symbol = body.symbol.upper()
    try:
        quote, df, portfolio_context = await _gather_context(db, symbol, body.portfolio_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch market data: {str(e)}")

    try:
        result = await get_trading_signal(symbol, df, quote, portfolio_context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Claude API error: {str(e)}")

    signal_val = result.get("signal", "HOLD")
    confidence = result.get("confidence", 0.5)

    signal_rec = Signal(
        portfolio_id=body.portfolio_id,
        symbol=symbol,
        signal=signal_val,
        confidence=confidence,
        reasoning=result.get("reasoning", ""),
        key_factors=json.dumps(result.get("key_factors", [])),
        risk_assessment=result.get("risk_assessment", "MEDIUM"),
        suggested_entry=result.get("suggested_entry"),
        suggested_stop_loss=result.get("suggested_stop_loss"),
        suggested_take_profit=result.get("suggested_take_profit"),
        suggested_position_size_pct=result.get("suggested_position_size_pct"),
        time_horizon=result.get("time_horizon"),
        sentiment_score=result.get("sentiment_score"),
        price_at_signal=quote["current_price"],
        technical_data=result.get("_technical_data"),
        raw_prompt=result.get("_raw_prompt"),
        raw_response=result.get("_raw_response"),
    )
    db.add(signal_rec)
    await db.flush()

    trade_result = None
    if signal_val in ("BUY", "SELL"):
        portfolio = await get_or_create_portfolio(db, body.portfolio_id)
        current_price = quote["current_price"]

        if signal_val == "BUY":
            sizing = calculate_position_size(
                confidence=confidence,
                current_price=current_price,
                cash_balance=portfolio.cash_balance,
                total_value=portfolio.total_value,
                max_position_pct=body.max_position_pct,
            )
            quantity = sizing["quantity"]
        else:
            # SELL: close existing position
            from sqlalchemy import select as sa_select
            from backend.models.portfolio import Position
            pos_result = await db.execute(
                sa_select(Position).where(
                    Position.portfolio_id == body.portfolio_id,
                    Position.symbol == symbol,
                )
            )
            pos = pos_result.scalar_one_or_none()
            quantity = pos.quantity if pos else 0

        if quantity > 0:
            try:
                trade, exec_price = await place_order(
                    db,
                    portfolio_id=body.portfolio_id,
                    symbol=symbol,
                    side=signal_val,
                    quantity=quantity,
                    signal_id=signal_rec.id,
                )
                if result.get("suggested_stop_loss") or result.get("suggested_take_profit"):
                    from backend.models.portfolio import Position
                    from sqlalchemy import select as sa_select
                    pos_result = await db.execute(
                        sa_select(Position).where(
                            Position.portfolio_id == body.portfolio_id,
                            Position.symbol == symbol,
                        )
                    )
                    pos = pos_result.scalar_one_or_none()
                    if pos:
                        pos.stop_loss = result.get("suggested_stop_loss")
                        pos.take_profit = result.get("suggested_take_profit")
                trade_result = {"trade_id": trade.id, "side": signal_val, "quantity": quantity, "price": exec_price}
            except ValueError as e:
                trade_result = {"error": str(e)}

    await db.commit()
    return {
        "signal": signal_val,
        "confidence": confidence,
        "reasoning": result.get("reasoning"),
        "trade": trade_result,
        "signal_id": signal_rec.id,
    }


@router.get("", response_model=list[SignalOut])
async def list_signals(
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    symbol: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Signal).where(Signal.portfolio_id == 1).order_by(desc(Signal.created_at))
    if symbol:
        query = query.where(Signal.symbol == symbol.upper())
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{signal_id}", response_model=SignalOut)
async def get_signal(signal_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


async def _gather_context(db, symbol: str, portfolio_id: int) -> tuple:
    from backend.services.paper_trading import get_or_create_portfolio
    from sqlalchemy import select as sa_select
    from backend.models.portfolio import Position

    quote, df, portfolio_obj = await __import__(
        "asyncio", fromlist=["gather"]
    ).gather(
        get_quote(symbol),
        get_ohlcv(symbol),
        get_or_create_portfolio(db, portfolio_id),
    )

    pos_result = await db.execute(
        sa_select(Position).where(
            Position.portfolio_id == portfolio_id, Position.symbol == symbol
        )
    )
    pos = pos_result.scalar_one_or_none()
    position_value = (pos.quantity * quote["current_price"]) if pos else 0.0
    risk_pct = (position_value / portfolio_obj.total_value * 100) if portfolio_obj.total_value else 0

    portfolio_context = {
        "cash_balance": portfolio_obj.cash_balance,
        "total_value": portfolio_obj.total_value,
        "position_qty": pos.quantity if pos else 0,
        "position_avg": pos.avg_entry_price if pos else 0.0,
        "risk_pct": round(risk_pct, 2),
    }
    return quote, df, portfolio_context
