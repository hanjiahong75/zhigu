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
from ..prompts import detect_engine, load_prompt
from ..services.user_profile_service import build_profile_context as _build_profile
from ..config import MAX_HISTORY_PAIRS

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

TRUNCATION_SUFFIX = "…[回复过长已截断]"
MAX_RESPONSE_UTF8_BYTES = 2000

CHAT_SYSTEM_PROMPT = """你是"知股"，一位专业、严谨的A股智能投研助手。

## 输出铁律（不可违反）

### 格式规范
1. **结论先行**：每条回答首句必须是你的核心判断
2. **数据必带分析**：每给出一个数据点，必须紧跟一句分析说明它意味着什么。禁止只罗列数字不给解读
3. **引用来源**：引用数据时标注 [来源: xxx]

### 红线
1. 永远不输出"建议买入/卖出/持有/加仓/减仓"等操作指令
2. 永远不给精确目标价，改用定性描述（如"前期密集成交区附近"）
3. 数据缺失时明确说"该维度数据不足，无法判断"，禁止用"通常/一般"等词猜测

### 合规声明（每条分析末尾必须附加）
> 以上内容由 AI 基于公开数据生成，不构成任何投资建议。请充分评估自身风险承受能力，自行投资决策并独立承担投资风险。

## 回答风格
- 精准简洁（500字以内），关键结论用**加粗**标出
- 正面信号和反面风险并列呈现
- 能力范围：A股个股分析、市场指数概况、板块研判、投资知识科普"""

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


# Red-line violation patterns → weak-bias replacement
_SANITIZE_RULES = [
    # Operation commands (specific patterns first)
    (r"强烈建议买入", "当前技术面呈现积极信号，"),
    (r"强烈建议卖出", "当前风险信号较强，"),
    (r"强烈建议持有", "综合来看暂无明显方向信号，"),
    (r"强烈建议", "综合来看"),
    (r"建议买入", "呈现积极信号"),
    (r"建议卖出", "呈现风险信号"),
    (r"建议持有", "当前暂无明显方向信号"),
    (r"建议加仓", "若看好可关注"),
    (r"建议减仓", "若担忧可关注风险"),
    (r"建议清仓", "风险信号较强"),
    (r"可以买入", "技术面呈现"),
    (r"可以卖出", "风险面呈现"),
    (r"推荐买入", "值得关注"),
    (r"推荐卖出", "需警惕"),
    # Price targets
    (r"目标价[^\d]*\d+[\.\d]*\s*元?", "估值参考区间"),
    (r"支撑位[^\d]*\d+[\.\d]*", "前期密集成交区附近"),
    (r"压力位[^\d]*\d+[\.\d]*", "上方密集成交区附近"),
    (r"止损[^\d]*\d+[\.\d]*", "风险控制参考位"),
    # Hallucination indicators (specific patterns first)
    (r"根据历史经验", "从数据来看"),
    (r"一般来说", "从当前数据来看"),
    (r"通常情况下", "当前数据显示"),
    (r"通常情况", "当前数据显示"),
    (r"通常来说", "当前来看"),
    (r"通常来看", "当前来看"),
    (r"大概率", "可能"),
    (r"通常", "当前数据"),
]

def _sanitize_response(text: str) -> str:
    """Post-process LLM output to catch and fix remaining red-line violations."""
    import re
    sanitized = text
    for pattern, replacement in _SANITIZE_RULES:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    return sanitized


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
                kline = get_kline_data(code, market, 10000, "101")
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
                    kline = get_kline_data(code, market, 10000, "101")
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
            # Inject user profile for R10 appropriateness
            profile_context = _build_profile(db)
            if profile_context:
                system_prompt += f"\n\n{profile_context}"
        except Exception:
            pass
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
        full_reply = _sanitize_response(_truncate_response(full_reply))

    yield _sse_done()

    # Store metadata for the route to persist
    yield f":__meta__{json.dumps({'full_reply': full_reply, 'type': 'stock' if stock_data else 'general', 'stock_code': stock_data['code'] if stock_data else '', 'stock_name': stock_data['name'] if stock_data else '', 'market': stock_data['market'] if stock_data else '', 'quote': stock_data['quote'] if stock_data else None, 'kline': stock_data['kline'] if stock_data else None}, ensure_ascii=False)}\n\n"

# --- Agent mode: Function Calling ---

from .agent_tools import AGENT_TOOLS, AGENT_SYSTEM_PROMPT, execute_tool

MAX_AGENT_ITERATIONS = 5
AGENT_TIMEOUT_SECONDS = 60


