"""Retrieval service: ChromaDB semantic search + SQLite summary lookup."""
from sqlalchemy.orm import Session
from ..models.database import SessionLocal
from ..models.stock import AnalysisCache, InvestmentSummary
from .memory import build_memory_context as _chroma_build_context


def build_context_prompt(
    stock_code: str,
    user_message: str = "",
    max_items: int = 5,
) -> str:
    """Build a context string by combining ChromaDB semantic search + latest summary."""
    parts = []

    # 1. ChromaDB semantic retrieval
    chroma_context = _chroma_build_context(stock_code, user_message, max_items)
    if chroma_context:
        parts.append(chroma_context)

    # 2. Latest investment summary from SQLite
    db = SessionLocal()
    try:
        latest_summary = (
            db.query(InvestmentSummary)
            .filter(InvestmentSummary.stock_code == stock_code)
            .order_by(InvestmentSummary.created_at.desc())
            .first()
        )
        if latest_summary and latest_summary.summary:
            parts.append(f"## 投资日志摘要\n{latest_summary.summary}")

        # 3. Recent analysis count
        count = (
            db.query(AnalysisCache)
            .filter(AnalysisCache.stock_code == stock_code)
            .count()
        )
        if count > 0:
            parts.insert(0, f"## 历史分析统计\n该股票已进行 {count} 次分析")
    finally:
        db.close()

    return "\n\n".join(parts) if parts else ""
