from datetime import datetime
from pydantic import BaseModel


class PositionOut(BaseModel):
    id: int
    portfolio_id: int
    symbol: str
    quantity: float
    avg_entry_price: float
    current_price: float
    unrealized_pnl: float
    realized_pnl: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime
    updated_at: datetime
    market_value: float = 0.0
    pnl_pct: float = 0.0

    model_config = {"from_attributes": True}


class PortfolioOut(BaseModel):
    id: int
    name: str
    initial_balance: float
    cash_balance: float
    total_value: float
    positions: list[PositionOut] = []
    created_at: datetime
    updated_at: datetime
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0

    model_config = {"from_attributes": True}


class PerformancePoint(BaseModel):
    timestamp: str
    value: float
    drawdown: float


class PerformanceOut(BaseModel):
    equity_curve: list[PerformancePoint]
    total_return: float
    total_return_pct: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    total_trades: int
    winning_trades: int


class RiskControlsIn(BaseModel):
    stop_loss: float | None = None
    take_profit: float | None = None
