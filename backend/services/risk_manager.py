"""Risk management: position sizing, drawdown guard, metrics."""
import math
import numpy as np
import pandas as pd

from backend.core.config import settings


def calculate_position_size(
    confidence: float,
    current_price: float,
    cash_balance: float,
    total_value: float,
    max_position_pct: float | None = None,
    stop_loss_pct: float = 0.05,
) -> dict:
    """
    Kelly Criterion simplified position sizing.
    Returns quantity to buy and dollar value.
    """
    max_pct = max_position_pct or settings.max_position_pct

    # Simplified Kelly: f = confidence - (1 - confidence) / (1 / stop_loss_pct - 1)
    win_pct = confidence
    loss_pct = stop_loss_pct
    reward_ratio = 1.5  # Assume 1.5:1 reward/risk
    kelly_fraction = (win_pct * reward_ratio - (1 - win_pct)) / reward_ratio

    # Cap at max position percent, floor at 0
    kelly_fraction = max(0.0, min(kelly_fraction, max_pct))

    position_value = kelly_fraction * total_value
    # Also cap by available cash
    position_value = min(position_value, cash_balance * 0.98)
    quantity = math.floor(position_value / current_price) if current_price > 0 else 0

    return {
        "quantity": quantity,
        "position_value": round(quantity * current_price, 2),
        "position_pct": round((quantity * current_price) / total_value * 100, 2) if total_value else 0,
        "kelly_fraction": round(kelly_fraction, 4),
    }


def calculate_metrics(trades: list[dict], equity_curve: list[float]) -> dict:
    """
    Calculate portfolio performance metrics.
    trades: list of {pnl: float}
    equity_curve: list of portfolio values over time
    """
    if not equity_curve:
        return _empty_metrics()

    # Total return
    initial = equity_curve[0]
    final = equity_curve[-1]
    total_return = final - initial
    total_return_pct = (total_return / initial * 100) if initial else 0.0

    # Max drawdown
    peak = equity_curve[0]
    max_dd = 0.0
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak else 0
        if dd > max_dd:
            max_dd = dd

    # Sharpe ratio (annualized, assuming daily bars)
    if len(equity_curve) > 1:
        returns = pd.Series(equity_curve).pct_change().dropna()
        if returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * math.sqrt(252)
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    # Win rate
    pnl_list = [t.get("pnl", 0) or 0 for t in trades if t.get("pnl") is not None]
    total_t = len(pnl_list)
    winning_t = sum(1 for p in pnl_list if p > 0)
    win_rate = (winning_t / total_t * 100) if total_t else 0.0

    # VaR (95%, parametric)
    if len(equity_curve) > 1:
        rets = pd.Series(equity_curve).pct_change().dropna()
        var_95 = float(np.percentile(rets, 5)) * final if len(rets) > 0 else 0.0
    else:
        var_95 = 0.0

    return {
        "total_return": round(total_return, 2),
        "total_return_pct": round(total_return_pct, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 4),
        "win_rate": round(win_rate, 2),
        "total_trades": total_t,
        "winning_trades": winning_t,
        "var_95": round(var_95, 2),
    }


def is_drawdown_exceeded(equity_curve: list[float]) -> bool:
    """Return True if current drawdown from peak exceeds the configured threshold."""
    if len(equity_curve) < 2:
        return False
    peak = max(equity_curve)
    current = equity_curve[-1]
    drawdown = (peak - current) / peak if peak else 0
    return drawdown >= settings.max_drawdown_threshold


def _empty_metrics() -> dict:
    return {
        "total_return": 0.0,
        "total_return_pct": 0.0,
        "max_drawdown": 0.0,
        "sharpe_ratio": 0.0,
        "win_rate": 0.0,
        "total_trades": 0,
        "winning_trades": 0,
        "var_95": 0.0,
    }
