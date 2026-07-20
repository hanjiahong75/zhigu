"""AI analysis service using DeepSeek API."""
import os
from curl_cffi import requests
from typing import Optional

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

SYSTEM_PROMPT = """你是专业的A股投研分析师。请对提供的股票数据进行多维度结构化分析。

## 输出铁律（不可违反）

### 格式规范
1. **结论先行**：第一句必须是你的核心判断，如"XX目前呈现积极信号，短期趋势偏强"
2. **数据必带分析**：每个数据点后紧跟一句分析，说明它意味着什么
3. **引用来源**：引用数据时标注 [来源: xxx]

### 红线
1. 永远不输出"建议买入/卖出/持有/加仓/减仓"等操作指令
2. 永远不给精确目标价，改用定性描述（如"前期密集成交区附近"）
3. 数据缺失时明确说"该维度数据不足，无法判断"

### 分析维度
## 技术面判断
- 趋势判断（结合MA排列和MACD状态）
- RSI超买超卖状态
- 成交量分析

## 基本面概况
- 估值水平参考
- 市值规模

## 资金面
- 今日资金流向判断
- 换手率含义

## 综合研判
- 短期（1-5天）趋势偏向 + 关键信号
- 中期（1-4周）趋势预判
- 正面信号与反面风险并列呈现
- 关键风险提示

### 合规声明（末尾必须附加）
> 以上内容由 AI 基于公开数据生成，不构成任何投资建议。请充分评估自身风险承受能力，自行投资决策并独立承担投资风险。

请用中文输出，控制在800字以内，使用Markdown格式。"""


def build_indicator_summary(indicators: dict) -> str:
    """Build a concise indicator summary for the AI prompt."""
    if "error" in indicators:
        return "指标数据不足"
    parts = []
    rsi = indicators.get("rsi", {})
    rsi14 = rsi.get("rsi14", [])
    if rsi14 and rsi14[-1] is not None:
        val = rsi14[-1]
        state = "超买" if val > 70 else ("超卖" if val < 30 else "中性")
        parts.append(f"RSI(14): {val:.1f} ({state})")

    macd = indicators.get("macd", {})
    dif = macd.get("dif", [])
    dea = macd.get("dea", [])
    if dif and dea and dif[-1] is not None and dea[-1] is not None:
        dif_val = dif[-1]
        dea_val = dea[-1]
        if dif[-2] and dea[-2]:
            if dif[-2] <= dea[-2] and dif_val > dea_val:
                parts.append("MACD: 金叉")
            elif dif[-2] >= dea[-2] and dif_val < dea_val:
                parts.append("MACD: 死叉")
            else:
                trend = "多头" if dif_val > dea_val else "空头"
                parts.append(f"MACD: {trend}排列")
        else:
            trend = "多头" if dif_val > dea_val else "空头"
            parts.append(f"MACD: {trend}排列")

    boll = indicators.get("bollinger", {})
    upper = boll.get("upper", [])
    mid = boll.get("mid", [])
    lower = boll.get("lower", [])
    if upper and upper[-1] is not None:
        parts.append(f"布林带上轨: {upper[-1]}, 中轨: {mid[-1]}, 下轨: {lower[-1]}")

    ma = indicators.get("ma", {})
    ma5 = ma.get("ma5", [])
    ma20 = ma.get("ma20", [])
    if ma5 and ma20 and ma5[-1] and ma20[-1]:
        position = "多头" if ma5[-1] > ma20[-1] else "空头"
        parts.append(f"MA5({ma5[-1]:.1f}) vs MA20({ma20[-1]:.1f}): {position}排列")

    return "; ".join(parts) if parts else "指标数据不足"


async def get_analysis(
    stock_name: str,
    stock_code: str,
    kline_summary: str,
    quote: dict,
    indicators: Optional[dict] = None,
    memory_context: str = "",
) -> str:
    if not DEEPSEEK_API_KEY:
        return "错误：未配置DeepSeek API Key，请在环境变量中设置 DEEPSEEK_API_KEY"

    indicator_text = build_indicator_summary(indicators) if indicators else "暂无指标数据"

    user_prompt = f"""请分析以下股票：

股票名称：{stock_name}
股票代码：{stock_code}
最新价：{quote.get("price", "N/A")}元
涨跌幅：{quote.get("change_pct", "N/A")}%
今日开盘：{quote.get("open", "N/A")}
今日最高：{quote.get("high", "N/A")}
今日最低：{quote.get("low", "N/A")}
成交额：{quote.get("amount", "N/A")}元
换手率：{quote.get("turnover", "N/A")}%

技术指标摘要：
{indicator_text}

近期K线走势（近20日）：
{kline_summary}"""

    if memory_context:
        user_prompt += f"""

{memory_context}

请结合以上历史分析记录的上下文，给出本次的多维度专业投研分析。如果历史分析中有值得注意的趋势变化，请特别指出。"""

    else:
        user_prompt += """

请给出多维度专业投研分析。"""

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

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
            "max_tokens": 1500,
        },
        timeout=120,
    )
    data = resp.json()
    if "choices" in data and len(data["choices"]) > 0:
        return data["choices"][0]["message"]["content"]
    return f"AI分析失败：{data.get('error', {}).get('message', '未知错误')}"


def summarize_kline(kline_data: list[dict]) -> str:
    if not kline_data:
        return "无近期K线数据"
    recent = kline_data[-20:]
    lines = []
    for k in recent:
        lines.append(f"{k['date']} O:{k['open']} H:{k['high']} L:{k['low']} C:{k['close']} V:{k['volume']}")
    return "\n".join(lines)
