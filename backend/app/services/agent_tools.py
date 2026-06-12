"""Agent tools: OpenAI-compatible function calling definitions + executor."""

import json
import logging
from sqlalchemy.orm import Session

from .stock_data import search_stocks, get_realtime_quote, get_kline_data, get_market_indices
from .technical import calc_all_indicators
from .retrieval import build_context_prompt
from ..models.database import SessionLocal
from ..models.stock import WatchlistItem
from .portfolio_service import get_portfolio_with_prices, calc_portfolio_risk

logger = logging.getLogger("wechat")

# ── Tool definitions (OpenAI function calling format) ──

AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_stock",
            "description": "根据名称或代码搜索A股股票，返回匹配的股票列表（代码、名称、市场）",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "股票名称或代码关键词，如茅台、300308"}
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_quote",
            "description": "获取A股实时行情：最新价、涨跌幅、开盘价、最高价、最低价、成交额、换手率",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码，如300308"},
                    "market": {"type": "string", "description": "市场，sh(上海)或sz(深圳)，默认sz"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_kline_data",
            "description": "获取A股历史K线数据，包含日期、开盘价、收盘价、最高价、最低价、成交量",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"},
                    "market": {"type": "string", "description": "市场，默认sz"},
                    "days": {"type": "integer", "description": "获取天数，默认60"},
                    "klt": {"type": "string", "description": "周期：101日K、102周K、103月K，默认101"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_technical_indicators",
            "description": "计算股票技术指标：MA均线、MACD、RSI、布林带等",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"},
                    "market": {"type": "string", "description": "市场，默认sz"},
                    "days": {"type": "integer", "description": "计算天数，默认60"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_overview",
            "description": "获取A股主要市场指数概况：上证、深证、创业板等",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_watchlist",
            "description": "获取用户的自选股列表",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "获取用户持仓信息：股票名称、数量、成本价、当前价、盈亏、总市值",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_portfolio_risk",
            "description": "获取持仓风险指标：夏普比率、最大回撤",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_stock_memories",
            "description": "从历史分析记忆中检索某只股票的过往分析记录",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"},
                    "query": {"type": "string", "description": "检索关键词"},
                    "max_items": {"type": "integer", "description": "返回条数，默认5"}
                },
                "required": ["code"]
            }
        }
    },
]

AGENT_SYSTEM_PROMPT = """你是"知股"，一位专业、简洁的A股智能投研助手。

你有以下工具可以调用：
- search_stock: 搜索股票
- get_stock_quote: 获取实时行情
- get_kline_data: 获取K线数据
- get_technical_indicators: 计算技术指标
- get_market_overview: 市场指数概况
- get_watchlist: 自选股列表
- get_portfolio: 持仓信息
- get_portfolio_risk: 持仓风险指标
- retrieve_stock_memories: 历史分析记忆

规则：
1. 当用户问股票时，先搜股票代码，然后获取行情和技术指标，综合分析后回复
2. 当用户问持仓/风险时，调取持仓数据
3. 回答精准简洁（500字以内），关键结论用**加粗**
4. 不推荐具体买卖操作，只给分析参考
5. 不为简单问候调用工具，直接回复
6. 只输出JSON格式中文，不要出现乱码"""


