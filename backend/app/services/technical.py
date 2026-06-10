"""Technical indicators - pure Python implementation (no talib dependency)."""
from typing import Optional


def calc_ma(data, period):
    """Simple Moving Average."""
    if len(data) < period:
        return [None] * len(data)
    result = [None] * (period - 1)
    for i in range(period - 1, len(data)):
        result.append(round(sum(data[i - period + 1: i + 1]) / period, 2))
    return result


def calc_ema(data, period):
    """Exponential Moving Average."""
    if len(data) < 2:
        return [None] * len(data)
    k = 2 / (period + 1)
    result = [None] * (period - 1)
    ema = sum(data[:period]) / period
    result.append(round(ema, 2))
    for price in data[period:]:
        ema = price * k + ema * (1 - k)
        result.append(round(ema, 2))
    return result


def calc_macd(closes, fast=12, slow=26, signal=9):
    """MACD indicator."""
    if len(closes) < slow + signal:
        return {"dif": [None]*len(closes), "dea": [None]*len(closes), "macd": [None]*len(closes)}
    ema_fast = calc_ema(closes, fast)
    ema_slow = calc_ema(closes, slow)
    dif = []
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif.append(round(ema_fast[i] - ema_slow[i], 2))
        else:
            dif.append(None)
    valid_dif = [d for d in dif if d is not None]
    dea_raw = calc_ema(valid_dif, signal)
    dea = [None] * (len(dif) - len(dea_raw)) + dea_raw
    macd = []
    for i in range(len(dif)):
        if dif[i] is not None and dea[i] is not None:
            macd.append(round((dif[i] - dea[i]) * 2, 2))
        else:
            macd.append(None)
    return {"dif": dif, "dea": dea, "macd": macd}


def calc_rsi(closes, period=14):
    """Relative Strength Index."""
    if len(closes) < period + 1:
        return [None] * len(closes)
    result = [None] * period
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        if change > 0:
            gains += change
        else:
            losses += abs(change)
    avg_gain = gains / period
    avg_loss = losses / period
    rs = avg_gain / avg_loss if avg_loss != 0 else 100
    result.append(round(100 - 100 / (1 + rs), 2))
    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain = max(change, 0)
        loss = abs(min(change, 0))
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 100
        result.append(round(100 - 100 / (1 + rs), 2))
    return result


def calc_bollinger(closes, period=20, std_dev=2.0):
    """Bollinger Bands."""
    if len(closes) < period:
        return {"upper": [None]*len(closes), "mid": [None]*len(closes), "lower": [None]*len(closes)}
    mid = calc_ma(closes, period)
    upper = [None] * (period - 1)
    lower = [None] * (period - 1)
    for i in range(period - 1, len(closes)):
        window = closes[i - period + 1: i + 1]
        mean = sum(window) / period
        variance = sum((x - mean) ** 2 for x in window) / period
        std = variance ** 0.5
        upper.append(round(mean + std_dev * std, 2))
        lower.append(round(mean - std_dev * std, 2))
    return {"upper": upper, "mid": mid, "lower": lower}


def calc_all_indicators(kline_data):
    """Calculate all technical indicators from K-line data."""
    if len(kline_data) < 5:
        return {"error": "Need at least 5 candles"}
    closes = [k["close"] for k in kline_data]
    macd = calc_macd(closes)
    rsi6 = calc_rsi(closes, 6)
    rsi14 = calc_rsi(closes, 14)
    rsi24 = calc_rsi(closes, 24)
    boll = calc_bollinger(closes)
    ma5 = calc_ma(closes, 5)
    ma10 = calc_ma(closes, 10)
    ma20 = calc_ma(closes, 20)
    ma60 = calc_ma(closes, 60) if len(closes) >= 60 else [None] * len(closes)
    return {
        "ma": {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60},
        "macd": macd,
        "rsi": {"rsi6": rsi6, "rsi14": rsi14, "rsi24": rsi24},
        "bollinger": boll,
    }
