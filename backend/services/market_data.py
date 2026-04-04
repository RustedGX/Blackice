"""Market data service using yfinance."""
import asyncio
from datetime import datetime
from functools import lru_cache

import pandas as pd
import yfinance as yf


def _fetch_ticker_info(symbol: str) -> dict:
    ticker = yf.Ticker(symbol)
    info = ticker.info
    hist = ticker.history(period="2d", interval="1d")
    if hist.empty:
        raise ValueError(f"No data found for symbol: {symbol}")
    current_price = float(hist["Close"].iloc[-1])
    prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current_price
    day_change = current_price - prev_close
    day_change_pct = (day_change / prev_close * 100) if prev_close else 0.0
    return {
        "symbol": symbol.upper(),
        "current_price": current_price,
        "prev_close": prev_close,
        "day_change": round(day_change, 4),
        "day_change_pct": round(day_change_pct, 4),
        "volume": int(hist["Volume"].iloc[-1]) if not hist.empty else 0,
        "market_cap": info.get("marketCap"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "avg_volume": info.get("averageVolume"),
        "name": info.get("longName") or info.get("shortName") or symbol,
        "currency": info.get("currency", "USD"),
    }


def _fetch_ohlcv(symbol: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No OHLCV data found for symbol: {symbol}")
    df.index = pd.to_datetime(df.index)
    return df[["Open", "High", "Low", "Close", "Volume"]].copy()


async def get_quote(symbol: str) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_ticker_info, symbol)


async def get_ohlcv(
    symbol: str, period: str = "3mo", interval: str = "1d"
) -> pd.DataFrame:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_ohlcv, symbol, period, interval)


async def get_current_price(symbol: str) -> float:
    quote = await get_quote(symbol)
    return quote["current_price"]


def ohlcv_to_list(df: pd.DataFrame) -> list[dict]:
    """Convert OHLCV DataFrame to list of dicts for JSON serialization."""
    records = []
    for ts, row in df.iterrows():
        records.append(
            {
                "time": int(ts.timestamp()) if hasattr(ts, "timestamp") else str(ts)[:10],
                "date": str(ts)[:10],
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(row["Volume"]),
            }
        )
    return records
