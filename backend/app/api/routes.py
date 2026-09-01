from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..models.database import get_db, SessionLocal
from ..models.stock import WatchlistItem, AnalysisCache, ChatThread, ChatMessage, PortfolioItem, User
from ..services.stock_data import search_stocks, get_realtime_quote, get_kline_data, get_market_indices, get_intraday, get_news, search_funds, get_fund_nav, get_fund_recommendations, get_fund_holdings, get_global_indices
from ..services.ai_analysis import get_analysis, summarize_kline
from ..services.technical import calc_all_indicators
from ..services.signal_service import compute_signal
from ..services.watch_service import (
    register_watch, list_watches, delete_watch, get_watch_monitor, get_thread_broker,
)
from ..services.retrieval import build_context_prompt
from ..services.memory import store_memory
from ..services.summarizer import should_summarize, generate_summary
from ..services.chat_service import chat_full, generate_title, chat_full_stream, chat_agent, chat_agent_stream
from ..services.auth_service import create_user, authenticate_user, update_profile, change_password, get_user_by_id, create_access_token
from ..services.user_profile_service import get_or_create_profile, update_profile, build_profile_context
from ..services.global_data import (
    get_global_quote, search_global_stocks, get_global_kline,
    get_global_indicators, get_global_indices as _get_global_indices,
)
from ..services.global_symbols import search_popular
from ..services.portfolio_service import (
    recognize_portfolio, update_current_prices, get_portfolio_with_prices, calc_portfolio_risk,
    build_portfolio_context, save_portfolio_items, delete_portfolio, calc_portfolio_diagnosis
)
from ..config import DEEPSEEK_API_KEY, WECHAT_WEBHOOK_API_KEY, CHAT_TIMEOUT_SECONDS, setup_wechat_logging
import json
import uuid
import re
import base64
import os
import asyncio
import hashlib
import time

router = APIRouter(prefix='/api')
# Simple in-memory cache for quotes (5s TTL)
_quote_simple_cache: dict = {}
_quote_simple_cache_ts: dict = {}

def _get_cached_quote(code: str, market: str):
    key = f"{code}:{market}"
    now = __import__("time").time()
    if key in _quote_simple_cache and _quote_simple_cache_ts.get(key, 0) > now - 5:
        return _quote_simple_cache[key]
    return None

def _set_cached_quote(code: str, market: str, data):
    key = f"{code}:{market}"
    _quote_simple_cache[key] = data
    _quote_simple_cache_ts[key] = __import__("time").time()


# --- Phase 5: WeChat webhook router (no /api prefix) ---
wechat_router = APIRouter()

UPLOAD_DIR = "data/uploads"

_wlogger = None

def _get_wechat_logger():
    global _wlogger
    if _wlogger is None:
        _wlogger = setup_wechat_logging()
    return _wlogger


# --- Pydantic models ---
class ChatRequest(BaseModel):
    message: str
    thread_id: str = ""


class WatchRequest(BaseModel):
    code: str
    market: str = "sz"
    name: str = ""


class RefreshRequest(BaseModel):
    code: str

class PortfolioItemUpdate(BaseModel):
    stock_code: str
    stock_name: str
    asset_type: str = "fund"
    quantity: float = 0
    cost_price: float = 0
    current_price: float = 0
    holding_amount: float = 0
    cost_amount: float = 0
    holding_return: float = 0
    daily_return: float = 0
    daily_return_pct: float = 0
    sector: str = ""

class PortfolioUpdateRequest(BaseModel):
    items: list[PortfolioItemUpdate]


class UserProfileUpdate(BaseModel):
    investment_style: str | None = None
    risk_preference: str | None = None
    focus_industries: str | None = None
    focus_stocks: str | None = None

# --- Phase 5: OpenAI-compatible Pydantic models ---
class ChatCompletionMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "zhigu-chat"
    messages: list[ChatCompletionMessage]
    stream: bool = False
    user: str = ""


# --- Stock endpoints ---
@router.get('/search')
def api_search(keyword: str = Query(..., min_length=1)):
    results = search_stocks(keyword)  # A-shares
    # Also search global popular stocks (static list, instant)
    for mkt in ['kr', 'jp', 'us', 'hk']:
        try:
            for s in search_popular(keyword, mkt):
                results.append({
                    'code': s['code'], 'name': s['name'],
                    'market': mkt,
                })
        except Exception:
            pass
    # Deduplicate by code+name
    seen = set()
    deduped = []
    for r in results:
        key = (r['code'], r.get('name', ''))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    return {'results': deduped[:20]}


@router.get('/indices')
def api_indices():
    indices = get_market_indices()
    return {'indices': indices}


