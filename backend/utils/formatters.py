"""Data formatting helpers."""
import pandas as pd


def ohlcv_to_table(df: pd.DataFrame, n: int = 10) -> str:
    """Format last N OHLCV rows as a plain-text table for Claude prompts."""
    recent = df.tail(n).copy()
    lines = ["Date            | Open     | High     | Low      | Close    | Volume"]
    lines.append("-" * 75)
    for idx, row in recent.iterrows():
        date_str = str(idx)[:10] if hasattr(idx, "__str__") else str(idx)
        lines.append(
            f"{date_str:<16}| {row['Open']:<9.2f}| {row['High']:<9.2f}"
            f"| {row['Low']:<9.2f}| {row['Close']:<9.2f}| {int(row['Volume'])}"
        )
    return "\n".join(lines)


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def format_pct(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"
