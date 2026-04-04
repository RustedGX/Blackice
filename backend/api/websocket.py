"""WebSocket connection manager and price monitor background task."""
import asyncio
import json
import logging
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, client_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket client connected: {client_id}")

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        logger.info(f"WebSocket client disconnected: {client_id}")

    async def broadcast(self, message: dict):
        dead = []
        for client_id, ws in list(self.active_connections.items()):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(client_id)
        for c in dead:
            self.disconnect(c)

    async def send_to(self, client_id: str, message: dict):
        ws = self.active_connections.get(client_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(client_id)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(client_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back with timestamp (client can send ping)
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await manager.send_to(client_id, {"type": "pong", "timestamp": datetime.utcnow().isoformat()})
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(client_id)


_monitored_symbols: set[str] = set()
_price_monitor_task: asyncio.Task | None = None


def register_symbol(symbol: str):
    _monitored_symbols.add(symbol.upper())


def unregister_symbol(symbol: str):
    _monitored_symbols.discard(symbol.upper())


async def price_monitor_loop(db_factory, interval_seconds: int = 15):
    """Background task: fetch live prices and broadcast portfolio updates."""
    from backend.services.market_data import get_current_price
    from backend.services.paper_trading import update_position_prices, get_or_create_portfolio
    from sqlalchemy import select
    from backend.models.portfolio import Position

    while True:
        await asyncio.sleep(interval_seconds)
        if not manager.active_connections:
            continue

        try:
            async with db_factory() as db:
                result = await db.execute(select(Position))
                positions = list(result.scalars().all())
                symbols = {p.symbol for p in positions}

            price_updates: dict[str, float] = {}
            for symbol in symbols:
                try:
                    price = await get_current_price(symbol)
                    price_updates[symbol] = price
                except Exception as e:
                    logger.warning(f"Price fetch failed for {symbol}: {e}")

            if price_updates:
                # Broadcast price updates
                await manager.broadcast({
                    "type": "price_update",
                    "timestamp": datetime.utcnow().isoformat(),
                    "data": price_updates,
                })

                # Update portfolio positions in DB
                async with db_factory() as db:
                    portfolio = await update_position_prices(db, 1, price_updates)
                    await db.commit()
                    await manager.broadcast({
                        "type": "portfolio_update",
                        "timestamp": datetime.utcnow().isoformat(),
                        "data": {
                            "cash_balance": portfolio.cash_balance,
                            "total_value": portfolio.total_value,
                        },
                    })

        except Exception as e:
            logger.error(f"Price monitor error: {e}", exc_info=True)