@router.get('/global-indices')
async def api_global_indices():
    """Get global market indices grouped by country."""
    return get_global_indices()

@router.get('/news')
async def api_news(page: int = Query(1, ge=1), limit: int = Query(20, ge=1, le=50)):
    """Get financial news from Sina Finance."""
    return get_news(page=page, limit=limit)

@router.get('/funds/search')
async def api_fund_search(keyword: str = Query('', min_length=1)):
    """Search OTC funds by code, name, or pinyin."""
    return search_funds(keyword)

@router.get('/funds/nav')
async def api_fund_nav(code: str = Query(..., min_length=6)):
    """Get fund NAV history and period returns."""
    result = get_fund_nav(code)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get('/funds/recommend')
async def api_fund_recommend():
    """Get fund recommendations across 5 categories (Agent-curated, randomized top performers)."""
    return get_fund_recommendations()

@router.get('/funds/holdings')
async def api_fund_holdings(code: str = Query(..., min_length=6)):
    """Get latest quarter stock holdings and industry allocation."""
    return get_fund_holdings(code)

@router.get('/quote')
def api_quote(code: str = Query(...), market: str = Query('sz')):
    # Check cache first
    cached = _get_cached_quote(code, market)
    if cached is not None:
        return cached

    quote = get_realtime_quote(code, market)
    if quote is None and "." in code:
        # Fallback to cached global indices for codes like "100.HSI"
        try:
            cached = get_global_indices()
            for group in cached:
                for idx in group["indices"]:
                    if idx["code"] == code:
                        p = idx["price"]
                        quote = {
                            "code": code, "name": idx["name"],
                            "price": p, "change_pct": idx["change_pct"], "change_amount": 0,
                            "volume": 0, "amount": 0,
                            "high": p, "low": p, "open": p, "pre_close": p,
                            "turnover": 0,
                        }
                        break
        except Exception:
            pass
    if quote is None:
        _set_cached_quote(code, market, None)
        raise HTTPException(status_code=404, detail='Stock not found')
    _set_cached_quote(code, market, quote)
    return quote


@router.get('/kline')
def api_kline(code: str = Query(...), market: str = Query('sz'), days: int = Query(60), klt: str = Query('101')):
    data = get_kline_data(code, market, days, klt)
    return {'kline': data}


@router.get("/intraday")
def api_intraday(code: str = Query(...), date: str = Query(""), klt: str = Query("5")):
    data = get_intraday(code, date, klt)
    if not data:
        return {"bars": [], "date": date, "synthetic": False, "empty": True}
    fallback = data[0].get("fallback_date", "")
    return {"bars": data, "date": fallback or data[0]["time"][:10],
            "synthetic": bool(fallback),
            "fallback_date": fallback}

@router.get('/indicators')
def api_indicators(code: str = Query(...), market: str = Query('sz'), days: int = Query(60), klt: str = Query('101')):
    kline = get_kline_data(code, market, days, klt)
    if not kline:
        raise HTTPException(status_code=404, detail='No K-line data')
    indicators = calc_all_indicators(kline)
    return {'kline': kline, 'indicators': indicators}


@router.get('/signal')
def api_signal(code: str = Query(...), market: str = Query('sz')):
    """Composite buy/sell signal for a stock (M3)."""
    return compute_signal(code, market)


@router.get('/analyze')
async def api_analyze(
    code: str = Query(...),
    market: str = Query('sz'),
    klt: str = Query('101'),
    user_message: str = Query(''),
    db: Session = Depends(get_db)
):
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=400, detail='DeepSeek API key not configured')

    quote = get_realtime_quote(code, market)
    if quote is None:
        raise HTTPException(status_code=404, detail='Stock not found')

    kline = get_kline_data(code, market, 10000, klt)
    summary = summarize_kline(kline)
    indicators = calc_all_indicators(kline) if klt == '101' else {}

    memory_context = build_context_prompt(code, user_message, max_items=5)

    analysis = await get_analysis(
        quote['name'], code, summary, quote, indicators, memory_context
    )

    cache = AnalysisCache(
        stock_code=code,
        stock_name=quote['name'],
        user_message=user_message,
        content=analysis,
    )
    db.add(cache)
    db.commit()

    try:
        store_memory(stock_code=code, stock_name=quote['name'],
                     user_message=user_message, analysis_content=analysis)
    except Exception:
        pass

    summary_text = ""
    if should_summarize(code):
        summary_text = generate_summary(code, quote['name'])

    return {
        'quote': quote, 'kline': kline, 'analysis': analysis,
        'memory_context': memory_context, 'summary': summary_text,
    }


