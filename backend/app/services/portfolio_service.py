"""Portfolio service: OCR + AI recognition + price updates + context building."""

import os
import json
import base64
import re
import logging
from curl_cffi import requests
from typing import Optional
from sqlalchemy.orm import Session

from ..models.database import SessionLocal
from ..models.stock import Portfolio, PortfolioItem
from .stock_data import get_realtime_quote

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

PARSE_PROMPT = """你是一个基金持仓截图解析器。请从OCR识别文本中提取所有基金持仓信息，忽略股票和ETF。

返回JSON数组格式：
[{{"stock_code":"基金代码","stock_name":"基金名称","holding_amount":持有金额,"cost_amount":买入金额,"holding_return":持仓收益,"daily_return":当日收益,"daily_return_pct":当日涨跌幅,"sector":"关联板块","asset_type":"fund"}}]

字段说明：
- stock_code: 基金代码（6位数字），必填，如无则填空字符串
- stock_name: 基金名称，必填
- holding_amount: 持有金额（元），如无则填0
- cost_amount: 买入金额/投入本金（元），如无则填0
- holding_return: 持仓收益/累计收益（元），正数为盈利负数为亏损，如无则填0
- daily_return: 当日收益（元），如无则填0
- daily_return_pct: 当日涨跌幅（2.5表示涨2.5%，-1.3表示跌1.3%），如无则填0
- sector: 关联板块/投资方向（如"新能源""半导体""消费""医疗"等），如无则填空字符串
- asset_type: 固定填"fund"

注意：
- 只提取基金类持仓，忽略股票和ETF
- 金额单位为人民币元，去掉"元""￥"等符号
- 百分比只保留数字不要%符号
- 持有金额大于0才返回
- 只返回JSON数组

OCR识别文本：
{ocr_text}"""


def recognize_portfolio(image_base64: str) -> list[dict]:
    """Recognize fund portfolio from screenshot using OCR + DeepSeek."""
    if not DEEPSEEK_API_KEY:
        raise ValueError("DeepSeek API key not configured")

    import easyocr
    image_bytes = base64.b64decode(image_base64)
    reader = easyocr.Reader(["ch_sim", "en"], gpu=False, verbose=False)
    results = reader.readtext(image_bytes, detail=0)
    ocr_text = "\n".join(results) if results else ""

    if not ocr_text.strip():
        raise ValueError("未能从图片中识别到文字，请确保截图清晰")

    print(f"OCR extracted {len(results)} text segments", flush=True)

    prompt = PARSE_PROMPT.format(ocr_text=ocr_text[:3000])

    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
        json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 2000},
        timeout=60,
    )
    data = resp.json()

    if "choices" not in data or not data["choices"]:
        err = data.get("error", {}).get("message", "未知错误")
        raise ValueError(f"AI调用失败：{err}")

    content = data["choices"][0]["message"]["content"]
    print(f"AI response: {content[:500]}", flush=True)

    # Parse: try many strategies
    for fence in ["```json", "```"]:
        content = content.replace(fence, "")
    content = content.strip()

    items = None

    # Strategy A: regex extract [...]
    m = re.search(r"\[.*\]", content, re.DOTALL)
    candidates = [m.group()] if m else []
    candidates.append(content)

    for cand in candidates:
        for variant in [cand, cand.replace("'", '"')]:
            try:
                parsed = json.loads(variant)
                if isinstance(parsed, list) and len(parsed) > 0:
                    items = parsed
                    break
            except:
                continue
        if items:
            break

    if not items:
        raise ValueError(f"解析失败。OCR: {ocr_text[:100]} ... AI: {content[:200]}")

    print(f"Parsed {len(items)} fund items: {items}", flush=True)
    return items
def update_current_prices(items: list[dict]) -> list[dict]:
    """Update current prices for portfolio items (stocks/ETFs only)."""
    for item in items:
        code = item.get("stock_code", "")
        if not code or item.get("asset_type") == "fund":
            continue
        market = "sh" if code.startswith("6") or code.startswith("9") else "sz"
        try:
            quote = get_realtime_quote(code, market)
            if quote:
                item["current_price"] = quote.get("price", 0)
        except Exception:
            pass
    return items


