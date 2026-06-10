"""Unified chat service: natural language → stock detection → full analysis pipeline."""

import os
import json
import re
import logging
from curl_cffi import requests
from typing import Optional, AsyncGenerator
from sqlalchemy.orm import Session

from .stock_data import search_stocks, get_realtime_quote, get_kline_data, get_market_indices, get_intraday
from .ai_analysis import build_indicator_summary, summarize_kline, get_analysis
from .technical import calc_all_indicators
from .retrieval import build_context_prompt
from .memory import store_memory
from .portfolio_service import build_portfolio_context
from ..config import MAX_HISTORY_PAIRS

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

TRUNCATION_SUFFIX = "…[回复过长已截断]"
MAX_RESPONSE_UTF8_BYTES = 2000

CHAT_SYSTEM_PROMPT = """你是"知股"，一位专业、简洁的A股智能投研助手。

你的特点：
- 回答精准、不啰嗦，用数据和逻辑说话
- 回答控制在500字以内，关键结论用**加粗**标出
- 不推荐具体买卖操作，只给分析参考
- 不说"作为AI"等套话，直接给结论
- 友好但保持专业

能力范围：A股个股分析、市场指数概况、板块研判、投资知识科普"""

STOCK_INTENT_PROMPT = """分析用户消息,判断是否涉及具体A股股票查询。
如果涉及,提取股票名称或代码。如果不涉及,返回null。

用户消息: "{message}"

返回JSON格式:
{{"is_stock_intent": true/false, "stock_keyword": "股票名称或代码"}}"""


def _detect_stock_intent(message: str) -> Optional[dict]:
    """Use AI to detect if user is asking about a specific stock."""
    if not DEEPSEEK_API_KEY:
        return None

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": STOCK_INTENT_PROMPT.format(message=message)}],
                "temperature": 0.1,
                "max_tokens": 100,
            },
            timeout=30,
        )
        data = resp.json()
        if "choices" in data and data["choices"]:
            content = data["choices"][0]["message"]["content"]
            content = content.strip()
            if "```" in content:
                content = re.sub(r'```\w*\n?', '', content).replace('```', '')
            return json.loads(content)
    except Exception:
        pass
    return None


def _truncate_history(pairs: list[dict], max_pairs: int) -> list[dict]:
    """Keep only the most recent N user-assistant pairs (2*N messages)."""
    if not pairs or max_pairs <= 0:
        return pairs or []
    if len(pairs) > max_pairs * 2:
        return pairs[-(max_pairs * 2):]
    return pairs


def _truncate_response(text: str) -> str:
    """Truncate response to fit within MAX_RESPONSE_UTF8_BYTES."""
    if len(text.encode("utf-8")) <= MAX_RESPONSE_UTF8_BYTES:
        return text
    suffix_bytes = len(TRUNCATION_SUFFIX.encode("utf-8"))
    target = MAX_RESPONSE_UTF8_BYTES - suffix_bytes
    truncated = text.encode("utf-8")[:target].decode("utf-8", errors="ignore")
    return truncated + TRUNCATION_SUFFIX