# --- Chat endpoints ---
@router.post('/chat')
async def api_chat(req: ChatRequest, db: Session = Depends(get_db)):
    """Unified chat: natural language -> stock detection -> full analysis."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail='Message cannot be empty')

    thread_id = req.thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())
        thread = ChatThread(id=thread_id, title=req.message[:50])
        db.add(thread)
        db.commit()
    else:
        thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()

    # Load conversation history
    history = []
    if thread_id:
        past = db.query(ChatMessage).filter(
            ChatMessage.thread_id == thread_id
        ).order_by(ChatMessage.created_at.asc()).all()
        for m in past:
            history.append({"role": m.role, "content": m.content})

    # Save user message
    user_msg = ChatMessage(thread_id=thread_id, role="user", content=req.message)
    db.add(user_msg)
    db.commit()

    result = await chat_agent(
        user_message=req.message,
        conversation_history=history,
        thread_id=thread_id,
        db=db,
    )

    reply = result.get("reply", "")
    msg_type = result.get("type", "general")

    # Auto-generate title for new threads
    if thread and (not thread.title or thread.title == req.message[:50]):
        try:
            title = await generate_title(req.message, reply)
            thread.title = title
        except Exception:
            pass

    # Save assistant message
    assistant_msg = ChatMessage(
        thread_id=thread_id,
        role="assistant",
        content=reply,
        stock_code=result.get("stock_code", ""),
        stock_name=result.get("stock_name", ""),
        stock_data=json.dumps({
            "stock_code": result.get("stock_code", ""),
            "stock_name": result.get("stock_name", ""),
            "market": result.get("market", ""),
            "quote": result.get("quote"),
            "kline": result.get("kline"),
            "indicators": result.get("indicators"),
        }, ensure_ascii=False) if msg_type == "stock" else "",
    )
    db.add(assistant_msg)
    db.commit()

    return {
        "reply": reply,
        "type": msg_type,
        "thread_id": thread_id,
        "stock_code": result.get("stock_code", ""),
        "stock_name": result.get("stock_name", ""),
        "market": result.get("market", ""),
        "quote": result.get("quote"),
        "kline": result.get("kline"),
        "indicators": result.get("indicators"),
    }


@router.post('/chat/stream')
async def api_chat_stream(req: ChatRequest, db: Session = Depends(get_db)):
    """Streaming unified chat (M4): meta -> delta* -> stock_data -> done.

    Reuses chat_agent_stream (tool rounds non-streaming, final answer streamed)
    and translates its OpenAI-style frames into the web event protocol.
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail='Message cannot be empty')

    thread_id = req.thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())
        thread = ChatThread(id=thread_id, title=req.message[:50])
        db.add(thread)
        db.commit()
    else:
        thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()

    # Load conversation history
    history = []
    if thread_id:
        past = db.query(ChatMessage).filter(
            ChatMessage.thread_id == thread_id
        ).order_by(ChatMessage.created_at.asc()).all()
        for m in past:
            history.append({"role": m.role, "content": m.content})

    # Save user message
    user_msg = ChatMessage(thread_id=thread_id, role="user", content=req.message)
    db.add(user_msg)
    db.commit()

    async def gen():
        meta = {}
        try:
            yield _sse({"type": "meta", "thread_id": thread_id})
            async for frame in chat_agent_stream(
                user_message=req.message,
                conversation_history=history,
                thread_id=thread_id,
                db=db,
            ):
                if frame.startswith(":__meta__"):
                    try:
                        meta = json.loads(frame[len(":__meta__"):].strip())
                    except json.JSONDecodeError:
                        meta = {}
                    continue
                if frame.startswith("data: [DONE]"):
                    continue
                if not frame.startswith("data: "):
                    continue
                try:
                    chunk = json.loads(frame[len("data: "):].strip())
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta", {}) or {}
                        content = delta.get("content", "")
                        if content:
                            yield _sse({"type": "delta", "content": content})
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

            reply = meta.get("full_reply", "")
            if reply:
                msg_type = meta.get("type", "general")
                stock_data_json = ""
                if msg_type == "stock":
                    stock_payload = {
                        "stock_code": meta.get("stock_code", ""),
                        "stock_name": meta.get("stock_name", ""),
                        "market": meta.get("market", ""),
                        "quote": meta.get("quote"),
                        "kline": meta.get("kline"),
                        "indicators": meta.get("indicators"),
                    }
                    stock_data_json = json.dumps(stock_payload, ensure_ascii=False)
                    yield _sse({"type": "stock_data", "stock_data": stock_payload})
                    try:
                        register_watch(thread_id, meta.get("stock_code", ""),
                                       meta.get("market", "sz"), meta.get("stock_name", ""))
                    except Exception:
                        pass
                assistant_msg = ChatMessage(
                    thread_id=thread_id,
                    role="assistant",
                    content=reply,
                    stock_code=meta.get("stock_code", ""),
                    stock_name=meta.get("stock_name", ""),
                    stock_data=stock_data_json,
                )
                db.add(assistant_msg)
                db.commit()
                if thread and (not thread.title or thread.title == req.message[:50]):
                    try:
                        title = await generate_title(req.message, reply)
                        thread.title = title
                        db.commit()
                    except Exception:
                        db.rollback()
                yield _sse({"type": "done", "message_id": assistant_msg.id,
                            "thread_id": thread_id, "content": reply})
            else:
                yield _sse({"type": "done", "thread_id": thread_id})
            yield "data: [DONE]\n\n"
        except Exception:
            db.rollback()
            yield _sse({"type": "error", "message": "服务暂时不可用，请稍后再试"})
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get('/chat/threads')
def api_chat_threads(db: Session = Depends(get_db)):
    """List all chat threads."""
    threads = db.query(ChatThread).order_by(
        ChatThread.pinned.desc(),
        ChatThread.updated_at.desc()
    ).all()
    result = []
    for t in threads:
        last_msg = db.query(ChatMessage).filter(
            ChatMessage.thread_id == t.id
        ).order_by(ChatMessage.created_at.desc()).first()
        result.append({
            "id": t.id,
            "title": t.title,
            "pinned": t.pinned,
            "updated_at": t.updated_at.isoformat() if t.updated_at else "",
            "last_message": last_msg.content[:60] if last_msg else "",
        })
    return result