async def chat_agent(
    user_message: str,
    conversation_history: list[dict] = None,
    thread_id: str = "",
    db: Session = None,
) -> dict:
    """Agent chat with function calling (non-streaming)."""
    if not DEEPSEEK_API_KEY:
        return {"reply": "**错误**：未配置 DeepSeek API Key", "type": "error"}

    system_prompt = AGENT_SYSTEM_PROMPT

    # Inject analysis engine template based on user intent
    engine = detect_engine(user_message)
    if engine == "combined":
        combined = load_prompt("combined")
        if combined:
            system_prompt += f"\n\n{combined}"
    elif engine:
        template = load_prompt(engine)
        if template:
            system_prompt += f"\n\n## 分析引擎指引\n{template}"

    if db:
        try:
            # Inject user profile for R10 appropriateness
            profile_context = _build_profile(db)
            if profile_context:
                system_prompt += f"\n\n{profile_context}"
        except Exception:
            pass
        try:
            portfolio_context = build_portfolio_context(db)
            if portfolio_context:
                system_prompt += f"\n\n{portfolio_context}"
        except Exception:
            pass

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history[-20:])
    messages.append({"role": "user", "content": user_message})

    logger = logging.getLogger("wechat")
    stock_info = {"code": "", "name": "", "market": "sz"}  # Track detected stock

    for iteration in range(MAX_AGENT_ITERATIONS):
        logger.info(f"Agent iteration {iteration + 1}/{MAX_AGENT_ITERATIONS} thread={thread_id}")

        try:
            resp = requests.post(
                f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "tools": AGENT_TOOLS,
                    "temperature": 0.4,
                    "max_tokens": 1200,
                },
                timeout=AGENT_TIMEOUT_SECONDS,
            )
            data = resp.json()
        except Exception as e:
            logger.error(f"Agent API error (iteration {iteration}): {e}")
            return {"reply": "AI 服务暂时不可用，请稍后再试", "type": "error"}

        if "choices" not in data or not data["choices"]:
            return {"reply": "AI 响应异常，请重试", "type": "error"}

        choice = data["choices"][0]
        message = choice.get("message", {})

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])
        if tool_calls:
            # Record assistant message with tool_calls
            assistant_msg = {
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
            }
            messages.append(assistant_msg)

            # Execute each tool
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                tool_result = execute_tool(func_name, args)
                # Track stock info from tool calls
                if func_name == "search_stock":
                    try:
                        results = json.loads(tool_result)
                        if results and len(results) > 0:
                            first = results[0]
                            stock_info["code"] = first.get("code", "")
                            stock_info["name"] = first.get("name", "")
                            stock_info["market"] = "sh" if first.get("code", "").startswith(("6","9")) else "sz"
                    except Exception:
                        pass
                elif func_name == "get_stock_quote":
                    stock_info["code"] = args.get("code", stock_info["code"])
                    stock_info["name"] = args.get("name", stock_info.get("name", ""))
                    stock_info["market"] = args.get("market", stock_info.get("market", "sz"))
                elif func_name == "get_kline_data" or func_name == "get_technical_indicators" or func_name == "get_portfolio_risk":
                    stock_info["code"] = args.get("code", stock_info["code"])
                    stock_info["market"] = args.get("market", stock_info.get("market", "sz"))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })
                logger.info(f"  Tool: {func_name}({str(args)[:60]}) -> {len(tool_result)} chars")
        else:
            # No tool calls — final answer
            reply = message.get("content", "")
            if not reply:
                reply = "抱歉，我暂时无法回答这个问题，请换个方式提问。"
            # If a stock was mentioned, attach market data
            response = {"reply": reply, "type": "general"}
            if stock_info["code"]:
                try:
                    from .stock_data import get_realtime_quote, get_kline_data
                    from .technical import calc_all_indicators
                    quote = get_realtime_quote(stock_info["code"], stock_info["market"])
                    kline = get_kline_data(stock_info["code"], stock_info["market"], 10000)
                    indicators = calc_all_indicators(kline) if kline else None
                    response.update({
                        "type": "stock",
                        "stock_code": stock_info["code"],
                        "stock_name": stock_info["name"] or (quote["name"] if quote else stock_info["code"]),
                        "market": stock_info["market"],
                        "quote": quote,
                        "kline": kline,
                        "indicators": indicators,
                    })
                except Exception:
                    pass
            return response

    # Exhausted iterations without final answer
    return {"reply": "分析过程较长，请稍后重新提问（可尝试简化问题）", "type": "error"}


def _build_stock_meta(stock_info: dict) -> dict:
    """Attach quote/kline/indicators for a detected stock (shared by chat_agent paths)."""
    meta = {"type": "general", "stock_code": "", "stock_name": "", "market": "",
            "quote": None, "kline": None, "indicators": None}
    if not stock_info.get("code"):
        return meta
    try:
        from .stock_data import get_realtime_quote, get_kline_data
        from .technical import calc_all_indicators
        quote = get_realtime_quote(stock_info["code"], stock_info["market"])
        kline = get_kline_data(stock_info["code"], stock_info["market"], 10000)
        indicators = calc_all_indicators(kline) if kline else None
        meta.update({
            "type": "stock",
            "stock_code": stock_info["code"],
            "stock_name": stock_info["name"] or (quote["name"] if quote else stock_info["code"]),
            "market": stock_info["market"],
            "quote": quote,
            "kline": kline,
            "indicators": indicators,
        })
    except Exception:
        pass
    return meta


