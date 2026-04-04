import asyncio
import logging

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.database import create_tables
from backend.api.router import api_router
from backend.api.websocket import websocket_endpoint, price_monitor_loop, manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Blackice AI Trading System",
    description="Paper trading system powered by Claude AI",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.websocket("/ws/{client_id}")
async def ws_endpoint(websocket: WebSocket, client_id: str):
    await websocket_endpoint(websocket, client_id)


@app.on_event("startup")
async def startup():
    logger.info("Creating database tables...")
    await create_tables()

    from backend.core.database import AsyncSessionLocal
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def db_factory():
        async with AsyncSessionLocal() as session:
            yield session

    logger.info("Starting price monitor background task...")
    asyncio.create_task(
        price_monitor_loop(db_factory, interval_seconds=settings.price_monitor_interval)
    )
    logger.info("Blackice backend started successfully.")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Blackice AI Trading System"}
