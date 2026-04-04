"""Backtesting engine: bar-by-bar historical replay with Claude signals."""
import asyncio
import json
import logging
import time
from datetime import datetime

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.backtest import Backtest
from backend.services.market_data import get_ohlcv
from backend.services.risk_manager import calculate_metrics, is_drawdown_exceeded
from backend.utils.indicators import get_all_indicators, calculate_rsi, calculate_macd

logger = logging.getLogger(__name__)


class BacktestPosition:
    def __init__(self):
        self.symbol = ""
        self.quantity = 0.0
        self.avg_entry_price = 0.0
        self.stop_loss: float | None = None
        self.take_profit: float | None = None


async def run_backtest(
    backtest_id: int,
    symbol: str,
    start_date: str,
    end_date: str,
    initial_balance: float,
    signal_every_n_bars: int,
    max_position_pct: float,
    ws_manager=None,
    db_factory=None,
) -> None:
    """Run a backtest in a background task, updating the DB record as it progresses."""
    logger.info(f"Starting backtest {backtest_id} for {symbol} {start_date} to {end_date}")

    async def update_backtest(status: str, **kwargs):
        if db_factory is None:
            return
        async with db_factory() as db:
            result = await db.execute(
                __import__("sqlalchemy", fromlist=["select"]).select(Backtest).where(
                    Backtest.id == backtest_id
                )
            )
            bt = result.scalar_one_or_none()
            if bt:
                bt.status = status
                for k, v in kwargs.items():
                    setattr(bt, k, v)
                await db.commit()

    try:
        # Fetch historical data
        period = _compute_period(start_date, end_date)
        df = await get_ohlcv(symbol, period=period, interval="1d")

        # Filter to date range
        df.index = pd.to_datetime(df.index).tz_localize(None)
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]

        if len(df) < 10:
            await update_backtest("FAILED", error_message="Insufficient data for date range")
            return

        # Initialize simulation state
        cash = initial_balance
        position = BacktestPosition()
        equity_curve = [initial_balance]
        trades: list[dict] = []
        total_bars = len(df)
        last_claude_call_time = 0.0
        min_call_interval = 60.0 / settings.claude_calls_per_minute

        for bar_idx, (ts, row) in enumerate(df.iterrows()):
            close = float(row["Close"])

            # Check stop-loss / take-profit
            if position.quantity > 0:
                if position.stop_loss and close <= position.stop_loss:
                    pnl = (close - position.avg_entry_price) * position.quantity
                    cash += close * position.quantity
                    trades.append({"side": "SELL", "price": close, "pnl": round(pnl, 2), "reason": "stop_loss"})
                    position = BacktestPosition()
                elif position.take_profit and close >= position.take_profit:
                    pnl = (close - position.avg_entry_price) * position.quantity
                    cash += close * position.quantity
                    trades.append({"side": "SELL", "price": close, "pnl": round(pnl, 2), "reason": "take_profit"})
                    position = BacktestPosition()

            # Update equity
            position_value = position.quantity * close if position.quantity > 0 else 0.0
            total_value = cash + position_value
            equity_curve.append(round(total_value, 2))

            # Generate signal every N bars
            if bar_idx > 0 and bar_idx % signal_every_n_bars == 0 and bar_idx < total_bars - 1:
                historical_slice = df.iloc[: bar_idx + 1]
                signal_data = _get_technical_signal(historical_slice, close)

                # Try Claude if rate limit allows
                try:
                    now = time.time()
                    if now - last_claude_call_time >= min_call_interval:
                        from backend.services.claude_agent import get_trading_signal
                        from backend.services.market_data import ohlcv_to_list

                        portfolio_context = {
                            "cash_balance": cash,
                            "total_value": total_value,
                            "position_qty": position.quantity,
                            "position_avg": position.avg_entry_price,
                            "risk_pct": (position_value / total_value * 100) if total_value else 0,
                        }
                        quote = {
                            "current_price": close,
                            "day_change_pct": 0,
                            "volume": int(row["Volume"]),
                            "avg_volume": None,
                            "fifty_two_week_high": None,
                            "fifty_two_week_low": None,
                        }
                        result = await get_trading_signal(
                            symbol, historical_slice, quote, portfolio_context
                        )
                        signal_data = {
                            "signal": result.get("signal", "HOLD"),
                            "confidence": result.get("confidence", 0.5),
                            "suggested_stop_loss": result.get("suggested_stop_loss"),
                            "suggested_take_profit": result.get("suggested_take_profit"),
                        }
                        last_claude_call_time = time.time()
                except Exception as e:
                    logger.warning(f"Claude call failed in backtest, using technical signal: {e}")

                # Execute signal on NEXT bar open to avoid lookahead bias
                if bar_idx + 1 < len(df):
                    next_open = float(df.iloc[bar_idx + 1]["Open"])
                    sig = signal_data["signal"]
                    conf = signal_data.get("confidence", 0.5)

                    if sig == "BUY" and position.quantity == 0 and not is_drawdown_exceeded(equity_curve):
                        position_value_to_buy = min(
                            cash * max_position_pct, cash * 0.98
                        )
                        qty = position_value_to_buy / next_open
                        if qty >= 0.001:
                            cost = qty * next_open
                            cash -= cost
                            position.symbol = symbol
                            position.quantity = qty
                            position.avg_entry_price = next_open
                            position.stop_loss = signal_data.get("suggested_stop_loss")
                            position.take_profit = signal_data.get("suggested_take_profit")
                            trades.append({"side": "BUY", "price": next_open, "pnl": None, "reason": "signal"})

                    elif sig == "SELL" and position.quantity > 0:
                        pnl = (next_open - position.avg_entry_price) * position.quantity
                        cash += next_open * position.quantity
                        trades.append({"side": "SELL", "price": next_open, "pnl": round(pnl, 2), "reason": "signal"})
                        position = BacktestPosition()

            # Broadcast progress
            if ws_manager and bar_idx % 10 == 0:
                progress = round(bar_idx / total_bars * 100, 1)
                await ws_manager.broadcast({
                    "type": "backtest_progress",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": {"backtest_id": backtest_id, "progress": progress, "bar": bar_idx, "total": total_bars},
                })

        # Close remaining position at last close
        if position.quantity > 0:
            last_close = float(df["Close"].iloc[-1])
            pnl = (last_close - position.avg_entry_price) * position.quantity
            cash += last_close * position.quantity
            trades.append({"side": "SELL", "price": last_close, "pnl": round(pnl, 2), "reason": "end_of_backtest"})
            equity_curve.append(round(cash, 2))

        final_balance = round(cash, 2)
        metrics = calculate_metrics(trades, equity_curve)

        results_payload = {
            "equity_curve": equity_curve,
            "trades": trades,
        }

        await update_backtest(
            "COMPLETE",
            final_balance=final_balance,
            total_trades=metrics["total_trades"],
            winning_trades=metrics["winning_trades"],
            max_drawdown=metrics["max_drawdown"],
            sharpe_ratio=metrics["sharpe_ratio"],
            total_return=metrics["total_return_pct"],
            win_rate=metrics["win_rate"],
            results_json=json.dumps(results_payload),
            completed_at=datetime.utcnow(),
        )

        if ws_manager:
            await ws_manager.broadcast({
                "type": "backtest_progress",
                "timestamp": datetime.utcnow().isoformat(),
                "data": {"backtest_id": backtest_id, "progress": 100, "status": "COMPLETE", "metrics": metrics},
            })

        logger.info(f"Backtest {backtest_id} complete. Return: {metrics['total_return_pct']:.2f}%")

    except Exception as e:
        logger.error(f"Backtest {backtest_id} failed: {e}", exc_info=True)
        await update_backtest("FAILED", error_message=str(e))


def _get_technical_signal(df: pd.DataFrame, current_price: float) -> dict:
    """Fallback: RSI + MACD crossover signal when Claude is rate-limited."""
    close = df["Close"]
    rsi = calculate_rsi(close)
    macd = calculate_macd(close)

    signal = "HOLD"
    confidence = 0.5

    if rsi < 35 and macd["histogram"] > 0:
        signal = "BUY"
        confidence = 0.65
    elif rsi > 65 and macd["histogram"] < 0:
        signal = "SELL"
        confidence = 0.65

    return {"signal": signal, "confidence": confidence, "suggested_stop_loss": None, "suggested_take_profit": None}


def _compute_period(start_date: str, end_date: str) -> str:
    """Compute a yfinance period string that covers the date range."""
    from datetime import date
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    days = (end - start).days
    if days <= 30:
        return "1mo"
    elif days <= 90:
        return "3mo"
    elif days <= 180:
        return "6mo"
    elif days <= 365:
        return "1y"
    elif days <= 730:
        return "2y"
    else:
        return "5y"
