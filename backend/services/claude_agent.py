"""Claude AI agent for trading signal generation."""
import json
import logging
from datetime import datetime

import anthropic
import pandas as pd

from backend.core.config import settings
from backend.utils.indicators import get_all_indicators
from backend.utils.formatters import ohlcv_to_table

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a quantitative trading analyst for Blackice, a paper trading system.
You analyze market data and produce structured trading signals.
You must respond with valid JSON only. No prose outside the JSON object.
You are trading with simulated money. Be analytical, disciplined, and precise.
Consider technical indicators, price action, volume, and portfolio risk when making decisions.
"""

SIGNAL_PROMPT_TEMPLATE = """Analyze the following market data for {symbol} and produce a trading signal.

## Current Market Snapshot
- Symbol: {symbol}
- Current Price: ${current_price}
- Day Change: {day_change_pct}%
- 52-Week High: ${high_52w}
- 52-Week Low: ${low_52w}
- Volume (today): {volume:,}
- Avg Volume (20d): {avg_volume}

## Technical Indicators
- RSI (14): {rsi_14}
- MACD Line: {macd_line} | Signal: {macd_signal} | Histogram: {macd_histogram}
- Bollinger Bands: Upper {bb_upper} | Mid {bb_middle} | Lower {bb_lower}
- EMA 20: {ema_20}
- EMA 50: {ema_50}
- ATR (14): {atr_14}
- Volume Ratio (vs 20d avg): {volume_ratio}x

## Recent OHLCV (last 10 bars)
{ohlcv_table}

## Current Portfolio Context
- Cash Available: ${cash_balance:,.2f}
- Existing Position in {symbol}: {position_qty} shares @ ${position_avg:.2f}
- Portfolio Total Value: ${total_value:,.2f}
- Current Portfolio Risk Exposure: {risk_pct:.1f}%

{news_section}

Respond with this exact JSON structure (no markdown, no extra text):
{{
  "signal": "BUY" | "SELL" | "HOLD",
  "confidence": <float 0.0-1.0>,
  "reasoning": "<detailed multi-sentence explanation>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "risk_assessment": "LOW" | "MEDIUM" | "HIGH",
  "suggested_entry": <float or null>,
  "suggested_stop_loss": <float or null>,
  "suggested_take_profit": <float or null>,
  "suggested_position_size_pct": <float 0.0-1.0 or null>,
  "time_horizon": "INTRADAY" | "SWING" | "POSITION",
  "sentiment_score": <float -1.0 to 1.0>
}}"""

SENTIMENT_PROMPT_TEMPLATE = """You are a financial news sentiment analyzer.
Given the following news headlines for {symbol}, return JSON only:
{{
  "sentiment_score": <float -1.0 to 1.0>,
  "summary": "<2-3 sentence synthesis>",
  "key_themes": ["<theme1>", "<theme2>"]
}}
Headlines:
{headlines}"""

EXPLANATION_PROMPT_TEMPLATE = """A paper trade was just executed in Blackice:
- Symbol: {symbol}
- Action: {side}
- Quantity: {quantity} shares at ${price:.2f}
- Signal Confidence: {confidence:.0%}
- Original Signal Reasoning: {reasoning}

