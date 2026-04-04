"""Paper trading engine: order execution, position management, SL/TP monitoring."""
import asyncio
import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.config import settings
from backend.models.portfolio import Portfolio, Position
from backend.models.trade import Trade
from backend.models.signal import Signal

logger = logging.getLogger(__name__)


async def get_or_create_portfolio(db: AsyncSession, portfolio_id: int = 1) -> Portfolio:
    result = await db.execute(select(Portfolio).where(Portfolio.id == portfolio_id))
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        portfolio = Portfolio(
            id=portfolio_id,
            name="Default",
            initial_balance=settings.initial_balance,
            cash_balance=settings.initial_balance,
            total_value=settings.initial_balance,
        )
        db.add(portfolio)
        await db.flush()
    return portfolio


async def place_order(
    db: AsyncSession,
    portfolio_id: int,
    symbol: str,
    side: str,  # BUY | SELL
    quantity: float,
    price: float | None = None,
    signal_id: int | None = None,
    current_price_override: float | None = None,
) -> tuple[Trade, float]:
    """
    Execute a paper market order.
    Returns (Trade, executed_price).
    """
    from backend.services.market_data import get_current_price

    portfolio = await get_or_create_portfolio(db, portfolio_id)

    # Determine execution price
    if price is not None:
        exec_price = price
    elif current_price_override is not None:
        exec_price = current_price_override
    else:
        exec_price = await get_current_price(symbol)

    # Apply slippage
    if side == "BUY":
        exec_price *= (1 + settings.slippage_pct)
    else:
        exec_price *= (1 - settings.slippage_pct)

    exec_price = round(exec_price, 4)
    total_value = round(exec_price * quantity, 4)

    if side == "BUY":
        if total_value > portfolio.cash_balance:
            raise ValueError(
                f"Insufficient cash: need ${total_value:.2f}, have ${portfolio.cash_balance:.2f}"
            )
        portfolio.cash_balance = round(portfolio.cash_balance - total_value, 4)
        pnl = None
        await _update_position_buy(db, portfolio_id, symbol, quantity, exec_price)

    elif side == "SELL":
        pnl = await _close_position(db, portfolio_id, symbol, quantity, exec_price)
        portfolio.cash_balance = round(portfolio.cash_balance + total_value, 4)

    else:
        raise ValueError(f"Invalid side: {side}. Must be BUY or SELL.")

    # Recalculate total portfolio value
    positions = await _get_positions(db, portfolio_id)
    position_value = sum(p.quantity * exec_price for p in positions if p.symbol == symbol)
    for p in positions:
        if p.symbol != symbol:
            position_value += p.quantity * p.current_price
    portfolio.total_value = round(portfolio.cash_balance + position_value, 4)
    portfolio.updated_at = datetime.utcnow()

    trade = Trade(
        portfolio_id=portfolio_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=exec_price,
        total_value=total_value,
        status="FILLED",
        signal_id=signal_id,
        pnl=pnl,
        executed_at=datetime.utcnow(),
    )
    db.add(trade)
    await db.flush()
    return trade, exec_price


async def _update_position_buy(
    db: AsyncSession,
    portfolio_id: int,
    symbol: str,
    quantity: float,
    price: float,
) -> Position:
    result = await db.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id, Position.symbol == symbol
        )
    )
    position = result.scalar_one_or_none()
    if position is None:
        position = Position(
            portfolio_id=portfolio_id,
            symbol=symbol,
            quantity=quantity,
            avg_entry_price=price,
            current_price=price,
            unrealized_pnl=0.0,
        )
        db.add(position)
    else:
        # Weighted average entry price
        total_cost = position.avg_entry_price * position.quantity + price * quantity
        position.quantity += quantity
        position.avg_entry_price = round(total_cost / position.quantity, 4)
        position.current_price = price
        position.unrealized_pnl = round(
            (price - position.avg_entry_price) * position.quantity, 4
        )
        position.updated_at = datetime.utcnow()
    return position