@router.get('/chat/threads/{thread_id}')
def api_chat_thread_messages(thread_id: str, db: Session = Depends(get_db)):
    """Get messages for a thread."""
    msgs = db.query(ChatMessage).filter(
        ChatMessage.thread_id == thread_id
    ).order_by(ChatMessage.created_at.asc()).all()
    return [{
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "stock_code": m.stock_code,
        "stock_name": m.stock_name,
        "stock_data": json.loads(m.stock_data) if m.stock_data else None,
        "created_at": m.created_at.isoformat() if m.created_at else "",
    } for m in msgs]


@router.patch('/chat/threads/{thread_id}')
def api_chat_thread_update(thread_id: str, title: str = Query(None), pinned: bool = Query(None),
                           db: Session = Depends(get_db)):
    """Update thread title or pinned status."""
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        raise HTTPException(status_code=404, detail='Thread not found')
    if title is not None:
        thread.title = title
    if pinned is not None:
        thread.pinned = pinned
    db.commit()
    return {"ok": True}


@router.delete('/chat/threads/{thread_id}')
def api_chat_thread_delete(thread_id: str, db: Session = Depends(get_db)):
    """Delete a thread and all its messages."""
    db.query(ChatMessage).filter(ChatMessage.thread_id == thread_id).delete()
    db.query(ChatThread).filter(ChatThread.id == thread_id).delete()
    db.commit()
    return {"ok": True}



# --- Auth endpoints ---

class RegisterRequest(BaseModel):
    username: str
    password: str
    nickname: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.get('/chat/threads/{thread_id}/watches')
def api_thread_watches(thread_id: str):
    """List the thread's watch list (M5)."""
    return list_watches(thread_id)


@router.post('/chat/threads/{thread_id}/watches')
def api_add_thread_watch(thread_id: str, req: WatchRequest):
    """Register a stock for the thread's watch list (M5)."""
    return register_watch(thread_id, req.code, req.market, req.name)


@router.delete('/chat/threads/{thread_id}/watches')
def api_delete_thread_watch(thread_id: str, code: str = Query(...)):
    """Remove a stock from the thread's watch list (M5)."""
    ok = delete_watch(thread_id, code)
    if not ok:
        raise HTTPException(status_code=404, detail='盯盘记录不存在')
    return {"ok": True}


@router.post('/chat/threads/{thread_id}/watches/refresh')
async def api_refresh_thread_watch(thread_id: str, req: RefreshRequest):
    """Manually re-evaluate one watch and push an advice update (M5)."""
    return await get_watch_monitor().refresh_now(thread_id, req.code)


