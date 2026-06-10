"""知股 - AI投研助手 FastAPI Backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .api.routes import router, wechat_router
from .models.database import init_db
from .config import APP_TITLE, APP_VERSION, CORS_ORIGINS
import os

app = FastAPI(title=APP_TITLE, version=APP_VERSION)

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

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"app": APP_TITLE, "version": APP_VERSION}
