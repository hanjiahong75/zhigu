"""Application configuration."""
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
APP_TITLE = "知股 - AI投研助手"
APP_VERSION = "0.1.0"
CORS_ORIGINS = ["http://localhost:5174", "http://127.0.0.1:5174", "http://zhigu.local:5174", "https://zhigu.local:5174", "https://localhost:5174"]

# Phase 5: WeChat integration
WECHAT_WEBHOOK_API_KEY = os.getenv("WECHAT_WEBHOOK_API_KEY", "")
CHAT_TIMEOUT_SECONDS = int(os.getenv("CHAT_TIMEOUT_SECONDS", "25"))
MAX_HISTORY_PAIRS = int(os.getenv("MAX_HISTORY_PAIRS", "10"))
LOG_DIR = os.getenv("LOG_DIR", str(Path(__file__).resolve().parent.parent / "logs"))

# Phase 1: Memory system
SUMMARY_INTERVAL = int(os.getenv("SUMMARY_INTERVAL", "10"))
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", str(Path(__file__).resolve().parent.parent / "chroma_db"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "stock_analyses")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")


def setup_wechat_logging() -> logging.Logger:
    """Setup dedicated logger for WeChat webhook debugging."""
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("wechat")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        fh = logging.FileHandler(os.path.join(LOG_DIR, "wechat.log"), encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(fh)
    return logger

