"""FastAPI application factory."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import CORS_ORIGINS
from src.api.routes import account, candles, positions, strategy, trades
from src.api.ws import periodic_account_broadcast, router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(periodic_account_broadcast())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Forex Scalper API", version="0.4.0", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(account.router)
app.include_router(positions.router)
app.include_router(trades.router)
app.include_router(candles.router)
app.include_router(strategy.router)
app.include_router(ws_router)


@app.get("/health")
def health():
    return {"status": "ok"}
