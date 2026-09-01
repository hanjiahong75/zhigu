"""知股 - AI投研助手 FastAPI Backend."""
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api.routes import router, wechat_router
from .models.database import init_db
from .config import APP_TITLE, APP_VERSION, CORS_ORIGINS
from .services.quote_poller import get_quote_poller
from .services.watch_service import get_watch_monitor
import asyncio
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    poller = get_quote_poller()
    poller.start()
    monitor = get_watch_monitor()
    monitor.start()

    async def _warmup():
        """Prefetch slow first-load endpoints so the first visitor hits a warm cache."""
        try:
            from .services.stock_data import (
                get_fund_recommendations, get_news, get_market_indices,
            )
            from .services.global_data import get_global_indices
            await asyncio.to_thread(get_fund_recommendations)
            await asyncio.to_thread(get_news, 1, 20)
            await asyncio.to_thread(get_global_indices)
            await asyncio.to_thread(get_market_indices)
        except Exception:
            pass

    asyncio.create_task(_warmup())
    try:
        yield
    finally:
        await poller.stop()
        await monitor.stop()


app = FastAPI(title=APP_TITLE, version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("data/uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")

app.include_router(router)
app.include_router(wechat_router)  # Phase 5: WeChat webhook (no /api prefix)

@app.get("/")
def root():
    return {"app": APP_TITLE, "version": APP_VERSION}