Write a 2-3 paragraph plain-English explanation of why this trade was made,
what market conditions drove the decision, and what the exit strategy is.
Keep it educational and concise. No JSON — plain prose only."""


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _technical_signal(indicators: dict, quote: dict, position_qty: float) -> dict:
    """
    RSI + MACD rule-based signal used as fallback when Claude API is unavailable.

    Rules:
      BUY  — RSI < 40 AND MACD histogram positive (momentum turning up)
      SELL — RSI > 65 AND we hold a position AND MACD histogram negative
      HOLD — everything else
    """
    try:
        rsi = float(indicators.get("rsi_14", 50))
    except (TypeError, ValueError):
        rsi = 50.0

    try:
        macd_hist = float(indicators.get("macd_histogram", 0))
    except (TypeError, ValueError):
        macd_hist = 0.0

    price = float(quote.get("current_price", 0))

    if rsi < 40 and macd_hist > 0:
        signal = "BUY"
        confidence = round(min(0.85, 0.5 + (40 - rsi) / 100 + macd_hist / (price or 1) * 10), 2)
        reasoning = (
            f"RSI at {rsi:.1f} indicates oversold conditions. "
            f"Positive MACD histogram ({macd_hist:+.4f}) confirms upward momentum. "
            "Technical setup favours a long entry."
        )
        risk = "LOW" if rsi < 30 else "MEDIUM"
    elif rsi > 65 and macd_hist < 0 and position_qty > 0:
        signal = "SELL"
        confidence = round(min(0.85, 0.5 + (rsi - 65) / 100 + abs(macd_hist) / (price or 1) * 10), 2)
        reasoning = (
            f"RSI at {rsi:.1f} indicates overbought conditions. "
            f"Negative MACD histogram ({macd_hist:+.4f}) signals fading momentum. "
            "Exiting position to lock in gains."
        )
        risk = "LOW" if rsi > 75 else "MEDIUM"
    else:
        signal = "HOLD"
        confidence = 0.55
        reasoning = (
            f"RSI at {rsi:.1f} and MACD histogram {macd_hist:+.4f} — "
            "no clear directional edge. Holding current position."
        )
        risk = "LOW"

    sl_pct, tp_pct = 0.05, 0.10
    return {
        "signal": signal,
        "confidence": confidence,
        "reasoning": reasoning,
        "key_factors": [f"RSI={rsi:.1f}", f"MACD_hist={macd_hist:+.4f}", "Technical fallback (no API key)"],
        "risk_assessment": risk,
        "suggested_entry": round(price, 4) if signal == "BUY" else None,
        "suggested_stop_loss": round(price * (1 - sl_pct), 4) if signal == "BUY" else None,
        "suggested_take_profit": round(price * (1 + tp_pct), 4) if signal == "BUY" else None,
        "suggested_position_size_pct": 0.08 if signal != "HOLD" else None,
        "time_horizon": "SWING",
        "sentiment_score": 0.3 if signal == "BUY" else (-0.3 if signal == "SELL" else 0.0),
        "_raw_prompt": "technical_fallback",
        "_raw_response": f"RSI={rsi:.1f} MACD_hist={macd_hist:+.4f}",
        "_technical_data": json.dumps(indicators),
    }


def _parse_signal_json(raw: str) -> dict:
    """Extract and parse JSON from Claude response, with fallback."""
    text = raw.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Claude signal response as JSON, returning HOLD")
        return {
            "signal": "HOLD",
            "confidence": 0.5,
            "reasoning": "Unable to parse AI response. Defaulting to HOLD.",
            "key_factors": ["Parse error"],
            "risk_assessment": "HIGH",
            "suggested_entry": None,
            "suggested_stop_loss": None,
            "suggested_take_profit": None,
            "suggested_position_size_pct": None,
            "time_horizon": "SWING",
            "sentiment_score": 0.0,
        }


async def get_trading_signal(
    symbol: str,
    df: pd.DataFrame,
    quote: dict,
    portfolio_context: dict,
    news_headlines: list[str] | None = None,
) -> dict:
    """
    Generate a trading signal from Claude based on market data and portfolio state.
    Returns the parsed signal dict plus raw prompt/response for auditing.
    """
    import asyncio

    indicators = get_all_indicators(df)
    ohlcv_table = ohlcv_to_table(df)

    position_qty = portfolio_context.get("position_qty", 0)
    position_avg = portfolio_context.get("position_avg", 0.0)
    cash_balance = portfolio_context.get("cash_balance", 0.0)
    total_value = portfolio_context.get("total_value", 0.0)
    risk_pct = portfolio_context.get("risk_pct", 0.0)

    news_section = ""
    if news_headlines:
        news_section = f"## News Headlines\n" + "\n".join(
            f"- {h}" for h in news_headlines[:10]
        )

    user_message = SIGNAL_PROMPT_TEMPLATE.format(
        symbol=symbol,
        current_price=quote.get("current_price", 0),
        day_change_pct=quote.get("day_change_pct", 0),
        high_52w=quote.get("fifty_two_week_high") or "N/A",
        low_52w=quote.get("fifty_two_week_low") or "N/A",
        volume=quote.get("volume", 0),
        avg_volume=quote.get("avg_volume") or "N/A",
        ohlcv_table=ohlcv_table,
        position_qty=position_qty,
        position_avg=position_avg,
        cash_balance=cash_balance,
        total_value=total_value,
        risk_pct=risk_pct,
        news_section=news_section,
        **indicators,
    )

    # Use technical fallback if API key is absent
    if not settings.anthropic_api_key:
        logger.info("No ANTHROPIC_API_KEY — using RSI/MACD technical signal for %s", symbol)
        return _technical_signal(indicators, quote, position_qty)

    client = _get_client()

    def _call_api():
        return client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _call_api)
        raw_response = response.content[0].text
        parsed = _parse_signal_json(raw_response)
        parsed["_raw_prompt"] = user_message
        parsed["_raw_response"] = raw_response
        parsed["_technical_data"] = json.dumps(indicators)
        return parsed
    except Exception as exc:
        logger.warning("Claude API call failed (%s) — falling back to technical signal for %s", exc, symbol)
        return _technical_signal(indicators, quote, position_qty)


async def get_trade_explanation(
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    confidence: float,
    reasoning: str,
) -> str:
    """Generate a plain-English explanation of a trade for the history view."""
    import asyncio

    prompt = EXPLANATION_PROMPT_TEMPLATE.format(
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        confidence=confidence,
        reasoning=reasoning,
    )
    client = _get_client()

    def _call_api():
        return client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, _call_api)
    return response.content[0].text