async def chat_full(
    user_message: str,
    conversation_history: list[dict] = None,
    thread_id: str = "",
    db: Session = None,
) -> dict:
    """
    Full chat pipeline:
    1. Detect stock intent
    2. If stock: fetch quote + kline + indicators + AI analysis
    3. If general: free-form chat
    Returns structured dict.
    """
    if not DEEPSEEK_API_KEY:
        return {
            "reply": "**错误**：未配置 DeepSeek API Key",
            "type": "error",
        }

    intent = _detect_stock_intent(user_message)
    is_stock = intent and intent.get("is_stock_intent") and intent.get("stock_keyword")
    stock_keyword = intent.get("stock_keyword", "") if intent else ""

    stock_data = None
    if is_stock and stock_keyword:
        results = search_stocks(stock_keyword)
        if results:
            best = results[0]
            code = best["code"]
            name = best["name"]
            market = "sh" if code.startswith("6") or code.startswith("9") else "sz"

            try:
                quote = get_realtime_quote(code, market)
                kline = get_kline_data(code, market, 120, "101")
                indicators = calc_all_indicators(kline) if kline else {}
                indicator_summary = build_indicator_summary(indicators)
                kline_summary = summarize_kline(kline) if kline else ""

                stock_data = {
                    "code": code,
                    "name": name,
                    "market": market,
                    "quote": quote,
                    "kline": kline,
                    "indicators": indicators,
                    "indicator_summary": indicator_summary,
                    "kline_summary": kline_summary,
                }
            except Exception:
                stock_data = None

    if stock_data:
        sd = stock_data
        q = sd["quote"] or {}
        memory_context = build_context_prompt(sd["code"], user_message, max_items=3)

        user_prompt = f"""用户问：{user_message}

已识别股票：{sd['name']}（{sd['code']}）
最新价：{q.get('price', 'N/A')}元 | 涨跌幅：{q.get('change_pct', 'N/A')}%
今日：开{q.get('open', 'N/A')} 高{q.get('high', 'N/A')} 低{q.get('low', 'N/A')}
成交额：{q.get('amount', 0)/1e8:.2f}亿 | 换手率：{q.get('turnover', 'N/A')}%

技术指标：{sd['indicator_summary']}
近20日K线概要：{sd['kline_summary'][:600] if sd['kline_summary'] else '无数据'}"""
        if memory_context:
            user_prompt += f"\n\n[历史分析记忆]\n{memory_context}"
    else:
        user_prompt = user_message

    system_prompt = CHAT_SYSTEM_PROMPT
    if db:
        portfolio_context = build_portfolio_context(db)
        if portfolio_context:
            system_prompt += f"\n\n{portfolio_context}"

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history[-20:])
    messages.append({"role": "user", "content": user_prompt})

    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": messages, "temperature": 0.4, "max_tokens": 1200},
        timeout=120,
    )
    data = resp.json()
    reply = ""
    if "choices" in data and data["choices"]:
        reply = data["choices"][0]["message"]["content"]
    else:
        reply = f"AI响应失败：{data}"

    if stock_data:
        try:
            store_memory(
                stock_code=stock_data["code"],
                stock_name=stock_data["name"],
                user_message=user_message,
                analysis_content=reply,
            )
        except Exception:
            pass

    result = {
        "reply": reply,
        "type": "stock" if stock_data else "general",
    }
    if stock_data:
        result["stock_code"] = stock_data["code"]
        result["stock_name"] = stock_data["name"]
        result["market"] = stock_data["market"]
        result["quote"] = stock_data["quote"]
        result["kline"] = stock_data["kline"]
        result["indicators"] = stock_data["indicators"]

    return result


async def generate_title(first_message: str, reply: str) -> str:
    """Generate a concise thread title using AI."""
    if not DEEPSEEK_API_KEY:
        return first_message[:30]

    prompt = f"用8-15个字概括这句话的核心意图，只输出标题，不要引号不要解释不要标点：{first_message[:80]}"

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 30,
                "stop": ["\n", "。", "，", "：", "（"],
            },
            timeout=20,
        )
        data = resp.json()
        if "choices" in data and data["choices"]:
            title = data["choices"][0]["message"]["content"].strip().strip('"').strip("'")
            return title[:20] if title else first_message[:20]
    except Exception:
        pass
    return first_message[:20]


# --- Phase 5: WeChat streaming chat ---

STREAM_SYSTEM_PROMPT = CHAT_SYSTEM_PROMPT

ERROR_MESSAGES = {
    "no_api_key": "AI 服务暂时不可用，请稍后再试",
    "stock_data_fail": "暂时无法获取股票信息，请稍后再试",
    "timeout": "处理中，请稍后重新提问",
    "general": "服务暂时不可用，请稍后再试",
}

FRIENDLY_TIMEOUT_MSG = ERROR_MESSAGES["timeout"]


