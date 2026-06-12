from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ..models.database import get_db, SessionLocal
from ..models.stock import WatchlistItem, AnalysisCache, ChatThread, ChatMessage, PortfolioItem
from ..services.stock_data import search_stocks, get_realtime_quote, get_kline_data, get_market_indices, get_intraday
from ..services.ai_analysis import get_analysis, summarize_kline
from ..services.technical import calc_all_indicators
from ..services.retrieval import build_context_prompt
from ..services.memory import store_memory
from ..services.summarizer import should_summarize, generate_summary
from ..services.chat_service import chat_full, generate_title, chat_full_stream, chat_agent, chat_agent_stream
from ..services.portfolio_service import (
    recognize_portfolio, update_current_prices, get_portfolio_with_prices, calc_portfolio_risk,
    build_portfolio_context, save_portfolio_items, delete_portfolio
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

class PortfolioItemUpdate(BaseModel):
    stock_code: str
    stock_name: str
    asset_type: str = "stock"
    quantity: float = 0
    cost_price: float = 0
    current_price: float = 0

class PortfolioUpdateRequest(BaseModel):
    items: list[PortfolioItemUpdate]

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
    results = search_stocks(keyword)
    return {'results': results}


@router.get('/indices')
def api_indices():
    indices = get_market_indices()
    return {'indices': indices}


@router.get('/quote')
def api_quote(code: str = Query(...), market: str = Query('sz')):
    quote = get_realtime_quote(code, market)
    if quote is None:
        raise HTTPException(status_code=404, detail='Stock not found')
    return quote


@router.get('/kline')
def api_kline(code: str = Query(...), market: str = Query('sz'), days: int = Query(60), klt: str = Query('101')):
    data = get_kline_data(code, market, days, klt)
    return {'kline': data}


@router.get("/intraday")
def api_intraday(code: str = Query(...), date: str = Query("")):
    data = get_intraday(code, date)
    if not data:
        raise HTTPException(status_code=404, detail="No intraday data")
    return {"bars": data, "date": data[0]["time"][:10] if data else date,
            "synthetic": data[0].get("avg_price", 0) > 0 if data else False}


@router.get('/indicators')
def api_indicators(code: str = Query(...), market: str = Query('sz'), days: int = Query(60), klt: str = Query('101')):
    kline = get_kline_data(code, market, days, klt)
    if not kline:
        raise HTTPException(status_code=404, detail='No K-line data')
    indicators = calc_all_indicators(kline)
    return {'kline': kline, 'indicators': indicators}


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

    kline = get_kline_data(code, market, 120, klt)
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


# --- Watchlist endpoints ---
@router.get('/watchlist')
def api_watchlist(db: Session = Depends(get_db)):
    items = db.query(WatchlistItem).filter(WatchlistItem.is_active == True).order_by(
        WatchlistItem.added_at.desc()).all()
    return [{'id': i.id, 'code': i.code, 'name': i.name, 'market': i.market} for i in items]


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
    for code in codes:
        q = get_realtime_quote(code)
        if q:
            results.append(q)
    return results


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




