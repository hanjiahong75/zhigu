"""Strategy signal service (M3).

Computes a composite buy/sell signal from technical indicators. Pure Python,
reuses technical.py. Each component score is in [-1, +1]; the composite is a
weighted average normalized over available components, with a confidence that
scales coverage by agreement (borrowed from the composite-signal idea; this is
an independent implementation).
"""

import time
from typing import Dict, List, Optional

from .technical import calc_ma, calc_macd, calc_rsi, calc_bollinger
from .stock_data import get_kline_data, get_realtime_quote
from .cache_utils import memo_ttl

DEFAULT_WEIGHTS: Dict[str, float] = {
    "ma": 0.3,
    "macd": 0.2,
    "rsi": 0.2,
    "boll": 0.2,
    "volume": 0.1,
}

RATING_STRONG_BUY = "强烈买入"
RATING_BUY = "买入"
RATING_NEUTRAL = "观望"
RATING_SELL = "卖出"
RATING_STRONG_SELL = "强烈卖出"


def _unavailable(name: str, weight: float) -> dict:
    return {"name": name, "score": 0.0, "weight": weight, "detail": "数据不足", "available": False}


def ma_signal(closes: List[float]) -> dict:
    """MA5/MA20 golden/death cross and alignment."""
    weight = DEFAULT_WEIGHTS["ma"]
    if len(closes) < 21:
        return _unavailable("均线", weight)
    ma5 = calc_ma(closes, 5)
    ma20 = calc_ma(closes, 20)
    cur5, cur20 = ma5[-1], ma20[-1]
    prev5, prev20 = ma5[-2], ma20[-2]
    if cur5 is None or cur20 is None or prev5 is None or prev20 is None:
        return _unavailable("均线", weight)
    if cur5 > cur20 and prev5 <= prev20:
        return {"name": "均线", "score": 1.0, "weight": weight,
                "detail": f"MA5({cur5})上穿MA20({cur20})，金叉", "available": True}
    if cur5 < cur20 and prev5 >= prev20:
        return {"name": "均线", "score": -1.0, "weight": weight,
                "detail": f"MA5({cur5})下穿MA20({cur20})，死叉", "available": True}
    if cur5 > cur20:
        return {"name": "均线", "score": 0.5, "weight": weight,
                "detail": f"MA5({cur5})位于MA20({cur20})上方，多头排列", "available": True}
    if cur5 < cur20:
        return {"name": "均线", "score": -0.5, "weight": weight,
                "detail": f"MA5({cur5})位于MA20({cur20})下方，空头排列", "available": True}
    return {"name": "均线", "score": 0.0, "weight": weight, "detail": "均线粘合", "available": True}


def macd_signal(closes: List[float]) -> dict:
    """MACD DIF/DEA cross plus histogram turn."""
    weight = DEFAULT_WEIGHTS["macd"]
    if len(closes) < 35:
        return _unavailable("MACD", weight)
    macd = calc_macd(closes)
    dif, dea, hist = macd["dif"], macd["dea"], macd["macd"]
    if dif[-1] is None or dea[-1] is None or dif[-2] is None or dea[-2] is None:
        return _unavailable("MACD", weight)
    score = 0.0
    parts = []
    if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
        score = 1.0
        parts.append("DIF上穿DEA金叉")
    elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
        score = -1.0
        parts.append("DIF下穿DEA死叉")
    elif dif[-1] > dea[-1]:
        score = 0.4
        parts.append("DIF位于DEA上方")
    else:
        score = -0.4
        parts.append("DIF位于DEA下方")
    if hist[-1] is not None and hist[-2] is not None:
        if hist[-2] <= 0 < hist[-1]:
            score += 0.3
            parts.append("柱状体由负转正")
        elif hist[-2] >= 0 > hist[-1]:
            score -= 0.3
            parts.append("柱状体由正转负")
    score = max(-1.0, min(1.0, score))
    return {"name": "MACD", "score": round(score, 2), "weight": weight,
            "detail": "，".join(parts), "available": True}


def rsi_signal(closes: List[float], period: int = 14) -> dict:
    """RSI overbought / oversold."""
    weight = DEFAULT_WEIGHTS["rsi"]
    if len(closes) < period + 1:
        return _unavailable("RSI", weight)
    values = calc_rsi(closes, period)
    val = values[-1]
    if val is None:
        return _unavailable("RSI", weight)
    if val >= 70:
        return {"name": "RSI", "score": -0.8, "weight": weight,
                "detail": f"RSI{period}={val}，超买", "available": True}
    if val <= 30:
        return {"name": "RSI", "score": 0.8, "weight": weight,
                "detail": f"RSI{period}={val}，超卖", "available": True}
    if 45 <= val <= 55:
        return {"name": "RSI", "score": 0.0, "weight": weight,
                "detail": f"RSI{period}={val}，中性", "available": True}
    if val < 45:
        return {"name": "RSI", "score": 0.3, "weight": weight,
                "detail": f"RSI{period}={val}，偏多", "available": True}
    return {"name": "RSI", "score": -0.3, "weight": weight,
            "detail": f"RSI{period}={val}，偏空", "available": True}


