from datetime import datetime, date
from pydantic import BaseModel


class BacktestIn(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    initial_balance: float = 100000.0
    portfolio_id: int = 1
    signal_every_n_bars: int = 5
    max_position_pct: float = 0.20


class BacktestOut(BaseModel):
    id: int
    portfolio_id: int
    symbol: str
    start_date: date
    end_date: date
    initial_balance: float
    final_balance: float | None
    total_trades: int | None
    winning_trades: int | None
    max_drawdown: float | None
    sharpe_ratio: float | None
    total_return: float | None
    win_rate: float | None
    status: str
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class BacktestResultOut(BacktestOut):
    results_json: str | None = None