def get_portfolio_with_prices(db: Session) -> Optional[dict]:
    """Get portfolio with updated current prices."""
    portfolio = db.query(Portfolio).first()
    if not portfolio:
        return None

    items = []
    total_value = 0
    total_cost = 0

    for item in portfolio.items:
        code = item.stock_code
        market = "sh" if code.startswith("6") or code.startswith("9") else "sz"
        current_price = item.current_price

        if code and item.asset_type != "fund":
            try:
                quote = get_realtime_quote(code, market)
                if quote:
                    current_price = quote.get("price", item.current_price)
                    item.current_price = current_price
                    db.commit()
            except Exception:
                pass

        value = item.quantity * current_price
        cost = item.quantity * item.cost_price
        profit = value - cost
        profit_pct = (profit / cost * 100) if cost > 0 else 0

        items.append({
            "id": item.id,
            "stock_code": item.stock_code,
            "stock_name": item.stock_name,
            "asset_type": item.asset_type,
            "quantity": item.quantity,
            "cost_price": item.cost_price,
            "current_price": current_price,
            "value": value,
            "profit_loss": profit,
            "profit_pct": profit_pct,
            "holding_amount": item.holding_amount or 0,
            "cost_amount": item.cost_amount or 0,
            "holding_return": item.holding_return or 0,
            "daily_return": item.daily_return or 0,
            "daily_return_pct": item.daily_return_pct or 0,
            "sector": item.sector or "",
        })
        total_value += value
        total_cost += cost

    total_profit = total_value - total_cost
    total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0

    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "items": items,
        "total_value": total_value,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "total_profit_pct": total_profit_pct,
    }


def build_portfolio_context(db: Session) -> str:
    """Build portfolio context string for AI chat."""
    portfolio = get_portfolio_with_prices(db)
    if not portfolio or not portfolio["items"]:
        return ""

    lines = ["[用户当前持仓]"]
    for item in portfolio["items"]:
        name = item['stock_name'] or item['stock_code'] or "未知"
        code_str = f"({item['stock_code']})" if item['stock_code'] else ""
        profit_str = f"+{item['profit_loss']:.0f}" if item['profit_loss'] >= 0 else f"{item['profit_loss']:.0f}"
        if item['asset_type'] == 'fund':
            lines.append(
                f"{name}{code_str}: "
                f"{item['quantity']:.0f}份, 成本净值{item['cost_price']}元, "
                f"最新净值{item['current_price']}元, 盈亏{profit_str}元"
            )
        else:
            lines.append(
                f"{name}{code_str}: "
                f"{item['quantity']:.0f}股, 成本价{item['cost_price']}元, "
                f"现价{item['current_price']}元, 盈亏{profit_str}元"
            )
    lines.append(
        f"总持仓市值: {portfolio['total_value']/10000:.1f}万, "
        f"总盈亏{portfolio['total_profit']/10000:+.1f}万"
    )
    return "\n".join(lines)



