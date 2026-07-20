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
from .global_data import (
    get_global_quote, search_global_stocks, get_global_kline,
    get_global_indicators, get_global_indices as _get_global_indices,
)


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
                    "days": {"type": "integer", "description": "获取天数，默认10000（上市至今）"},
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
                    "days": {"type": "integer", "description": "计算天数，默认10000（上市至今）"}
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
    {
        "type": "function",
        "function": {
            "name": "search_stock_news",
            "description": "搜索股票相关新闻、公告，返回标题、摘要、来源、时间",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码，如300308或600519"},
                    "max_results": {"type": "integer", "description": "返回条数，默认5"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_data",
            "description": "获取股票财务数据：营收、净利润、EPS等关键指标的最新几期数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码，如300308或600519"}
                },
                "required": ["code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_industry_pe",
            "description": "获取A股各行业市盈率数据（加权平均和中位数），用于判断个股估值在行业中的位置",
            "parameters": {
                "type": "object",
                "properties": {
                    "industry": {"type": "string", "description": "行业关键词，如'半导体'、'白酒'、'银行'，留空返回全部行业"}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_global_stock",
            "description": "搜索海外股票（港股/美股/日股/韩股），返回代码和名称",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "股票名称或代码关键词"},
                    "market": {"type": "string", "description": "市场：hk(港股)/us(美股)/jp(日股)/kr(韩股)，默认hk"}
                },
                "required": ["keyword"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_global_quote",
            "description": "获取海外股票实时行情：最新价、涨跌幅、成交量",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"},
                    "market": {"type": "string", "description": "市场：hk/us/jp/kr"}
                },
                "required": ["code", "market"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_global_kline",
            "description": "获取海外股票历史K线数据",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"},
                    "market": {"type": "string", "description": "市场：hk/us/jp/kr"},
                    "days": {"type": "integer", "description": "获取天数，默认120"}
                },
                "required": ["code", "market"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_global_indicators",
            "description": "获取海外股票技术指标和多空信号（RSI/MACD/布林带/ADX/随机指标 + BUY/SELL推荐）",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "股票代码"},
                    "market": {"type": "string", "description": "市场：hk/us/jp/kr"}
                },
                "required": ["code", "market"]
            }
        }
    },
]


AGENT_SYSTEM_PROMPT = """你是"知股"，一位专业、严谨的A股智能投研助手。

## 可用工具
- search_stock: 搜索股票代码/名称
- get_stock_quote: 实时行情（最新价、涨跌幅、成交额、换手率等）
- get_kline_data: 历史K线数据（日/周/月）
- get_technical_indicators: 技术指标（MA、MACD、RSI、布林带）
- get_market_overview: 市场指数概况
- get_watchlist: 自选股列表
- get_portfolio: 持仓信息
- get_portfolio_risk: 持仓风险指标
- retrieve_stock_memories: 历史分析记忆
- search_stock_news: 搜索股票新闻/公告
- get_financial_data: 财务数据（营收/净利润/EPS）
- get_industry_pe: 行业市盈率对比
- search_global_stock: 搜索海外股票（港股/美股/日股/韩股）
- get_global_quote: 海外实时行情
- get_global_kline: 海外K线数据
- get_global_indicators: 海外技术指标 + 多空信号

## 工作流程
1. 用户提及股票时：先 search_stock 确认代码 → 获取行情 + K线 + 指标 → 综合分析
2. 用户问持仓/风险时：调取持仓/风险数据
3. 简单问候/闲聊：直接回复，不调工具

## 输出铁律（不可违反）

### 格式规范
1. **结论先行**：每条回答首句必须是你的核心判断。例如"XX目前呈现积极信号，短期趋势偏强"或"XX当前动能不足，处于弱势整理"
2. **数据必带分析**：每给出一个数据点，必须紧跟一句分析说明它意味着什么。禁止只罗列数字不给解读
3. **引用来源**：引用工具数据时标注来源，格式为 [来源: 工具名]，如 [来源: get_stock_quote]

### 红线（违反即不合格）
1. 永远不输出"建议买入/卖出/持有/加仓/减仓"等操作指令
2. 永远不给精确目标价或具体价位（如"420是支撑位"），改用定性描述（如"前期密集成交区附近"）
3. 永远不说"根据历史经验/通常/一般/大概率"等词来猜测数据——数据缺失时明确说"该维度数据不足，无法判断"
4. 数据查不到就是查不到，禁止用模糊语言兜底

### 弱偏向措辞规范
- ✅ 正确："若成交量持续放大，上行概率可能增加"
- ❌ 错误："建议买入" / "目标价50元" / "支撑位在42.5"

### 合规声明（每条分析末尾必须附加）
> 以上内容由 AI 基于公开数据生成，不构成任何投资建议。请充分评估自身风险承受能力，自行投资决策并独立承担投资风险。

## 回答风格
- 用数据和逻辑说话，结论有依据
- 关键结论用**加粗**标出
- 正面信号和反面风险并列呈现
- 能力范围：A股个股分析、市场指数、板块研判、投资知识科普

## 市场识别
- 用户提及港股/香港/港交所/HK/恒生 -> 使用 global 系列工具，market="hk"
- 用户提及美股/纳斯达克/纽交所/美国 -> 使用 global 系列工具，market="us"
- 用户提及日股/东京/日本 -> market="jp"
- 用户提及韩股/韩国/首尔 -> market="kr"
- 用户提及A股/沪深 -> 使用原有A股工具（search_stock/get_stock_quote等）"""