@router.get('/chat/threads/{thread_id}/stream')
async def api_thread_stream(thread_id: str, interval: int = Query(0, ge=0, le=60)):
    """SSE stream of realtime conversation events (M5): advice_update etc."""
    broker = get_thread_broker()
    queue = broker.subscribe(thread_id)
    if interval >= 3:
        get_watch_monitor().set_interval(interval)

    async def gen():
        try:
            yield _sse({"type": "watch_connected", "thread_id": thread_id})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield _sse(event)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            broker.unsubscribe(thread_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post('/auth/register')
def api_register(req: RegisterRequest, db: Session = Depends(get_db)):
    """Register a new user."""
    if len(req.username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少3位")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")
    user = create_user(db, req.username, req.password, req.nickname)
    if not user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    token = create_access_token({"sub": str(user.id), "username": user.username})
    return {
        "token": token,
        "user": {"id": user.id, "username": user.username, "nickname": user.nickname},
    }


@router.post('/auth/login')
def api_login(req: LoginRequest, db: Session = Depends(get_db)):
    """Login and get JWT token."""
    user = authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token({"sub": str(user.id), "username": user.username})
    return {
        "token": token,
        "user": {"id": user.id, "username": user.username, "nickname": user.nickname, "avatar": user.avatar},
    }


@router.get('/auth/profile')
def api_get_profile(user_id: int = Query(...), db: Session = Depends(get_db)):
    """Get user profile."""
    profile = get_user_by_id(db, user_id)
    if not profile:
        raise HTTPException(status_code=404, detail="用户不存在")
    return profile


@router.put('/auth/profile')
def api_update_profile(user_id: int = Query(...), nickname: str = Query(None),
                       db: Session = Depends(get_db)):
    """Update nickname."""
    ok = update_profile(db, user_id, nickname=nickname)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True}


@router.post('/auth/change-password')
def api_change_password(req: ChangePasswordRequest, user_id: int = Query(...),
                        db: Session = Depends(get_db)):
    """Change password."""
    ok, msg = change_password(db, user_id, req.old_password, req.new_password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}

# --- Watchlist endpoints ---
@router.get('/watchlist')
def api_watchlist(db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).filter(WatchlistItem.is_active == True).order_by(
        WatchlistItem.added_at.desc()).all()
    return [{'id': i.id, 'code': i.code, 'name': i.name, 'market': i.market} for i in items]


# --- 微信小程序登录 ---
class WxLoginRequest(BaseModel):
    code: str

@router.post('/auth/wx-login')
def wx_login(req: WxLoginRequest, db: Session = Depends(get_db)):
    import requests as wx_req
    wx_appid = os.getenv("WX_APPID", "")
    wx_secret = os.getenv("WX_SECRET", "")
    if not wx_appid or not wx_secret:
        raise HTTPException(500, "WX_APPID/WX_SECRET not configured in .env")
    wx_url = f"https://api.weixin.qq.com/sns/jscode2session?appid={wx_appid}&secret={wx_secret}&js_code={req.code}&grant_type=authorization_code"
    resp = wx_req.get(wx_url)
    wx_data = resp.json()
    if "errcode" in wx_data and wx_data["errcode"] != 0:
        raise HTTPException(400, f"wx login failed: {wx_data.get('errmsg', '')}")
    openid = wx_data["openid"]
    wx_username = f"wx_{openid}"
    user = db.query(User).filter(User.username == wx_username).first()
    if not user:
        from ..services.auth_service import hash_password, create_access_token
        user = User(username=wx_username, nickname="微信用户", password_hash="")
        db.add(user)
        db.commit()
        db.refresh(user)
    token = create_access_token({"sub": str(user.id), "username": user.username})
    return {"token": token, "user_id": str(user.id), "nickname": user.nickname}


@router.post('/watchlist')
def api_add_watchlist(code: str = Query(...), name: str = Query(...), market: str = Query('sz'),
                      db: Session = Depends(get_db)):
    existing = db.query(WatchlistItem).filter(WatchlistItem.code == code).first()
    if existing:
        existing.is_active = True
    else:
        item = WatchlistItem(code=code, name=name, market=market)
        db.add(item)
    db.commit()
    return {'ok': True}


@router.get('/watchlist/quotes')
def api_watchlist_quotes(codes: list[str] = Query(...)):
    results = []
    # Known index codes and their markets
    INDEX_CODES = {"000001": "sh", "000300": "sh", "000688": "sh", "399001": "sz", "399006": "sz"}
    for code in codes:
        if code in INDEX_CODES:
            market = INDEX_CODES[code]
        else:
            market = "sh" if code.startswith(("6", "9")) else "sz"
        q = get_realtime_quote(code, market)
        if q:
            results.append(q)
    return results