async def _close_position(
    db: AsyncSession,
    portfolio_id: int,
    symbol: str,
    quantity: float,
    price: float,
) -> float:
    """Close (or reduce) a position. Returns realized PnL."""
    result = await db.execute(
        select(Position).where(
            Position.portfolio_id == portfolio_id, Position.symbol == symbol
        )
    )
    position = result.scalar_one_or_none()
    if position is None or position.quantity < quantity:
        raise ValueError(
            f"Cannot sell {quantity} shares of {symbol}: "
            f"position has {position.quantity if position else 0} shares"
        )

    pnl = round((price - position.avg_entry_price) * quantity, 4)
    position.realized_pnl = round(position.realized_pnl + pnl, 4)

    if abs(position.quantity - quantity) < 0.0001:
        await db.delete(position)
    else:
        position.quantity = round(position.quantity - quantity, 8)
        position.current_price = price
        position.unrealized_pnl = round(
            (price - position.avg_entry_price) * position.quantity, 4
        )
        position.updated_at = datetime.utcnow()

    return pnl


async def _get_positions(db: AsyncSession, portfolio_id: int) -> list[Position]:
    result = await db.execute(
        select(Position).where(Position.portfolio_id == portfolio_id)
    )
    return list(result.scalars().all())


async def update_position_prices(
    db: AsyncSession,
    portfolio_id: int,
    prices: dict[str, float],
) -> Portfolio:
    """Update current_price and unrealized_pnl for all positions, then recalc total_value."""
    portfolio = await get_or_create_portfolio(db, portfolio_id)
    positions = await _get_positions(db, portfolio_id)

    position_value = 0.0
    for position in positions:
        price = prices.get(position.symbol, position.current_price)
        position.current_price = price
        position.unrealized_pnl = round(
            (price - position.avg_entry_price) * position.quantity, 4
        )
        position.updated_at = datetime.utcnow()
        position_value += position.quantity * price

    portfolio.total_value = round(portfolio.cash_balance + position_value, 4)
    portfolio.updated_at = datetime.utcnow()
    return portfolio


async def check_stop_loss_take_profit(
    db: AsyncSession,
    portfolio_id: int,
    ws_manager=None,
) -> list[Trade]:
    """Check all positions for SL/TP triggers. Auto-sell if triggered."""
    from backend.services.market_data import get_current_price

    positions = await _get_positions(db, portfolio_id)
    executed_trades = []

    for position in positions:
        if position.stop_loss is None and position.take_profit is None:
            continue
        try:
            current = await get_current_price(position.symbol)
        except Exception as e:
            logger.warning(f"Could not fetch price for {position.symbol}: {e}")
            continue

        triggered = False
        reason = ""
        if position.stop_loss and current <= position.stop_loss:
            triggered = True
            reason = f"Stop-loss triggered at ${current:.2f} (limit: ${position.stop_loss:.2f})"
        elif position.take_profit and current >= position.take_profit:
            triggered = True
            reason = f"Take-profit triggered at ${current:.2f} (limit: ${position.take_profit:.2f})"

        if triggered:
            logger.info(f"Auto-selling {position.symbol}: {reason}")
            try:
                trade, exec_price = await place_order(
                    db,
                    portfolio_id,
                    position.symbol,
                    "SELL",
                    position.quantity,
                    current_price_override=current,
                )
                executed_trades.append(trade)
                await db.commit()
                if ws_manager:
                    await ws_manager.broadcast(
                        {
                            "type": "trade_executed",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {
                                "symbol": position.symbol,
                                "side": "SELL",
                                "quantity": position.quantity,
                                "price": exec_price,
                                "reason": reason,
                            },
                        }
                    )
            except Exception as e:
                logger.error(f"Failed to auto-sell {position.symbol}: {e}")

    return executed_trades