async def chat_full_stream(
    user_message: str,
    conversation_history: list[dict] = None,
    thread_id: str = "",
    db: Session = None,
) -> AsyncGenerator[str, None]:
    """
    Streaming chat pipeline for WeChat (OpenAI-compatible SSE).

    Same pipeline as chat_full() but:
    - Yields SSE-formatted chunks from DeepSeek streaming response
    - Truncates conversation history to MAX_HISTORY_PAIRS pairs
    - Truncates final response if exceeding UTF-8 byte limit
    - Returns friendly error messages on failure
    """
    def _sse_chunk(content: str, finish_reason: str = None) -> str:
        delta = {"content": content}
        choice = {"index": 0, "delta": delta}
        if finish_reason:
            choice["finish_reason"] = finish_reason
        return f"data: {json.dumps({'choices': [choice]})}\n\n"

    def _sse_done() -> str:
        return "data: [DONE]\n\n"

    if not DEEPSEEK_API_KEY:
        yield _sse_chunk(ERROR_MESSAGES["no_api_key"], "stop")
        yield _sse_done()
        return

    # --- Phase 1: Stock intent detection ---
    stock_data = None
    try:
        intent = _detect_stock_intent(user_message)
        is_stock = intent and intent.get("is_stock_intent") and intent.get("stock_keyword")
        stock_keyword = intent.get("stock_keyword", "") if intent else ""

        if is_stock and stock_keyword:
            results = search_stocks(stock_keyword)
            if results:
                best = results[0]
                code = best["code"]
                name = best["name"]
                market = "sh" if code.startswith("6") or code.startswith("9") else "sz"

                try:
                    quote = get_realtime_quote(code, market)
                    kline = get_kline_data(code, market, 120, "101")
                    indicators = calc_all_indicators(kline) if kline else {}
                    indicator_summary = build_indicator_summary(indicators)
                    kline_summary = summarize_kline(kline) if kline else ""

                    stock_data = {
                        "code": code,
                        "name": name,
                        "market": market,
                        "quote": quote,
                        "kline": kline,
                        "indicators": indicators,
                        "indicator_summary": indicator_summary,
                        "kline_summary": kline_summary,
                    }
                except Exception:
                    stock_data = None
    except Exception:
        stock_data = None

    # --- Phase 2: Build messages ---
    if stock_data:
        sd = stock_data
        q = sd["quote"] or {}
        memory_context = build_context_prompt(sd["code"], user_message, max_items=3)

        user_prompt = f"""用户问：{user_message}

已识别股票：{sd['name']}（{sd['code']}）
最新价：{q.get('price', 'N/A')}元 | 涨跌幅：{q.get('change_pct', 'N/A')}%
今日：开{q.get('open', 'N/A')} 高{q.get('high', 'N/A')} 低{q.get('low', 'N/A')}
成交额：{q.get('amount', 0)/1e8:.2f}亿 | 换手率：{q.get('turnover', 'N/A')}%

技术指标：{sd['indicator_summary']}
近20日K线概要：{sd['kline_summary'][:600] if sd['kline_summary'] else '无数据'}"""
        if memory_context:
            user_prompt += f"\n\n[历史分析记忆]\n{memory_context}"
    else:
        user_prompt = user_message

    system_prompt = STREAM_SYSTEM_PROMPT
    if db:
        try:
            portfolio_context = build_portfolio_context(db)
            if portfolio_context:
                system_prompt += f"\n\n{portfolio_context}"
        except Exception:
            pass

    messages = [{"role": "system", "content": system_prompt}]
    history = _truncate_history(conversation_history or [], MAX_HISTORY_PAIRS)
    messages.extend(history)
    messages.append({"role": "user", "content": user_prompt})

    # --- Phase 3: Stream from DeepSeek ---
    full_reply = ""
    logger = logging.getLogger("wechat")
    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": messages,
                "temperature": 0.4,
                "max_tokens": 1200,
                "stream": True,
            },
            timeout=25,
            stream=True,
        )

        for raw_line in resp.iter_lines():
            if not raw_line:
                continue
            # curl_cffi iter_lines returns bytes
            line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
            line = line.strip()
            if not line:
                continue
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                chunk = json.loads(data_str)
                if "choices" in chunk and chunk["choices"]:
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_reply += content
                        yield _sse_chunk(content)
            except json.JSONDecodeError:
                continue

    except Exception as e:
        error_msg = str(e).lower()
        if "timeout" in error_msg or "timed out" in error_msg:
            if full_reply:
                full_reply += FRIENDLY_TIMEOUT_MSG
                yield _sse_chunk(FRIENDLY_TIMEOUT_MSG)
            else:
                full_reply = FRIENDLY_TIMEOUT_MSG
                yield _sse_chunk(FRIENDLY_TIMEOUT_MSG)
        else:
            logger.error(f"Stream error: {e}")
            err = ERROR_MESSAGES["general"]
            if not full_reply:
                full_reply = err
                yield _sse_chunk(err)

    # --- Phase 4: Truncate if too long ---
    if full_reply:
        full_reply = _truncate_response(full_reply)

    yield _sse_done()

    # Store metadata for the route to persist
    yield f":__meta__{json.dumps({'full_reply': full_reply, 'type': 'stock' if stock_data else 'general', 'stock_code': stock_data['code'] if stock_data else '', 'stock_name': stock_data['name'] if stock_data else '', 'market': stock_data['market'] if stock_data else '', 'quote': stock_data['quote'] if stock_data else None, 'kline': stock_data['kline'] if stock_data else None}, ensure_ascii=False)}\n\n"
