"""Summarizer: generates rolling investment log summaries via LLM."""
import os
from curl_cffi import requests
from sqlalchemy.orm import Session
from ..models.database import SessionLocal
from ..models.stock import AnalysisCache, InvestmentSummary
from ..config import SUMMARY_INTERVAL, DEEPSEEK_API_KEY

def _get_recent_analyses(stock_code: str, count: int) -> list[dict]:
    db = SessionLocal()
    try:
        records = (
            db.query(AnalysisCache)
            .filter(AnalysisCache.stock_code == stock_code)
            .order_by(AnalysisCache.created_at.desc())
            .limit(count)
            .all()
        )
        return [{"date": r.created_at.strftime("%Y-%m-%d") if r.created_at else "",
                 "content": r.content} for r in reversed(records)]
    finally:
        db.close()

def should_summarize(stock_code: str) -> bool:
    db = SessionLocal()
    try:
        total = db.query(AnalysisCache).filter(
            AnalysisCache.stock_code == stock_code
        ).count()
        summarized = db.query(InvestmentSummary).filter(
            InvestmentSummary.stock_code == stock_code
        ).count()
        total_summarized = summarized * SUMMARY_INTERVAL
        return (total - total_summarized) >= SUMMARY_INTERVAL
    finally:
        db.close()

def generate_summary(stock_code: str, stock_name: str) -> str:
    if not DEEPSEEK_API_KEY:
        return ""
    analyses = _get_recent_analyses(stock_code, SUMMARY_INTERVAL)
    if len(analyses) < 3:
        return ""
    joined = "\n---\n".join([
        f"[{a['date']}] {a['content'][:500]}" for a in analyses
    ])
    prompt = f"请根据以下{len(analyses)}次对{stock_name}({stock_code})的AI投研分析记录，生成一段200字以内的投资日志摘要。要求：提取关键趋势变化、重复出现的信号、以及最重要的结论。用中文输出。\n\n分析记录：\n{joined}\n\n投资日志摘要："
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 400,
            },
            timeout=60,
        )
        data = resp.json()
        if "choices" in data and len(data["choices"]) > 0:
            summary = data["choices"][0]["message"]["content"].strip()
            _save_summary(stock_code, stock_name, summary, len(analyses))
            return summary
    except Exception:
        pass
    return ""

def _save_summary(stock_code: str, stock_name: str, summary: str, count: int):
    db = SessionLocal()
    try:
        record = InvestmentSummary(
            stock_code=stock_code,
            stock_name=stock_name,
            summary=summary,
            source_count=count,
        )
        db.add(record)
        db.commit()
    finally:
        db.close()