def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool by name and return JSON result string."""
    db = SessionLocal()
    try:
        if tool_name == "search_stock":
            keyword = arguments.get("keyword", "")
            results = search_stocks(keyword)
            if not results:
                return json.dumps({"found": False, "message": f"未找到与'{keyword}'相关的股票"}, ensure_ascii=False)
            top = results[:5]
            return json.dumps({
                "found": True,
                "stocks": [{"code": r["code"], "name": r["name"], "market": r.get("market", "sz")} for r in top],
            }, ensure_ascii=False)

        elif tool_name == "get_stock_quote":
            code = arguments.get("code", "")
            market = arguments.get("market", "sz")
            quote = get_realtime_quote(code, market)
            if not quote:
                return json.dumps({"error": f"未获取到{code}的行情"}, ensure_ascii=False)
            return json.dumps({
                "name": quote.get("name", ""),
                "code": code,
                "price": quote.get("price"),
                "change_pct": quote.get("change_pct"),
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "amount_yi": round(quote.get("amount", 0) / 1e8, 2) if quote.get("amount") else 0,
                "turnover": quote.get("turnover"),
            }, ensure_ascii=False)

        elif tool_name == "get_kline_data":
            code = arguments.get("code", "")
            market = arguments.get("market", "sz")
            days = arguments.get("days", 60)
            klt = arguments.get("klt", "101")
            kline = get_kline_data(code, market, days, klt)
            if not kline:
                return json.dumps({"error": f"未获取到{code}的K线数据"}, ensure_ascii=False)
            summary = {
                "total_bars": len(kline),
                "first_date": kline[0]["date"] if kline else "",
                "last_date": kline[-1]["date"] if kline else "",
                "latest_close": kline[-1]["close"] if kline else 0,
                "recent_5": [
                    {"date": b["date"], "close": b["close"], "volume": b.get("volume", 0)}
                    for b in kline[-5:]
                ] if len(kline) >= 5 else [],
            }
            return json.dumps(summary, ensure_ascii=False)

        elif tool_name == "get_technical_indicators":
            code = arguments.get("code", "")
            market = arguments.get("market", "sz")
            days = arguments.get("days", 60)
            kline = get_kline_data(code, market, days, "101")
            if not kline:
                return json.dumps({"error": f"未获取到{code}的指标数据"}, ensure_ascii=False)
            indicators = calc_all_indicators(kline)
            summary = {}
            if "ma" in indicators:
                ma = indicators["ma"]
                summary["ma5"] = ma.get("ma5", [])[-1] if ma.get("ma5") else None
                summary["ma20"] = ma.get("ma20", [])[-1] if ma.get("ma20") else None
            if "macd" in indicators:
                macd = indicators["macd"]
                summary["macd_dif"] = macd.get("dif", [])[-1] if macd.get("dif") else None
                summary["macd_dea"] = macd.get("dea", [])[-1] if macd.get("dea") else None
                summary["macd_hist"] = macd.get("macd", [])[-1] if macd.get("macd") else None
            if "rsi" in indicators:
                rsi = indicators["rsi"]
                summary["rsi_6"] = rsi.get("rsi6", [])[-1] if rsi.get("rsi6") else None
                summary["rsi_14"] = rsi.get("rsi14", [])[-1] if rsi.get("rsi14") else None
            if "boll" in indicators:
                boll = indicators["boll"]
                summary["boll_upper"] = boll.get("upper", [])[-1] if boll.get("upper") else None
                summary["boll_mid"] = boll.get("mid", [])[-1] if boll.get("mid") else None
                summary["boll_lower"] = boll.get("lower", [])[-1] if boll.get("lower") else None
            return json.dumps(summary, ensure_ascii=False)

        elif tool_name == "get_market_overview":
            indices = get_market_indices()
            if not indices:
                return json.dumps({"error": "未获取到市场指数"}, ensure_ascii=False)
            overview = []
            for idx in indices[:5]:
                overview.append({
                    "name": idx.get("name", ""),
                    "price": idx.get("price"),
                    "change_pct": idx.get("change_pct"),
                })
            return json.dumps({"indices": overview}, ensure_ascii=False)

        elif tool_name == "get_watchlist":
            items = db.query(WatchlistItem).filter(WatchlistItem.is_active == True).all()
            return json.dumps({
                "count": len(items),
                "stocks": [{"code": i.code, "name": i.name, "market": i.market} for i in items],
            }, ensure_ascii=False)

        elif tool_name == "get_portfolio":
            portfolio = get_portfolio_with_prices(db)
            if not portfolio or not portfolio.get("items"):
                return json.dumps({"has_portfolio": False, "message": "暂无持仓数据"}, ensure_ascii=False)
            items = []
            for item in portfolio["items"]:
                items.append({
                    "name": item.get("stock_name", ""),
                    "code": item.get("stock_code", ""),
                    "asset_type": item.get("asset_type", "stock"),
                    "quantity": item.get("quantity", 0),
                    "cost_price": item.get("cost_price", 0),
                    "current_price": item.get("current_price", 0),
                    "profit": item.get("profit", 0),
                })
            return json.dumps({
                "has_portfolio": True,
                "total_value": portfolio.get("total_value", 0),
                "total_profit": portfolio.get("total_profit", 0),
                "total_profit_pct": portfolio.get("total_profit_pct", 0),
                "items": items,
            }, ensure_ascii=False)

        elif tool_name == "get_portfolio_risk":
            risk = calc_portfolio_risk(db)
            return json.dumps(risk, ensure_ascii=False)

        elif tool_name == "retrieve_stock_memories":
            code = arguments.get("code", "")
            query = arguments.get("query", "")
            max_items = arguments.get("max_items", 5)
            context = build_context_prompt(code, query, max_items)
            if not context:
                return json.dumps({"found": False, "message": f"未找到{code}的历史分析"}, ensure_ascii=False)
            return json.dumps({"found": True, "context": context[:800]}, ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Tool execution error: {tool_name} -> {e}")
        return json.dumps({"error": f"工具执行失败: {str(e)[:100]}"}, ensure_ascii=False)
    finally:
        db.close()