def calc_portfolio_risk(db: Session) -> dict:
    """Calculate risk metrics: Sharpe ratio and max drawdown."""
    import math
    from collections import defaultdict

    portfolio = db.query(Portfolio).first()
    if not portfolio or not portfolio.items:
        return {"sharpe_ratio": None, "max_drawdown": None, "message": "无持仓数据"}

    # Get items with stock codes (can't compute for funds without codes)
    stock_items = [i for i in portfolio.items if i.stock_code and i.asset_type != "fund"]
    if not stock_items:
        return {"sharpe_ratio": None, "max_drawdown": None, "message": "无可计算的股票/ETF持仓"}

    try:
        # Fetch kline data for each holding (last 120 trading days)
        daily_values = defaultdict(float)
        for item in stock_items:
            market = "sh" if item.stock_code.startswith("6") or item.stock_code.startswith("9") else "sz"
            kline = get_kline_data(item.stock_code, market, 120, "101")
            if not kline:
                continue
            weight = item.quantity * item.current_price
            for bar in kline:
                daily_values[bar["date"]] += weight * (bar["close"] / kline[-1]["close"])

        if len(daily_values) < 30:
            return {"sharpe_ratio": None, "max_drawdown": None, "message": "历史数据不足（需30个交易日以上）"}

        # Sort by date and build daily return series
        sorted_dates = sorted(daily_values.keys())
        values = [daily_values[d] for d in sorted_dates]
        returns = []
        for i in range(1, len(values)):
            if values[i-1] > 0:
                returns.append((values[i] - values[i-1]) / values[i-1])

        if len(returns) < 20:
            return {"sharpe_ratio": None, "max_drawdown": None, "message": "收益率数据不足"}

        # Sharpe ratio (annualized)
        avg_return = sum(returns) / len(returns)
        variance = sum((r - avg_return) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else 0
        risk_free_daily = 0.025 / 252  # 2.5% annual risk-free rate
        sharpe = ((avg_return - risk_free_daily) / std_dev * math.sqrt(252)) if std_dev > 0 else 0

        # Max drawdown
        peak = values[0]
        max_dd = 0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        return {
            "sharpe_ratio": round(sharpe, 3),
            "max_drawdown": round(max_dd * 100, 2),
            "trading_days": len(returns),
            "message": None,
        }

    except Exception as e:
        logger.error(f"Risk calculation failed: {str(e)}")
        return {"sharpe_ratio": None, "max_drawdown": None, "message": f"计算失败：{str(e)[:50]}"}


def save_portfolio_items(db: Session, items: list[dict], image_path: str = "") -> Portfolio:
    """Save or update portfolio items."""
    portfolio = db.query(Portfolio).first()
    if not portfolio:
        portfolio = Portfolio(name="默认持仓", image_path=image_path)
        db.add(portfolio)
        db.flush()

    db.query(PortfolioItem).filter(PortfolioItem.portfolio_id == portfolio.id).delete()

    for item in items:
        db_item = PortfolioItem(
            portfolio_id=portfolio.id,
            stock_code=item.get("stock_code", ""),
            stock_name=item.get("stock_name", ""),
            asset_type=item.get("asset_type", "fund"),
            quantity=item.get("quantity", 0),
            cost_price=item.get("cost_price", 0),
            current_price=item.get("current_price", 0),
            holding_amount=item.get("holding_amount", 0),
            cost_amount=item.get("cost_amount", 0),
            holding_return=item.get("holding_return", 0),
            daily_return=item.get("daily_return", 0),
            daily_return_pct=item.get("daily_return_pct", 0),
            sector=item.get("sector", ""),
        )
        db.add(db_item)

    if image_path:
        portfolio.image_path = image_path

    db.commit()
    db.refresh(portfolio)
    return portfolio



def calc_portfolio_diagnosis(db) -> dict:
    """Simplified fund portfolio diagnosis: per-item signal lights and health summary."""
    from ..models.stock import Portfolio
    portfolio = db.query(Portfolio).first()
    if not portfolio or not portfolio.items:
        return {"concentration": None, "items": [], "summary": "暂无持仓数据"}

    items = []
    green = yellow = red = 0
    for item in portfolio.items:
        holding_return = item.holding_return or 0
        cost_amount = item.cost_amount or 0
        profit_pct = (holding_return / cost_amount * 100) if cost_amount > 0 else 0
        daily_pct = item.daily_return_pct or 0

        if profit_pct > 5:
            signal = "green"
            reason = f"盈利{profit_pct:.1f}%"
        elif profit_pct < -10:
            signal = "red"
            reason = f"亏损{abs(profit_pct):.1f}%"
        elif profit_pct < -5:
            signal = "yellow"
            reason = f"小幅亏损{abs(profit_pct):.1f}%"
        elif profit_pct >= 0:
            signal = "green"
            reason = "持仓正常"
        else:
            signal = "yellow"
            reason = "轻微浮动"

        if signal == "green": green += 1
        elif signal == "yellow": yellow += 1
        elif signal == "red": red += 1

        items.append({
            "stock_code": item.stock_code,
            "stock_name": item.stock_name,
            "asset_type": item.asset_type,
            "weight_pct": round((item.holding_amount or 0) / max(sum(i.holding_amount or 0 for i in portfolio.items), 1) * 100, 1),
            "profit_pct": round(profit_pct, 2),
            "change_today": daily_pct,
            "signal": signal,
            "reason": reason,
        })

    total = len(portfolio.items)
    top1 = sorted(items, key=lambda x: x["weight_pct"], reverse=True)
    top1_pct = top1[0]["weight_pct"] if top1 else 0
    top3_pct = sum(x["weight_pct"] for x in top1[:3]) if len(top1) >= 3 else (top1_pct if top1 else 0)
    warning = "持仓过于集中，建议分散风险" if top1_pct > 40 else None

    summary_parts = []
    if green > 0: summary_parts.append(f"{green}只健康")
    if yellow > 0: summary_parts.append(f"{yellow}只需关注")
    if red > 0: summary_parts.append(f"{red}只风险较高")
    summary = "，".join(summary_parts) if summary_parts else "数据不足"

    return {
        "concentration": {"top3_pct": round(top3_pct, 1), "top1_pct": round(top1_pct, 1), "top1_name": top1[0]["stock_name"] if top1 else "", "warning": warning},
        "items": items,
        "summary": summary,
    }

def delete_portfolio(db: Session) -> bool:
    """Delete portfolio and all items."""
    portfolio = db.query(Portfolio).first()
    if not portfolio:
        return False
    db.delete(portfolio)
    db.commit()
    return True
