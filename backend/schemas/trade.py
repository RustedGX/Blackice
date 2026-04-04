from datetime import datetime
from pydantic import BaseModel


class OrderIn(BaseModel):
    symbol: str
    side: str  # BUY | SELL
    quantity: float
    price: float | None = None  # None = market order


class TradeOut(BaseModel):
    id: int
    portfolio_id: int
    symbol: str
    side: str
    quantity: float
    price: float
    total_value: float
    status: str
    signal_id: int | None
    pnl: float | None
    executed_at: datetime

    model_config = {"from_attributes": True}