def _sse(data: dict) -> str:
    """Format an SSE data frame."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get('/quotes/stream')
async def api_quotes_stream(codes: str = Query(''), interval: int = Query(0, ge=0, le=60)):
    """SSE stream of realtime quotes (M2).

    Subscribes the poller to the given codes, pushes an initial snapshot,
    then pushes one frame per poll round. Emits ': ping' heartbeats when idle.
    """
    from ..services.quote_poller import get_quote_poller

    wanted = [c.strip() for c in codes.split(',') if c.strip()]
    poller = get_quote_poller()
    poller.register_codes(wanted)
    sub_id, queue = poller.add_subscriber(interval)

    async def gen():
        try:
            # Initial snapshot (may be empty until the first poll round fills cache)
            yield _sse(poller.snapshot(wanted if wanted else None))
            wanted_set = set(wanted)
            while True:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15)
                    quotes = msg.get("quotes", [])
                    if wanted_set:
                        quotes = [q for q in quotes if q.get("code") in wanted_set]
                    if quotes:
                        yield _sse({"type": "quotes", "ts": msg.get("ts", 0), "quotes": quotes})
                except asyncio.TimeoutError:
                    yield ": ping\n\n"
        finally:
            poller.remove_subscriber(sub_id)
            poller.unregister_codes(wanted)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get('/history')
def api_history(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200)):
    records = db.query(AnalysisCache).order_by(AnalysisCache.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
             "user_message": r.user_message or "", "content": r.content,
             "created_at": r.created_at.isoformat() if r.created_at else ""}
            for r in records]


@router.get('/conversations')
def api_conversations(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200)):
    """Get conversation history."""
    records = db.query(AnalysisCache).order_by(AnalysisCache.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "stock_code": r.stock_code, "stock_name": r.stock_name,
             "user_message": r.user_message or "", "content": r.content,
             "created_at": r.created_at.isoformat() if r.created_at else ""}
            for r in records]


@router.delete('/watchlist')
def api_remove_watchlist(code: str = Query(...), db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.code == code).first()
    if item:
        item.is_active = False
        db.commit()
    return {'ok': True}


# --- User profile endpoints ---

@router.get('/user/profile')
def api_get_user_profile(db: Session = Depends(get_db)):
    """Get user investment profile."""
    profile = get_or_create_profile(db)
    return {
        "investment_style": profile.investment_style,
        "risk_preference": profile.risk_preference,
        "focus_industries": profile.focus_industries,
        "focus_stocks": profile.focus_stocks,
    }


@router.put('/user/profile')
def api_update_user_profile(req: UserProfileUpdate, db: Session = Depends(get_db)):
    """Update user investment profile."""
    profile = update_profile(
        db,
        investment_style=req.investment_style,
        risk_preference=req.risk_preference,
        focus_industries=req.focus_industries,
        focus_stocks=req.focus_stocks,
    )
    return {"ok": True, "investment_style": profile.investment_style}


# --- Global market endpoints ---

@router.get('/global/search')
def api_global_search(keyword: str, market: str = "hk"):
    """Search global stocks."""
    results = search_global_stocks(keyword, market)
    return {"results": results}


@router.get('/global/quote')
def api_global_quote(code: str, market: str = "hk"):
    """Get global stock quote."""
    quote = get_global_quote(code, market)
    if not quote:
        raise HTTPException(status_code=404, detail=f"Quote not found for {market}:{code}")
    return quote


@router.get('/global/kline')
def api_global_kline(code: str, market: str = "hk", days: int = 120):
    """Get global stock K-line data."""
    kline = get_global_kline(code, market, days)
    return {"kline": kline}


@router.get('/global/indicators')
def api_global_indicators(code: str, market: str = "hk", days: int = Query(60), klt: str = Query("101")):
    """Get global stock K-line + technical indicators."""
    kline = get_global_kline(code, market, days, klt)
    if not kline:
        # Fallback: return TradingView snapshot
        tv = get_global_indicators(code, market)
        return {"kline": [], "indicators": tv}
    from ..services.technical import calc_all_indicators
    indicators = calc_all_indicators(kline)
    return {"kline": kline, "indicators": indicators}


@router.get('/global/indices')
def api_global_indices():
    """Get global market indices."""
    indices = _get_global_indices()
    return {"indices": indices}


# --- Portfolio endpoints ---
@router.get('/portfolio')
def api_get_portfolio(db: Session = Depends(get_db)):
    portfolio = get_portfolio_with_prices(db)
    if not portfolio:
        return {"id": None, "name": "", "items": [], "total_value": 0, "total_cost": 0, "total_profit": 0, "total_profit_pct": 0}
    return portfolio


@router.post('/portfolio/upload')
async def api_upload_portfolio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='File must be an image')

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail='File too large (max 10MB)')

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = file.filename.split('.')[-1] if file.filename else 'jpg'
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(content)

    image_b64 = base64.b64encode(content).decode('utf-8')

    try:
        recognized = recognize_portfolio(image_b64)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    recognized = update_current_prices(recognized)

    return {"items": recognized, "image_path": filepath}


@router.put('/portfolio/items')
def api_update_portfolio_items(req: PortfolioUpdateRequest, db: Session = Depends(get_db)):
    items = [item.dict() for item in req.items]
    portfolio = save_portfolio_items(db, items)
    return {"ok": True, "id": portfolio.id}


@router.get('/portfolio/risk')
def api_portfolio_risk(db: Session = Depends(get_db)):
    """Get portfolio risk metrics: Sharpe ratio and max drawdown."""
    risk = calc_portfolio_risk(db)
    return risk

@router.get('/portfolio/diagnosis')
def api_portfolio_diagnosis(db: Session = Depends(get_db)):
    """Get portfolio diagnosis: concentration, per-item signal lights, summary."""
    diagnosis = calc_portfolio_diagnosis(db)
    return diagnosis


@router.get('/alerts')
def api_get_alerts():
    """Get latest monitor alerts from alerts.json."""
    import json as _json
    from pathlib import Path as _Path
    alerts_file = _Path(__file__).resolve().parent.parent.parent / "data" / "alerts.json"
    if not alerts_file.exists():
        return {"alerts": [], "updated_at": None}
    try:
        with open(alerts_file, "r", encoding="utf-8") as f:
            return _json.load(f)
    except Exception:
        return {"alerts": [], "updated_at": None}


@router.delete('/portfolio')
def api_delete_portfolio(db: Session = Depends(get_db)):
    success = delete_portfolio(db)
    return {"ok": success}


# --- Phase 5: OpenAI-compatible /v1/chat/completions (WeChat) ---

@wechat_router.post("/v1/chat/completions")
async def v1_chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint for OpenClaw WeChat integration.
    Accepts any valid JSON body to avoid Pydantic strict validation on OpenClaw's rich payloads.
    """
    logger = _get_wechat_logger()
    start_time = time.time()

    # Parse raw body to avoid Pydantic strict validation
    try:
        body = await request.json()
    except Exception:
        return {"error": {"message": "Invalid JSON body", "type": "invalid_request"}}

    # Optional API key auth
    if WECHAT_WEBHOOK_API_KEY:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {WECHAT_WEBHOOK_API_KEY}":
            return {"error": {"message": "Unauthorized", "type": "auth_error"}}

    # Extract user identity
    user_id = body.get("user", "")
    if not user_id:
        client_ip = request.client.host if request.client else "unknown"
        user_id = hashlib.md5(client_ip.encode()).hexdigest()[:12]
    thread_id = f"wechat:{user_id}"

    # Extract messages: handle both simple and complex message formats
    raw_messages = body.get("messages", [])
    
    # Find system prompt and last user message
    system_prompt = ""
    user_messages = []
    conversation_history = []
    
    for i, m in enumerate(raw_messages):
        role = m.get("role", "")
        content = m.get("content", "")
        
        # Extract text content (handle both string and array content)
        if isinstance(content, list):
            text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
            content = "".join(text_parts)
        if not isinstance(content, str):
            content = ""
        
        if role == "system":
            system_prompt = content
        elif role == "user" and content:
            user_messages.append({"index": i, "content": content})
        elif role in ("user", "assistant") and content:
            conversation_history.append({"role": role, "content": content})
    
    if not user_messages:
        return {"error": {"message": "No user message found", "type": "invalid_request"}}
    
    # Last user message is the current query
    current_message = user_messages[-1]["content"]
    # Strip OpenClaw metadata prefix (e.g. "Conversation info (untrusted metadata):\n```json\n...\n```")
    meta_pattern = r"^Conversation info \(untrusted metadata\):\s*```json\s*\{[^`]*?\}\s*```\s*"
    current_message = re.sub(meta_pattern, "", current_message, flags=re.DOTALL).strip()
    # Exclude the last user message from conversation history
    last_user_idx = user_messages[-1]["index"]
    conversation_history = [m for m in conversation_history 
                           if m.get("_idx", raw_messages.index(m)) < last_user_idx]

        # DEBUG: log raw messages structure for troubleshooting
    logger.debug(f"RAW messages count={len(raw_messages)}")
    for mi, m in enumerate(raw_messages[:5]):
        c = m.get("content", "")
        if isinstance(c, list):
            parts = [p.get("text","")[:60] if isinstance(p,dict) else str(p)[:60] for p in c[:3]]
            logger.debug(f"  msg[{mi}] role={m.get('role','?')} content_type=list parts={parts}")
        else:
            logger.debug(f"  msg[{mi}] role={m.get('role','?')} content={str(c)[:80]}")

    stream = body.get("stream", False)
    model = body.get("model", "zhigu-chat")

    logger.info(
        f"REQ user={user_id} thread={thread_id} "
        f"msg={current_message[:100]} history_len={len(conversation_history)} "
        f"stream={stream} sys_prompt_len={len(system_prompt)}"
    )

    if stream:
        async def stream_response():
            full_reply = ""
            stock_data_meta = None

            try:
                async for chunk in chat_agent_stream(
                    user_message=current_message,
                    conversation_history=conversation_history,
                    thread_id=thread_id,
                ):
                    chunk_str = chunk if isinstance(chunk, str) else chunk
                    if chunk_str.startswith(":__meta__"):
                        try:
                            meta_json = chunk_str[len(":__meta__"):]
                            stock_data_meta = json.loads(meta_json)
                            full_reply = stock_data_meta.get("full_reply", "")
                        except json.JSONDecodeError:
                            pass
                        continue
                    yield chunk_str.encode("utf-8") if isinstance(chunk_str, str) else chunk_str

            finally:
                elapsed = (time.time() - start_time) * 1000
                logger.info(
                    f"RES user={user_id} thread={thread_id} "
                    f"reply_len={len(full_reply)} elapsed={elapsed:.0f}ms "
                    f"stream=1"
                )

                if full_reply:
                    asyncio.create_task(_persist_stream_message(
                        thread_id=thread_id,
                        user_message=current_message,
                        full_reply=full_reply,
                        stock_data_meta=stock_data_meta,
                    ))

        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            result = await chat_agent(
                user_message=current_message,
                conversation_history=conversation_history,
                thread_id=thread_id,
            )
            reply = result.get("reply", "")

            elapsed = (time.time() - start_time) * 1000
            logger.info(
                f"RES user={user_id} thread={thread_id} "
                f"reply_len={len(reply)} elapsed={elapsed:.0f}ms "
                f"stream=0"
            )

            sd = {
                "stock_code": result.get("stock_code", ""),
                "stock_name": result.get("stock_name", ""),
                "type": result.get("type", "general"),
                "quote": result.get("quote"),
                "kline": result.get("kline"),
                "indicators": result.get("indicators"),
            }
            asyncio.create_task(_persist_stream_message(
                thread_id=thread_id,
                user_message=current_message,
                full_reply=reply,
                stock_data_meta=sd,
            ))

            return {
                "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop",
                }],
            }

        except Exception as e:
            logger.error(f"ERR user={user_id} thread={thread_id} error={e}")
            return {"error": {"message": "服务暂时不可用，请稍后再试", "type": "api_error"}}