async def chat_agent_stream(
    user_message: str,
    conversation_history: list[dict] = None,
    thread_id: str = "",
    db: Session = None,
) -> AsyncGenerator[str, None]:
    """Agent chat with function calling (streaming).
    
    Tool execution rounds are non-streaming.
    Final response round is streamed.
    """
    stock_info = {"code": "", "name": "", "market": "sz"}  # Track detected stock

    def _sse_chunk(content: str, finish_reason: str = None) -> str:
        delta = {"content": content}
        choice = {"index": 0, "delta": delta}
        if finish_reason:
            choice["finish_reason"] = finish_reason
        return f"data: {json.dumps({'choices': [choice]})}\n\n"

    def _sse_done() -> str:
        return "data: [DONE]\n\n"

    if not DEEPSEEK_API_KEY:
        yield _sse_chunk("AI 服务暂时不可用，请稍后再试", "stop")
        yield _sse_done()
        return

    system_prompt = AGENT_SYSTEM_PROMPT

    # Inject analysis engine template based on user intent
    engine = detect_engine(user_message)
    if engine == "combined":
        combined = load_prompt("combined")
        if combined:
            system_prompt += f"\n\n{combined}"
    elif engine:
        template = load_prompt(engine)
        if template:
            system_prompt += f"\n\n## 分析引擎指引\n{template}"

    if db:
        try:
            # Inject user profile for R10 appropriateness
            profile_context = _build_profile(db)
            if profile_context:
                system_prompt += f"\n\n{profile_context}"
        except Exception:
            pass
        try:
            portfolio_context = build_portfolio_context(db)
            if portfolio_context:
                system_prompt += f"\n\n{portfolio_context}"
        except Exception:
            pass

    messages = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history[-20:])
    messages.append({"role": "user", "content": user_message})

    logger = logging.getLogger("wechat")

    # Phase 1: Tool execution loop (non-streaming)
    for iteration in range(MAX_AGENT_ITERATIONS):
        try:
            resp = requests.post(
                f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "tools": AGENT_TOOLS,
                    "temperature": 0.4,
                    "max_tokens": 1200,
                },
                timeout=AGENT_TIMEOUT_SECONDS,
            )
            data = resp.json()
        except Exception as e:
            logger.error(f"Agent stream API error: {e}")
            yield _sse_chunk("AI 服务暂时不可用，请稍后再试", "stop")
            yield _sse_done()
            return

        if "choices" not in data or not data["choices"]:
            yield _sse_chunk("AI 响应异常，请重试", "stop")
            yield _sse_done()
            return

        choice = data["choices"][0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls", [])

        if tool_calls:
            assistant_msg = {
                "role": "assistant",
                "content": message.get("content") or "",
                "tool_calls": tool_calls,
            }
            messages.append(assistant_msg)

            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                tool_result = execute_tool(func_name, args)
                # Track stock info from tool calls
                if func_name == "search_stock":
                    try:
                        results = json.loads(tool_result)
                        if results and len(results) > 0:
                            first = results[0]
                            stock_info["code"] = first.get("code", "")
                            stock_info["name"] = first.get("name", "")
                            stock_info["market"] = "sh" if first.get("code", "").startswith(("6","9")) else "sz"
                    except Exception:
                        pass
                elif func_name == "get_stock_quote":
                    stock_info["code"] = args.get("code", stock_info["code"])
                    stock_info["name"] = args.get("name", stock_info.get("name", ""))
                    stock_info["market"] = args.get("market", stock_info.get("market", "sz"))
                elif func_name == "get_kline_data" or func_name == "get_technical_indicators" or func_name == "get_portfolio_risk":
                    stock_info["code"] = args.get("code", stock_info["code"])
                    stock_info["market"] = args.get("market", stock_info.get("market", "sz"))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })
                logger.info(f"  Stream tool: {func_name}({str(args)[:60]}) -> {len(tool_result)} chars")
        else:
            # Final answer — stream it
            full_reply = ""

            try:
                stream_resp = requests.post(
                    f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-chat",
                        "messages": messages,
                        "temperature": 0.4,
                        "max_tokens": 1200,
                        "stream": True,
                    },
                    timeout=AGENT_TIMEOUT_SECONDS,
                    stream=True,
                )

                for raw_line in stream_resp.iter_lines():
                    if not raw_line:
                        continue
                    line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                    line = line.strip()
                    if not line or not line.startswith("data: "):
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
                    yield _sse_chunk("处理中，请稍后重新提问", "stop")
                else:
                    logger.error(f"Agent stream error on final: {e}")
                    yield _sse_chunk("服务暂时不可用，请稍后再试", "stop")

            full_reply = _sanitize_response(_truncate_response(full_reply))
            yield _sse_done()

            # Metadata for persistence
            meta = _build_stock_meta(stock_info)
            meta["full_reply"] = full_reply
            yield f":__meta__{json.dumps(meta, ensure_ascii=False)}\n\n"
            return

    # Exhausted
    yield _sse_chunk("分析过程较长，请稍后重新提问", "stop")
    yield _sse_done()
