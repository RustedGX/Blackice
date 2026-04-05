"""
Blackice Paper Trading Agent
─────────────────────────────
Autonomous agent that tests the Blackice trading system with $20,000 in paper
money.  It cycles through a watchlist, requests Claude AI signals via the
backend API, executes auto-trades, tracks performance, and logs everything to
agents/trading_log.jsonl.

Usage
-----
    python -m agents.paper_trader                # run with defaults
    python -m agents.paper_trader --cycles 10    # run 10 cycles then exit
    python -m agents.paper_trader --interval 60  # 60-second cycle interval
    python -m agents.paper_trader --balance 20000 --dry-run   # no trades

Environment
-----------
    BLACKICE_API  - base URL of the running backend (default: http://localhost:8000)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

# ── Configuration ────────────────────────────────────────────────────────────

BASE_URL = os.getenv("BLACKICE_API", "http://localhost:8000")
LOG_FILE = Path(__file__).parent / "trading_log.jsonl"
REPORT_FILE = Path(__file__).parent / "session_report.json"

STARTING_BALANCE = 20_000.0

# Symbols to trade — diversified across sectors
WATCHLIST = [
    "AAPL",   # Technology – Apple
    "MSFT",   # Technology – Microsoft
    "NVDA",   # AI/Semiconductors – Nvidia
    "TSLA",   # EV / Growth – Tesla
    "AMZN",   # Consumer / Cloud – Amazon
    "GOOGL",  # Advertising / AI – Alphabet
    "META",   # Social Media / AI – Meta
    "JPM",    # Finance – JPMorgan
    "XOM",    # Energy – ExxonMobil
    "SPY",    # S&P 500 ETF (broad market)
]

# Maximum capital to risk per symbol (% of starting balance)
MAX_POSITION_PCT = 0.08   # 8 % per symbol → max 10 positions = 80 % deployed

# ── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("paper_trader")


# ── Helpers ──────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_log(record: dict[str, Any]) -> None:
    record.setdefault("ts", _now())
    with LOG_FILE.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def _fmt_currency(v: float) -> str:
    return f"${v:,.2f}"


def _fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


# ── API Client ───────────────────────────────────────────────────────────────

class BlackiceClient:
    """Thin async wrapper around the Blackice REST API."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> bool:
        try:
            r = await self._client.get(f"{self._base}/health")
            return r.status_code == 200
        except Exception:
            return False

    async def reset_portfolio(self, balance: float) -> dict:
        r = await self._client.post(
            f"{self._base}/api/portfolio/reset",
            params={"initial_balance": balance},
        )
        r.raise_for_status()
        return r.json()

    async def get_portfolio(self) -> dict:
        r = await self._client.get(f"{self._base}/api/portfolio")
        r.raise_for_status()
        return r.json()

    async def get_performance(self) -> dict:
        r = await self._client.get(f"{self._base}/api/portfolio/performance")
        r.raise_for_status()
        return r.json()

    async def get_positions(self) -> list[dict]:
        r = await self._client.get(f"{self._base}/api/portfolio/positions")
        r.raise_for_status()
        return r.json()

    async def get_risk_metrics(self) -> dict:
        r = await self._client.get(f"{self._base}/api/risk/metrics")
        r.raise_for_status()
        return r.json()

    async def auto_trade(self, symbol: str, max_position_pct: float = MAX_POSITION_PCT) -> dict:
        r = await self._client.post(
            f"{self._base}/api/signals/auto-trade",
            json={"symbol": symbol, "max_position_pct": max_position_pct, "portfolio_id": 1},
        )
        r.raise_for_status()
        return r.json()

    async def analyze(self, symbol: str) -> dict:
        r = await self._client.post(
            f"{self._base}/api/signals/analyze",
            json={"symbol": symbol, "portfolio_id": 1},
        )
        r.raise_for_status()
        return r.json()

    async def get_trades(self, limit: int = 100) -> list[dict]:
        r = await self._client.get(f"{self._base}/api/trades", params={"limit": limit})
        r.raise_for_status()
        return r.json()


# ── Agent ────────────────────────────────────────────────────────────────────

