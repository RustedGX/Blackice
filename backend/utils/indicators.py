"""Technical indicator calculations using pandas/numpy."""
import numpy as np
import pandas as pd


def calculate_rsi(close: pd.Series, period: int = 14) -> float:
    """Relative Strength Index."""
    if len(close) < period + 1:
        return 50.0
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return round(float(val) if not np.isnan(val) else 50.0, 2)


def calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    """MACD line, signal line, and histogram."""
    if len(close) < slow:
        return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd": round(float(macd_line.iloc[-1]), 4),
        "signal": round(float(signal_line.iloc[-1]), 4),
        "histogram": round(float(histogram.iloc[-1]), 4),
    }


def calculate_bollinger_bands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> dict:
    """Bollinger Bands: upper, middle, lower."""
    if len(close) < period:
        price = float(close.iloc[-1])
        return {"upper": price, "middle": price, "lower": price}
    rolling_mean = close.rolling(window=period).mean()
    rolling_std = close.rolling(window=period).std()
    upper = rolling_mean + (rolling_std * std_dev)
    lower = rolling_mean - (rolling_std * std_dev)
    return {
        "upper": round(float(upper.iloc[-1]), 4),
        "middle": round(float(rolling_mean.iloc[-1]), 4),
        "lower": round(float(lower.iloc[-1]), 4),
    }


def calculate_ema(close: pd.Series, period: int) -> float:
    """Exponential Moving Average."""
    if len(close) < period:
        return round(float(close.iloc[-1]), 4)
    ema = close.ewm(span=period, adjust=False).mean()
    return round(float(ema.iloc[-1]), 4)


def calculate_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> float:
    """Average True Range."""
    if len(close) < 2:
        return 0.0
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(com=period - 1, min_periods=period).mean()
    val = atr.iloc[-1]
    return round(float(val) if not np.isnan(val) else 0.0, 4)


def calculate_volume_ratio(volume: pd.Series, period: int = 20) -> float:
    """Current volume vs N-period average."""
    if len(volume) < period:
        return 1.0
    avg = volume.rolling(window=period).mean().iloc[-1]
    current = volume.iloc[-1]
    if avg == 0:
        return 1.0
    return round(float(current / avg), 2)


def get_all_indicators(df: pd.DataFrame) -> dict:
    """
    Compute all indicators from an OHLCV DataFrame.
    Required columns: Open, High, Low, Close, Volume
    """
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    macd = calculate_macd(close)
    bb = calculate_bollinger_bands(close)

    return {
        "rsi_14": calculate_rsi(close),
        "macd_line": macd["macd"],
        "macd_signal": macd["signal"],
        "macd_histogram": macd["histogram"],
        "bb_upper": bb["upper"],
        "bb_middle": bb["middle"],
        "bb_lower": bb["lower"],
        "ema_20": calculate_ema(close, 20),
        "ema_50": calculate_ema(close, 50),
        "atr_14": calculate_atr(high, low, close),
        "volume_ratio": calculate_volume_ratio(volume),
    }
