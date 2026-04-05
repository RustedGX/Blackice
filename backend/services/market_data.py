"""Market data service using yfinance, with a mock fallback for offline/sandboxed environments."""
import asyncio
import math
import random
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import pandas as pd
import yfinance as yf

# ── Realistic baseline prices (approximate real-world values) ─────────────────
_MOCK_PRICES: dict[str, float] = {
    "AAPL":  172.50,
    "MSFT":  415.30,
    "NVDA":  875.20,
    "TSLA":  175.80,
    "AMZN":  185.40,
    "GOOGL": 163.20,
    "META":  511.60,
    "JPM":   196.40,
    "XOM":    114.90,
    "SPY":   524.80,
    # Generic fallback for unknown symbols
    "_DEFAULT": 100.0,
}

# Per-symbol volatility (daily %)
_MOCK_VOLATILITY: dict[str, float] = {
    "AAPL": 0.012, "MSFT": 0.011, "NVDA": 0.030, "TSLA": 0.040,
    "AMZN": 0.016, "GOOGL": 0.014, "META": 0.022, "JPM": 0.013,
    "XOM": 0.014, "SPY": 0.009, "_DEFAULT": 0.015,
}

# Persistent simulated prices that drift over time within a session
_sim_prices: dict[str, float] = {}
_sim_last_update: dict[str, float] = {}


def _get_simulated_price(symbol: str) -> float:
    """Return a simulated price that slowly random-walks from the baseline."""
    sym = symbol.upper()
    base = _MOCK_PRICES.get(sym, _MOCK_PRICES["_DEFAULT"])
    vol = _MOCK_VOLATILITY.get(sym, _MOCK_VOLATILITY["_DEFAULT"])

    now = time.time()
    if sym not in _sim_prices:
        _sim_prices[sym] = base
        _sim_last_update[sym] = now

    # Evolve price since last call (geometric Brownian motion step)
    dt = (now - _sim_last_update[sym]) / 86400.0  # fraction of a trading day
    if dt > 0:
        drift = 0.0001  # small upward drift
        shock = random.gauss(0, 1)
        _sim_prices[sym] *= math.exp((drift - 0.5 * vol**2) * dt + vol * shock * math.sqrt(dt))
        _sim_last_update[sym] = now

    return round(_sim_prices[sym], 4)


def _mock_ticker_info(symbol: str) -> dict:
    sym = symbol.upper()
    price = _get_simulated_price(sym)
    vol = _MOCK_VOLATILITY.get(sym, 0.015)
    prev_close = round(price * (1 - random.gauss(0, vol * 0.5)), 4)
    day_change = round(price - prev_close, 4)
    day_change_pct = round((day_change / prev_close) * 100, 4) if prev_close else 0.0
    return {
        "symbol": sym,
        "current_price": price,
        "prev_close": prev_close,
        "day_change": day_change,
        "day_change_pct": day_change_pct,
        "volume": random.randint(10_000_000, 80_000_000),
        "market_cap": None,
        "fifty_two_week_high": round(price * 1.35, 2),
        "fifty_two_week_low": round(price * 0.70, 2),
        "avg_volume": 45_000_000,
        "name": sym,
        "currency": "USD",
        "_mock": True,
    }


def _mock_ohlcv(symbol: str, period: str = "3mo", interval: str = "1d") -> pd.DataFrame:
    """Generate synthetic OHLCV bars via a random walk."""
    sym = symbol.upper()
    base = _MOCK_PRICES.get(sym, _MOCK_PRICES["_DEFAULT"])
    vol = _MOCK_VOLATILITY.get(sym, 0.015)

    # Map period string to bar count
    period_days = {"1d": 1, "5d": 5, "1mo": 21, "3mo": 63, "6mo": 126,
                   "1y": 252, "2y": 504, "5y": 1260}
    n_bars = period_days.get(period, 63)
    if interval in ("1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"):
        n_bars = min(n_bars * 7, 500)  # rough intraday bars

    end = datetime.now(timezone.utc)
    freq_map = {"1d": "B", "1h": "h", "1m": "min"}
    freq = freq_map.get(interval, "B")

    idx = pd.bdate_range(end=end, periods=n_bars, freq=freq)

    price = base
    opens, highs, lows, closes, volumes = [], [], [], [], []
    rng = random.Random(hash(sym) % (2**32))  # deterministic seed per symbol

    for _ in idx:
        o = price
        daily_vol = vol * rng.gauss(1.0, 0.3)
        c = o * math.exp(rng.gauss(0.0002, daily_vol))
        h = max(o, c) * (1 + abs(rng.gauss(0, daily_vol * 0.5)))
        l = min(o, c) * (1 - abs(rng.gauss(0, daily_vol * 0.5)))
        v = int(rng.uniform(8_000_000, 60_000_000))
        opens.append(round(o, 4)); highs.append(round(h, 4))
        lows.append(round(l, 4));  closes.append(round(c, 4))
        volumes.append(v)
        price = c

    df = pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )
    return df


# ── Real implementations ──────────────────────────────────────────────────────

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


# ── Public async API ──────────────────────────────────────────────────────────

async def get_quote(symbol: str) -> dict:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _fetch_ticker_info, symbol)
    except Exception:
        # Fallback to mock data when network is unavailable
        return _mock_ticker_info(symbol)


async def get_ohlcv(
    symbol: str, period: str = "3mo", interval: str = "1d"
) -> pd.DataFrame:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _fetch_ohlcv, symbol, period, interval)
    except Exception:
        return _mock_ohlcv(symbol, period, interval)


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