async def _persist_stream_message(
    thread_id: str,
    user_message: str,
    full_reply: str,
    stock_data_meta: dict = None,
):
    """Async background task: persist chat to DB + ChromaDB."""
    db = SessionLocal()
    try:
        # Ensure thread exists
        thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
        if not thread:
            title = user_message[:50]
            thread = ChatThread(id=thread_id, title=title)
            db.add(thread)
        else:
            # Auto-generate title if still default
            if (not thread.title or thread.title == user_message[:50]) and full_reply:
                try:
                    title = await generate_title(user_message, full_reply)
                    thread.title = title
                except Exception:
                    pass

        # Save user message
        user_msg = ChatMessage(thread_id=thread_id, role="user", content=user_message)
        db.add(user_msg)

        # Save assistant message
        sd = stock_data_meta or {}
        stock_data_json = json.dumps({
            "stock_code": sd.get("stock_code", ""),
            "stock_name": sd.get("stock_name", ""),
            "market": sd.get("market", ""),
            "quote": sd.get("quote"),
            "kline": sd.get("kline"),
            "indicators": sd.get("indicators"),
        }, ensure_ascii=False) if sd.get("type") == "stock" else ""

        assistant_msg = ChatMessage(
            thread_id=thread_id,
            role="assistant",
            content=full_reply,
            stock_code=sd.get("stock_code", ""),
            stock_name=sd.get("stock_name", ""),
            stock_data=stock_data_json,
        )
        db.add(assistant_msg)
        db.commit()

        # ChromaDB memory (best-effort, non-blocking already)
        if sd.get("stock_code") and sd.get("stock_name"):
            try:
                store_memory(
                    stock_code=sd["stock_code"],
                    stock_name=sd["stock_name"],
                    user_message=user_message,
                    analysis_content=full_reply,
                )
            except Exception:
                pass

    except Exception as e:
        logger = logging.getLogger("wechat")
        logger.error(f"PERSIST error thread={thread_id}: {e}")
    finally:
        db.close()





