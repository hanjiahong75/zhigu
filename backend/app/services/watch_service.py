"""Thread watch (盯盘) service (M5).

Registers per-thread stock watches, periodically evaluates quotes + strategy
signals, and pushes "⚠ 实时更新" advice updates into the conversation via SSE.
"""

import asyncio
import json
import time
from typing import Dict, Optional, Set

from curl_cffi import requests

from ..config import QUOTE_POLL_INTERVAL_SECONDS, DEEPSEEK_API_KEY
from ..models.database import SessionLocal
from ..models.stock import ChatThreadWatch, ChatMessage
from .stock_data import get_batch_quotes, get_realtime_quote
from .signal_service import compute_signal

MAX_WATCHES_PER_THREAD = 5
PRICE_TRIGGER_PCT = 0.02
SIGNAL_REFRESH_SECONDS = 300
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

_broker: Optional["ThreadEventBroker"] = None
_monitor: Optional["WatchMonitor"] = None


def get_thread_broker() -> "ThreadEventBroker":
    global _broker
    if _broker is None:
        _broker = ThreadEventBroker()
    return _broker


def get_watch_monitor() -> "WatchMonitor":
    global _monitor
    if _monitor is None:
        _monitor = WatchMonitor()
    return _monitor


class ThreadEventBroker:
    """Per-thread pub/sub channel for realtime conversation events."""

    def __init__(self) -> None:
        self._subs: Dict[str, Set[asyncio.Queue]] = {}

    def subscribe(self, thread_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=50)
        self._subs.setdefault(thread_id, set()).add(q)
        return q

    def unsubscribe(self, thread_id: str, q: asyncio.Queue) -> None:
        subs = self._subs.get(thread_id)
        if subs:
            subs.discard(q)
            if not subs:
                self._subs.pop(thread_id, None)

    def publish(self, thread_id: str, event: dict) -> None:
        for q in list(self._subs.get(thread_id, set())):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass


# -- DB helpers ----------------------------------------------------------
def register_watch(thread_id: str, code: str, market: str = "sz", name: str = "") -> dict:
    """Register a stock for the thread's watch list (idempotent, max 5)."""
    db = SessionLocal()
    try:
        count = db.query(ChatThreadWatch).filter(ChatThreadWatch.thread_id == thread_id).count()
        if count >= MAX_WATCHES_PER_THREAD:
            return {"error": f"每个对话最多盯盘 {MAX_WATCHES_PER_THREAD} 只股票"}
        row = db.query(ChatThreadWatch).filter_by(thread_id=thread_id, code=code).first()
        if not row:
            row = ChatThreadWatch(thread_id=thread_id, code=code, market=market, name=name)
            db.add(row)
        else:
            row.market = market or row.market
            row.name = name or row.name
        db.commit()
        db.refresh(row)
        return {"id": row.id, "thread_id": row.thread_id, "code": row.code,
                "name": row.name, "market": row.market}
    finally:
        db.close()


def list_watches(thread_id: str) -> list:
    db = SessionLocal()
    try:
        rows = db.query(ChatThreadWatch).filter_by(thread_id=thread_id).all()
        return [{
            "id": r.id, "thread_id": r.thread_id, "code": r.code,
            "name": r.name, "market": r.market,
            "last_rating": r.last_rating, "last_price": r.last_price,
            "last_signal_ts": r.last_signal_ts or 0,
        } for r in rows]
    finally:
        db.close()


def delete_watch(thread_id: str, code: str) -> bool:
    db = SessionLocal()
    try:
        row = db.query(ChatThreadWatch).filter_by(thread_id=thread_id, code=code).first()
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


# -- Advice generation -----------------------------------------------------
def _rule_text(watch: ChatThreadWatch, quote: dict, signal: dict,
               old_rating: str, new_rating: str) -> str:
    parts = [f"{watch.name or watch.code}（{watch.code}）盯盘提醒"]
    if new_rating != old_rating:
        parts.append(f"建议由【{old_rating}】变为【{new_rating}】")
    else:
        parts.append(f"建议维持【{new_rating}】")
    if signal and "error" not in signal and signal.get("components"):
        top = sorted(signal["components"], key=lambda c: abs(c.get("score", 0)), reverse=True)[0]
        parts.append(f"主要依据：{top.get('detail', '')}")
    price = (quote or {}).get("price")
    chg = (quote or {}).get("change_pct")
    if price:
        parts.append(f"最新价 {price}" + (f"（{chg:+.2f}%）" if chg is not None else ""))
    return "；".join(parts) + "。"