def _search_stock_news_impl(code: str, max_results: int = 5) -> list[dict]:
    """Search for stock-related news using akshare (eastmoney source)."""
    try:
        import akshare as ak
        # stock_news_em takes plain code like "300308", not "SZ300308"
        code_plain = code.replace("SZ", "").replace("SH", "").replace("sz", "").replace("sh", "")
        df = ak.stock_news_em(symbol=code_plain)
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.head(max_results).iterrows():
            results.append({
                "title": str(row.get("新闻标题", "")),
                "snippet": str(row.get("新闻内容", ""))[:300],
                "source": str(row.get("文章来源", "")),
                "time": str(row.get("发布时间", "")),
                "url": str(row.get("新闻链接", "")),
            })
        return results
    except Exception as e:
        logger.error(f"News search failed: {e}")
        return []


def execute_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool by name and return JSON result string."""
    db = SessionLocal()
    try:
        if tool_name == "search_stock":
            keyword = arguments.get("keyword", "")
            results = search_stocks(keyword)
            if not results:
                return json.dumps({
                    "found": False,
                    "action": "STOP",
                    "message": f"未找到与'{keyword}'相关的股票，请用户确认名称或代码后重试。不要再尝试其他工具分析该股票。"
                }, ensure_ascii=False)
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
            days = arguments.get("days", 10000)
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
            days = arguments.get("days", 10000)
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

        elif tool_name == "search_stock_news":
            code = arguments.get("code", arguments.get("keyword", ""))
            max_results = arguments.get("max_results", 5)
            results = _search_stock_news_impl(code, max_results)
            if not results:
                return json.dumps({"found": False, "message": f"未找到与'{code}'相关的新闻"}, ensure_ascii=False)
            return json.dumps({
                "found": True,
                "count": len(results),
                "news": results,
            }, ensure_ascii=False)

        elif tool_name == "get_financial_data":
            code = arguments.get("code", "")
            import akshare as ak
            try:
                df = ak.stock_financial_abstract(symbol=code)
            except Exception:
                return json.dumps({"found": False, "message": f"未获取到{code}的财务数据"}, ensure_ascii=False)
            if df is None or df.empty:
                return json.dumps({"found": False, "message": f"未获取到{code}的财务数据"}, ensure_ascii=False)

            # Get latest 4 period columns
            date_cols = [c for c in df.columns if c not in ['选项', '指标']][:4]

            # Extract key indicators
            indicators = {}
            for _, row in df.iterrows():
                name = str(row['指标'])
                if name == '净资产收益率(ROE)' and 'ROE' not in indicators:
                    indicators['ROE'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']
                elif name == '毛利率' and '毛利率' not in indicators:
                    indicators['毛利率'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']
                elif name == '销售净利率' and '净利率' not in indicators:
                    indicators['净利率'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']
                elif name == '资产负债率' and '资产负债率' not in indicators:
                    indicators['资产负债率'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']
                elif name == '营业总收入增长率' and '营收增长率' not in indicators:
                    indicators['营收增长率'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']
                elif name == '归属母公司净利润增长率' and '净利增长率' not in indicators:
                    indicators['净利增长率'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']
                elif name == '基本每股收益' and 'EPS' not in indicators:
                    indicators['EPS'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']
                elif name == '归母净利润' and '归母净利润' not in indicators:
                    indicators['归母净利润'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']
                elif name == '营业总收入' and '营业总收入' not in indicators:
                    indicators['营业总收入'] = [float(row[c]) for c in date_cols if row[c] and str(row[c]) != 'nan']

            if not indicators:
                return json.dumps({"found": False, "message": "未提取到有效财务指标"}, ensure_ascii=False)

            # Format periods array from indicator data
            periods = []
            for i, date_col in enumerate(date_cols):
                period = {"report_date": date_col}
                for key, vals in indicators.items():
                    if i < len(vals):
                        period[key] = vals[i]
                periods.append(period)

            return json.dumps({
                "found": True,
                "periods": periods,
                "latest": {
                    k: v[0] if v else None
                    for k, v in indicators.items()
                },
            }, ensure_ascii=False)

        elif tool_name == "get_industry_pe":
            industry = arguments.get("industry", "")
            import akshare as ak
            import pandas as pd
            from datetime import datetime
            from datetime import timedelta
            df = None
            # Try recent dates (today and last 5 trading days) in case today has no data
            for days_back in range(6):
                try:
                    date_str = (datetime.now() - timedelta(days=days_back)).strftime("%Y%m%d")
                    df = ak.stock_industry_pe_ratio_cninfo(symbol="证监会行业分类", date=date_str)
                    if df is not None and len(df) > 0:
                        break
                except Exception:
                    continue
            if df is None or len(df) == 0:
                return json.dumps({"found": False, "message": "行业PE数据暂不可用（近期无数据）"}, ensure_ascii=False)
            if df is None or df.empty:
                return json.dumps({"found": False, "message": "未获取到行业PE数据"}, ensure_ascii=False)
            # Filter by industry keyword if provided (each char must appear in order)
            if industry:
                mask = df["行业名称"].str.contains(industry, na=False)
                if not mask.any():
                    # Fallback: try matching any single char from the keyword
                    for ch in industry:
                        mask = df["行业名称"].str.contains(ch, na=False)
                        if mask.any():
                            break
                df = df[mask].copy() if mask.any() else df.iloc[:0].copy()
            if len(df) == 0:
                return json.dumps({"found": False, "message": f"未找到包含'{industry}'的行业"}, ensure_ascii=False)
            # Take second-level industries (行业层级==2) for cleaner results
            level2 = df[df["行业层级"] == 2] if "行业层级" in df.columns else df
            source = level2 if len(level2) > 0 else df
            industries = []
            for _, row in source.head(20).iterrows():
                industries.append({
                    "name": str(row.get("行业名称", "")),
                    "company_count": int(float(row.get("纳入计算公司数量", 0) or 0)) if pd.notna(row.get("纳入计算公司数量")) else 0,
                    "pe_weighted": round(float(row.get("静态市盈率-加权平均", 0) or 0), 1) if pd.notna(row.get("静态市盈率-加权平均")) else None,
                    "pe_median": round(float(row.get("静态市盈率-中位数", 0) or 0), 1) if pd.notna(row.get("静态市盈率-中位数")) else None,
                })
            return json.dumps({
                "found": True,
                "count": len(industries),
                "industries": industries,
            }, ensure_ascii=False)

        elif tool_name == "search_global_stock":
            keyword = arguments.get("keyword", "")
            market = arguments.get("market", "hk")
            results = search_global_stocks(keyword, market)
            if not results:
                return json.dumps({"found": False, "message": f"未找到{market}市场中与'{keyword}'相关的股票"}, ensure_ascii=False)
            return json.dumps({"found": True, "count": len(results), "stocks": results}, ensure_ascii=False)

        elif tool_name == "get_global_quote":
            code = arguments.get("code", "")
            market = arguments.get("market", "hk")
            quote = get_global_quote(code, market)
            if not quote:
                return json.dumps({"found": False, "message": f"未获取到{market}:{code}的行情"}, ensure_ascii=False)
            return json.dumps({"found": True, "quote": quote}, ensure_ascii=False)

        elif tool_name == "get_global_kline":
            code = arguments.get("code", "")
            market = arguments.get("market", "hk")
            days = arguments.get("days", 120)
            kline = get_global_kline(code, market, days)
            if not kline:
                return json.dumps({"found": False, "message": f"未获取到{market}:{code}的K线数据"}, ensure_ascii=False)
            recent = [
                {"date": k["date"], "open": k["open"], "close": k["close"],
                 "high": k["high"], "low": k["low"], "volume": k["volume"]}
                for k in kline[-5:]
            ] if len(kline) >= 5 else kline
            return json.dumps({"found": True, "count": len(kline), "recent": recent}, ensure_ascii=False)

        elif tool_name == "get_global_indicators":
            code = arguments.get("code", "")
            market = arguments.get("market", "hk")
            indicators = get_global_indicators(code, market)
            if "error" in indicators:
                return json.dumps({"found": False, "message": indicators["error"]}, ensure_ascii=False)
            return json.dumps({"found": True, "indicators": indicators}, ensure_ascii=False)

        else:
            return json.dumps({"error": f"未知工具: {tool_name}"}, ensure_ascii=False)

    except Exception as e:
        logger.error(f"Tool execution error: {tool_name} -> {e}")
        return json.dumps({"error": f"工具执行失败: {str(e)[:100]}"}, ensure_ascii=False)
    finally:
        db.close()