def boll_signal(closes: List[float]) -> dict:
    """Bollinger band breakout / position."""
    weight = DEFAULT_WEIGHTS["boll"]
    if len(closes) < 20:
        return _unavailable("布林带", weight)
    boll = calc_bollinger(closes)
    upper, lower, mid = boll["upper"][-1], boll["lower"][-1], boll["mid"][-1]
    if upper is None or lower is None or mid is None:
        return _unavailable("布林带", weight)
    close = closes[-1]
    if close > upper:
        return {"name": "布林带", "score": 1.0, "weight": weight,
                "detail": f"收盘价{close}上穿上轨{upper}，强势突破", "available": True}
    if close < lower:
        return {"name": "布林带", "score": -1.0, "weight": weight,
                "detail": f"收盘价{close}下穿下轨{lower}", "available": True}
    if close > mid:
        return {"name": "布林带", "score": 0.3, "weight": weight,
                "detail": f"收盘价{close}位于中轨{mid}上方", "available": True}
    if close < mid:
        return {"name": "布林带", "score": -0.3, "weight": weight,
                "detail": f"收盘价{close}位于中轨{mid}下方", "available": True}
    return {"name": "布林带", "score": 0.0, "weight": weight, "detail": "收盘价贴近中轨", "available": True}


def volume_signal(closes: List[float], volumes: List[float]) -> dict:
    """Volume ratio vs 5-day average, combined with price direction."""
    weight = DEFAULT_WEIGHTS["volume"]
    if len(volumes) < 6 or len(closes) < 2:
        return _unavailable("量比", weight)
    avg5 = sum(volumes[-6:-1]) / 5
    if avg5 <= 0:
        return _unavailable("量比", weight)
    ratio = volumes[-1] / avg5
    change = closes[-1] - closes[-2]
    if ratio >= 1.5 and change > 0:
        return {"name": "量比", "score": 0.5, "weight": weight,
                "detail": f"量比{ratio:.2f}，放量上涨，量价配合", "available": True}
    if ratio >= 1.5 and change < 0:
        return {"name": "量比", "score": -0.5, "weight": weight,
                "detail": f"量比{ratio:.2f}，放量下跌", "available": True}
    return {"name": "量比", "score": 0.0, "weight": weight,
            "detail": f"量比{ratio:.2f}，量能平淡", "available": True}


def compose_signal(components: List[dict], weights: Optional[Dict[str, float]] = None) -> dict:
    """Aggregate component signals into a composite rating.

    Weighted score uses only available components (weights renormalized).
    Confidence = coverage * (1 - score disagreement), where disagreement is the
    population std of available component scores (0..1).
    """
    weights = weights or DEFAULT_WEIGHTS
    available = [c for c in components if c.get("available")]
    if not available:
        return {
            "rating": RATING_NEUTRAL, "score": 0.0, "confidence": 0.0,
            "coverage": 0.0, "summary": "数据不足，无法计算信号",
            "components": [],
        }
    total = sum(c["score"] * c["weight"] for c in available)
    norm = sum(c["weight"] for c in available)
    score = round(total / norm if norm > 0 else 0.0, 2)
    coverage = round(len(available) / len(weights), 2)
    mean = sum(c["score"] for c in available) / len(available)
    variance = sum((c["score"] - mean) ** 2 for c in available) / len(available)
    disagreement = min(1.0, variance ** 0.5)
    confidence = round(coverage * (1 - disagreement), 2)
    rating = _rating(score)
    strongest = max(available, key=lambda c: abs(c["score"]))
    summary = f"综合信号：{rating}（得分 {score:.2f}，置信度 {confidence:.2f}）；主要依据：{strongest['detail']}"
    return {
        "rating": rating, "score": score, "confidence": confidence,
        "coverage": coverage, "summary": summary,
        "components": [
            {"name": c["name"], "score": c["score"], "weight": c["weight"], "detail": c["detail"]}
            for c in available
        ],
    }


def _rating(score: float) -> str:
    if score >= 0.5:
        return RATING_STRONG_BUY
    if score >= 0.2:
        return RATING_BUY
    if score <= -0.5:
        return RATING_STRONG_SELL
    if score <= -0.2:
        return RATING_SELL
    return RATING_NEUTRAL


@memo_ttl(30)
def compute_signal(code: str, market: str = "sz", kline: Optional[list] = None,
                   name: Optional[str] = None, days: int = 120) -> dict:
    """Compute the composite signal for a stock.

    `kline` may be injected for tests; otherwise it is fetched via
    stock_data.get_kline_data (default 120 daily bars).
    """
    if kline is None:
        kline = get_kline_data(code, market, days, "101")
    if not kline:
        return {"code": code, "market": market, "error": f"未获取到{code}的K线数据"}
    closes = [float(k["close"]) for k in kline]
    volumes = [float(k.get("volume", 0) or 0) for k in kline]
    components = [
        ma_signal(closes),
        macd_signal(closes),
        rsi_signal(closes),
        boll_signal(closes),
        volume_signal(closes, volumes),
    ]
    result = compose_signal(components)
    if name is None:
        try:
            quote = get_realtime_quote(code, market)
            name = quote.get("name", "") if quote else ""
        except Exception:
            name = ""
    result.update({
        "code": code,
        "name": name or code,
        "market": market,
        "ts": int(time.time()),
    })
    return result
