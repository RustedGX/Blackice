from fastapi import APIRouter

from backend.api.endpoints import portfolio, trades, market, signals, backtest, risk

api_router = APIRouter(prefix="/api")
api_router.include_router(portfolio.router)
api_router.include_router(trades.router)
api_router.include_router(market.router)
api_router.include_router(signals.router)
api_router.include_router(backtest.router)
api_router.include_router(risk.router)