class PaperTradingAgent:
    """
    Autonomous paper trading agent.

    Each cycle:
      1. Fetches portfolio state & risk metrics
      2. Checks max-drawdown guard (halts trading if exceeded)
      3. For each symbol in the watchlist, calls /api/signals/auto-trade
      4. Prints a summary table
      5. Sleeps until the next cycle
    """

    def __init__(
        self,
        client: BlackiceClient,
        starting_balance: float = STARTING_BALANCE,
        max_cycles: int | None = None,
        interval: float = 300.0,   # seconds between cycles
        dry_run: bool = False,
        max_drawdown_pct: float = 15.0,
    ):
        self._c = client
        self.starting_balance = starting_balance
        self.max_cycles = max_cycles
        self.interval = interval
        self.dry_run = dry_run
        self.max_drawdown_pct = max_drawdown_pct

        self.cycle_count = 0
        self.session_start = _now()
        self.halted = False

        # Track per-cycle snapshots for the session report
        self.snapshots: list[dict] = []

    # ── Setup ────────────────────────────────────────────────────────────────

    async def setup(self) -> None:
        log.info("=" * 60)
        log.info("  BLACKICE PAPER TRADING AGENT")
        log.info(f"  Starting balance : {_fmt_currency(self.starting_balance)}")
        log.info(f"  Watchlist        : {', '.join(WATCHLIST)}")
        log.info(f"  Max position     : {MAX_POSITION_PCT*100:.0f}% per symbol")
        log.info(f"  Cycle interval   : {self.interval}s")
        log.info(f"  Dry run          : {self.dry_run}")
        log.info("=" * 60)

        log.info("Checking backend health …")
        if not await self._c.health():
            log.error(f"Backend not reachable at {BASE_URL}. Start uvicorn first.")
            sys.exit(1)
        log.info("Backend is healthy.")

        if not self.dry_run:
            log.info(f"Resetting portfolio to {_fmt_currency(self.starting_balance)} …")
            result = await self._c.reset_portfolio(self.starting_balance)
            log.info(f"Portfolio reset: {result}")
            _write_log({"event": "portfolio_reset", "balance": result.get("balance")})

    # ── Cycle ────────────────────────────────────────────────────────────────

    async def run_cycle(self) -> None:
        self.cycle_count += 1
        log.info("")
        log.info(f"━━━  CYCLE {self.cycle_count}  ━━━  {_now()}")

        # 1. Portfolio snapshot
        portfolio = await self._c.get_portfolio()
        cash = portfolio["cash_balance"]
        total = portfolio["total_value"]
        pnl = total - self.starting_balance
        pnl_pct = pnl / self.starting_balance * 100

        log.info(
            f"Portfolio  cash={_fmt_currency(cash)}  "
            f"total={_fmt_currency(total)}  "
            f"P&L={_fmt_currency(pnl)} ({_fmt_pct(pnl_pct)})"
        )

        # 2. Drawdown guard
        try:
            metrics = await self._c.get_risk_metrics()
            dd = metrics.get("max_drawdown", 0.0)
            if dd >= self.max_drawdown_pct:
                log.warning(
                    f"MAX DRAWDOWN EXCEEDED: {dd:.1f}% >= {self.max_drawdown_pct:.1f}%. "
                    "Halting new trades for this cycle."
                )
                self.halted = True
                _write_log({"event": "drawdown_halt", "drawdown_pct": dd})
            else:
                self.halted = False
        except Exception as exc:
            log.warning(f"Could not fetch risk metrics: {exc}")

        # 3. Snapshot
        self.snapshots.append({
            "cycle": self.cycle_count,
            "ts": _now(),
            "cash": cash,
            "total": total,
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

        if self.halted:
            log.info("Trading halted this cycle — monitoring only.")
            return

        # 4. Work through watchlist
        results: list[dict] = []
        for symbol in WATCHLIST:
            result = await self._trade_symbol(symbol)
            results.append(result)
            # Small delay to avoid hammering the Claude API rate limit
            await asyncio.sleep(2)

        # 5. Print cycle summary table
        self._print_cycle_summary(results)

    async def _trade_symbol(self, symbol: str) -> dict:
        """Request an auto-trade signal for one symbol."""
        entry: dict[str, Any] = {"symbol": symbol, "ts": _now()}
        try:
            if self.dry_run:
                analysis = await self._c.analyze(symbol)
                signal = analysis.get("signal", "N/A")
                confidence = analysis.get("confidence", 0.0)
                entry.update({"action": "DRY_RUN", "signal": signal, "confidence": confidence})
                log.info(f"  {symbol:6s} signal={signal:4s}  confidence={confidence:.0%}  (dry-run, no trade)")
            else:
                result = await self._c.auto_trade(symbol, MAX_POSITION_PCT)
                signal = result.get("signal", "N/A")
                confidence = result.get("confidence", 0.0)
                trade = result.get("trade")
                action = "NO_TRADE"

                if trade:
                    side = trade.get("side", "?")
                    qty = trade.get("quantity", 0)
                    price = trade.get("price", 0)
                    action = f"{side} {qty}@{_fmt_currency(price)}"
                    log.info(
                        f"  {symbol:6s} signal={signal:4s}  conf={confidence:.0%}  "
                        f"→ TRADED {side} {qty} @ {_fmt_currency(price)}"
                    )
                else:
                    log.info(
                        f"  {symbol:6s} signal={signal:4s}  conf={confidence:.0%}  "
                        f"→ {result.get('message', 'no trade')}"
                    )

                entry.update({
                    "signal": signal,
                    "confidence": confidence,
                    "action": action,
                    "trade": trade,
                })

        except httpx.HTTPStatusError as exc:
            log.warning(f"  {symbol:6s} API error: {exc.response.status_code} {exc.response.text[:120]}")
            entry["error"] = str(exc)
        except Exception as exc:
            log.warning(f"  {symbol:6s} Error: {exc}")
            entry["error"] = str(exc)

        _write_log({"event": "symbol_processed", **entry})
        return entry

    def _print_cycle_summary(self, results: list[dict]) -> None:
        buys = sum(1 for r in results if "BUY" in r.get("action", ""))
        sells = sum(1 for r in results if "SELL" in r.get("action", ""))
        holds = sum(1 for r in results if r.get("signal") == "HOLD")
        errors = sum(1 for r in results if "error" in r)
        log.info(
            f"  Cycle summary — BUY:{buys}  SELL:{sells}  HOLD:{holds}  ERRORS:{errors}"
        )

    # ── Report ───────────────────────────────────────────────────────────────

    async def save_report(self) -> None:
        try:
            portfolio = await self._c.get_portfolio()
            perf = await self._c.get_performance()
            trades = await self._c.get_trades()
            positions = await self._c.get_positions()
        except Exception as exc:
            log.warning(f"Could not fetch final state for report: {exc}")
            portfolio = perf = trades = positions = {}

        report = {
            "session_start": self.session_start,
            "session_end": _now(),
            "cycles_run": self.cycle_count,
            "starting_balance": self.starting_balance,
            "final_portfolio": portfolio,
            "performance": perf,
            "open_positions": positions,
            "total_trades": len(trades) if isinstance(trades, list) else 0,
            "snapshots": self.snapshots,
        }

        with REPORT_FILE.open("w") as fh:
            json.dump(report, fh, indent=2, default=str)

        # Final P&L
        if isinstance(portfolio, dict):
            total = portfolio.get("total_value", self.starting_balance)
            pnl = total - self.starting_balance
            pnl_pct = pnl / self.starting_balance * 100
            log.info("")
            log.info("═" * 60)
            log.info("  SESSION COMPLETE")
            log.info(f"  Cycles run      : {self.cycle_count}")
            log.info(f"  Starting balance: {_fmt_currency(self.starting_balance)}")
            log.info(f"  Final value     : {_fmt_currency(total)}")
            log.info(f"  Total P&L       : {_fmt_currency(pnl)} ({_fmt_pct(pnl_pct)})")
            if isinstance(perf, dict):
                log.info(f"  Max drawdown    : {perf.get('max_drawdown', 0):.2f}%")
                log.info(f"  Sharpe ratio    : {perf.get('sharpe_ratio', 0):.2f}")
                log.info(f"  Win rate        : {perf.get('win_rate', 0):.1f}%")
                log.info(f"  Total trades    : {perf.get('total_trades', 0)}")
            log.info(f"  Report saved    : {REPORT_FILE}")
            log.info("═" * 60)

        _write_log({"event": "session_end", "cycles": self.cycle_count, "report": str(REPORT_FILE)})

    # ── Main loop ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        await self.setup()

        try:
            while True:
                cycle_start = time.monotonic()
                await self.run_cycle()

                if self.max_cycles and self.cycle_count >= self.max_cycles:
                    log.info(f"Reached max_cycles={self.max_cycles}. Stopping.")
                    break

                # Sleep for the remainder of the interval
                elapsed = time.monotonic() - cycle_start
                sleep_for = max(0.0, self.interval - elapsed)
                if sleep_for > 0:
                    log.info(f"Next cycle in {sleep_for:.0f}s …")
                    await asyncio.sleep(sleep_for)

        except KeyboardInterrupt:
            log.info("\nInterrupted by user.")
        finally:
            await self.save_report()
            await self._c.close()


# ── Entry point ──────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Blackice autonomous paper trading agent ($20k starting balance)"
    )
    p.add_argument(
        "--balance", type=float, default=STARTING_BALANCE,
        help=f"Starting paper-money balance (default: {STARTING_BALANCE:,.0f})",
    )
    p.add_argument(
        "--cycles", type=int, default=None,
        help="Number of trading cycles to run before exiting (default: infinite)",
    )
    p.add_argument(
        "--interval", type=float, default=300.0,
        help="Seconds between cycles (default: 300 = 5 min)",
    )
    p.add_argument(
        "--max-drawdown", type=float, default=15.0,
        help="Halt trading if drawdown exceeds this %% (default: 15)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Analyse symbols but do not execute trades",
    )
    p.add_argument(
        "--api", type=str, default=BASE_URL,
        help=f"Blackice backend URL (default: {BASE_URL})",
    )
    return p.parse_args()


async def main() -> None:
    args = parse_args()
    client = BlackiceClient(args.api)
    agent = PaperTradingAgent(
        client=client,
        starting_balance=args.balance,
        max_cycles=args.cycles,
        interval=args.interval,
        dry_run=args.dry_run,
        max_drawdown_pct=args.max_drawdown,
    )
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
