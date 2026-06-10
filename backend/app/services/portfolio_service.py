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

PARSE_PROMPT = """请从以下OCR识别出的持仓截图文本中，提取所有持仓信息（包括股票、场内基金ETF、场外基金等）。
返回JSON数组格式：
[{"stock_code":"代码","stock_name":"名称","quantity":数量,"cost_price":成本价,"current_price":当前价,"asset_type":"类型"}]

注意：
- stock_code：填股票或基金代码，场外基金如果没有代码则填空字符串""
- stock_name：股票或基金名称，必填
- quantity：持有份额/股数，如没有则填0
- cost_price：成本价/净值，如没有则填0
- current_price：当前价/最新净值，如没有则填0
- asset_type：股票填"stock"，场内基金/ETF填"etf"，场外基金填"fund"
- 场外基金常见字段：持有金额、持仓收益、最新净值等，请尽量映射到上述字段
- 忽略表格标题行和非持仓相关内容
- 只返回JSON数组，不要其他文字

OCR识别文本：
{ocr_text}"""


def recognize_portfolio(image_base64: str) -> list[dict]:
    """Recognize portfolio from screenshot using OCR + DeepSeek."""
    if not DEEPSEEK_API_KEY:
        raise ValueError("DeepSeek API key not configured")

    try:
        import easyocr

        image_bytes = base64.b64decode(image_base64)
        reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
        results = reader.readtext(image_bytes, detail=0)
        ocr_text = '\n'.join(results) if results else ''

        if not ocr_text.strip():
            raise ValueError("未能从图片中识别到文字，请确保截图清晰，或使用手动输入")

        logger.info(f"OCR extracted {len(results)} text segments")

        prompt = PARSE_PROMPT.format(ocr_text=ocr_text[:3000])

        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 1000,
            },
            timeout=30,
        )
        data = resp.json()

        if "choices" in data and data["choices"]:
            content = data["choices"][0]["message"]["content"]
            content = content.strip()
            if "```" in content:
                content = re.sub(r'```\w*\n?', '', content).replace('```', '')
            match = re.search(r'\[.*\]', content, re.DOTALL)
            if match:
                try:
                    items = json.loads(match.group())
                    if isinstance(items, list) and len(items) > 0:
                        return items
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"未能解析持仓信息，请尝试手动输入。OCR文本：{ocr_text[:200]}")
        else:
            raise ValueError(f"AI识别失败：{data.get('error', {}).get('message', '未知错误')}")

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Recognition failed: {str(e)}")
        raise ValueError(f"识别失败：{str(e)}")


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
        # Accept items with or without stock_code (funds may not have one)
        db_item = PortfolioItem(
            portfolio_id=portfolio.id,
            stock_code=item.get("stock_code", ""),
            stock_name=item.get("stock_name", ""),
            asset_type=item.get("asset_type", "stock"),
            quantity=item.get("quantity", 0),
            cost_price=item.get("cost_price", 0),
            current_price=item.get("current_price", 0),
        )
        db.add(db_item)

    if image_path:
        portfolio.image_path = image_path

    db.commit()
    db.refresh(portfolio)
    return portfolio


def delete_portfolio(db: Session) -> bool:
    """Delete portfolio and all items."""
    portfolio = db.query(Portfolio).first()
    if not portfolio:
        return False
    db.delete(portfolio)
    db.commit()
    return True