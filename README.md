# Blackice AI Trading System

A paper trading system powered by Claude AI (claude-sonnet-4-6). Analyzes market data using technical indicators and generates BUY/SELL/HOLD signals with detailed reasoning. No real money involved.

## Stack

- **Backend**: Python + FastAPI + SQLAlchemy (SQLite) + Anthropic SDK + yfinance
- **Frontend**: React + TypeScript + Vite + Tailwind CSS + lightweight-charts

## Features

- AI-powered trading signals via Claude API
- Real-time price updates via WebSocket
- Paper trading engine with position management
- Risk controls: stop-loss, take-profit, drawdown guard, Kelly position sizing
- Strategy backtesting with historical replay
- Live dashboard with candlestick charts
- Portfolio tracking with equity curve and performance metrics

## Setup

### 1. Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

## API Docs

FastAPI auto-generates docs at: `http://localhost:8000/docs`

## Architecture

```
backend/
├── main.py              # FastAPI app entry point
├── core/                # Config, database session
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── api/endpoints/       # REST API endpoints
├── api/websocket.py     # WebSocket + price monitor
├── services/
│   ├── claude_agent.py  # Claude API integration
│   ├── market_data.py   # yfinance wrapper
│   ├── paper_trading.py # Order execution engine
│   ├── backtesting.py   # Historical replay engine
│   └── risk_manager.py  # Position sizing + metrics
└── utils/
    ├── indicators.py    # RSI, MACD, Bollinger, EMA, ATR
    └── formatters.py    # Data formatting helpers

frontend/src/
├── pages/               # Dashboard, Portfolio, Backtesting, TradeHistory
├── components/          # Charts, trading UI, common components
├── store/               # Zustand state management
├── hooks/               # useWebSocket
└── api/                 # Axios API client
```

## Usage

1. Open the dashboard at `http://localhost:3000`
2. Select a symbol and click **AI Analyze** to get a Claude-powered signal
3. Use **AI Auto-Trade** to let Claude analyze and execute automatically
4. Place manual orders via the Trade Panel
5. Set stop-loss / take-profit on the Portfolio page
6. Run backtests on the Backtesting page to test strategies historically
7. Review trade reasoning in Trade History

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Your Anthropic API key |
| `INITIAL_BALANCE` | 100000 | Starting paper balance ($) |
| `MAX_POSITION_PCT` | 0.20 | Max portfolio % per position |
| `MAX_DRAWDOWN_THRESHOLD` | 0.15 | Halt trading at 15% drawdown |
| `CLAUDE_CALLS_PER_MINUTE` | 10 | Rate limit for backtesting |
| `PRICE_MONITOR_INTERVAL` | 15 | Live price refresh (seconds) |