def _polish_advice(old_rating: str, new_rating: str, quote: dict,
                   signal: dict, rule_text: str) -> str:
    """Short LLM polish (1~2 sentences); falls back to rule text on failure."""
    if not DEEPSEEK_API_KEY:
        return rule_text
    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "你是知股投研助手。用1~2句简洁、专业的中文给出盯盘建议更新，包含风险提示，不要重复规则文本的格式。"},
                    {"role": "user", "content": json.dumps({
                        "旧建议": old_rating, "新信号": new_rating,
                        "行情": quote, "信号": signal, "规则文本": rule_text,
                    }, ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "max_tokens": 150,
                "stream": False,
            },
            timeout=20,
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        return content or rule_text
    except Exception:
        return rule_text


class WatchMonitor:
    """Background loop evaluating watches and pushing advice updates."""

    def __init__(self, interval_seconds: int = QUOTE_POLL_INTERVAL_SECONDS) -> None:
        self._interval = max(3, int(interval_seconds))
        self._task: Optional[asyncio.Task] = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    def set_interval(self, seconds: int) -> None:
        self._interval = max(3, min(60, int(seconds)))

    async def _loop(self) -> None:
        while True:
            try:
                await self._tick()
            except Exception:
                pass
            await asyncio.sleep(self._interval)

    async def _tick(self) -> None:
        db = SessionLocal()
        try:
            rows = db.query(ChatThreadWatch).all()
            if not rows:
                return
            codes = sorted({r.code for r in rows})
            quotes = await asyncio.to_thread(get_batch_quotes, codes)
            now = time.time()
            for r in rows:
                q = quotes.get(r.code)
                if not q:
                    continue
                price = float(q.get("price") or 0)
                triggered = False
                if r.last_price and price and abs(price - r.last_price) / r.last_price >= PRICE_TRIGGER_PCT:
                    triggered = True
                signal = None
                if triggered or (now - (r.last_signal_ts or 0)) >= SIGNAL_REFRESH_SECONDS:
                    signal = await asyncio.to_thread(compute_signal, r.code, r.market)
                    r.last_signal_ts = now
                    if signal and "error" not in signal and signal["rating"] != r.last_rating:
                        triggered = True
                if triggered and price:
                    await self._emit_update(db, r, q, signal, price)
            db.commit()
        finally:
            db.close()

    async def refresh_now(self, thread_id: str, code: str) -> dict:
        """Manual refresh: re-evaluate one watch and emit an update."""
        db = SessionLocal()
        try:
            row = db.query(ChatThreadWatch).filter_by(thread_id=thread_id, code=code).first()
            if not row:
                return {"error": "该股票不在盯盘列表中"}
            quote = await asyncio.to_thread(get_realtime_quote, row.code, row.market)
            signal = await asyncio.to_thread(compute_signal, row.code, row.market)
            if not quote:
                return {"error": "行情获取失败，请稍后再试"}
            price = float(quote.get("price") or 0)
            await self._emit_update(db, row, quote, signal, price)
            db.commit()
            return {"ok": True}
        finally:
            db.close()

    async def _emit_update(self, db, watch: ChatThreadWatch, quote: dict,
                           signal: dict, price: float) -> None:
        old_rating = watch.last_rating or "观望"
        new_rating = (signal or {}).get("rating") or old_rating
        rule = _rule_text(watch, quote, signal, old_rating, new_rating)
        content = await asyncio.to_thread(_polish_advice, old_rating, new_rating, quote, signal, rule)

        stock_data = {
            "stock_code": watch.code,
            "stock_name": watch.name or watch.code,
            "market": watch.market,
            "quote": quote,
            "source": "realtime",
            "signal_update": {
                "old_rating": old_rating,
                "new_rating": new_rating,
                "reason": rule,
                "ts": int(time.time()),
            },
        }
        db.add(ChatMessage(
            thread_id=watch.thread_id,
            role="assistant",
            content=content,
            stock_code=watch.code,
            stock_name=watch.name or watch.code,
            stock_data=json.dumps(stock_data, ensure_ascii=False),
        ))
        watch.last_rating = new_rating
        watch.last_price = price
        watch.last_signal_ts = time.time()

        get_thread_broker().publish(watch.thread_id, {
            "type": "advice_update",
            "code": watch.code,
            "name": watch.name or watch.code,
            "old_rating": old_rating,
            "new_rating": new_rating,
            "content": content,
            "ts": int(time.time()),
        })
