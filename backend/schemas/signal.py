from datetime import datetime
from pydantic import BaseModel


class AnalyzeIn(BaseModel):
    symbol: str
    include_news: bool = False
    portfolio_id: int = 1


class AutoTradeIn(BaseModel):
    symbol: str
    max_position_pct: float = 0.10
    portfolio_id: int = 1


class SignalOut(BaseModel):
    id: int
    portfolio_id: int
    symbol: str
    signal: str
    confidence: float
    reasoning: str
    key_factors: str | None
    risk_assessment: str
    suggested_entry: float | None
    suggested_stop_loss: float | None
    suggested_take_profit: float | None
    suggested_position_size_pct: float | None
    time_horizon: str | None
    sentiment_score: float | None
    price_at_signal: float
    created_at: datetime

    model_config = {"from_attributes": True}
