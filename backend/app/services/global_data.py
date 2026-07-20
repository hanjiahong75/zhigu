"""Global market data service: multi-market quote/kline/indicators.

Data routing:
- HK/US: akshare (spot + hist + search + financial)
- JP/KR/EU: tradingview-ta (quote + 60+ indicators)
- All markets: tradingview-ta (technical indicators, buy/sell signals)
"""

import json
import logging
from tradingview_ta import TA_Handler, Interval

from .global_symbols import search_popular, get_stock_name

logger = logging.getLogger(__name__)

# Market → (TradingView exchange, screener)
TV_EXCHANGE_MAP = {
    "hk": ("HKEX", "hongkong"),
    "us": ("NASDAQ", "america"),
    "jp": ("TSE", "japan"),
    "kr": ("KRX", "korea"),
    "uk": ("LSE", "uk"),
    "de": ("XETR", "germany"),
}

# us sub-market routing by code prefix (for akshare)
US_MARKET_ROUTE = {
    "NASDAQ": ["A", "G", "M", "N", "S", "T"],
}

INTERVAL_MAP = {
    "1D": Interval.INTERVAL_1_DAY,
    "1W": Interval.INTERVAL_1_WEEK,
    "1M": Interval.INTERVAL_1_MONTH,
    "1H": Interval.INTERVAL_1_HOUR,
    "4H": Interval.INTERVAL_4_HOURS,
}


def _get_tv_analysis(code: str, market: str, interval: str = "1D") -> dict | None:
    """Fetch TradingView technical analysis for a symbol."""
    exchange_info = TV_EXCHANGE_MAP.get(market)
    if not exchange_info:
        return None
    exchange, screener = exchange_info
    try:
        handler = TA_Handler(
            symbol=code,
            exchange=exchange,
            screener=screener,
            interval=INTERVAL_MAP.get(interval, Interval.INTERVAL_1_DAY),
        )
        analysis = handler.get_analysis()
        return {
            "indicators": analysis.indicators,
            "summary": analysis.summary,
        }
    except Exception as e:
        logger.warning(f"TV analysis failed for {market}:{code} -> {e}")
        return None


def get_global_quote(code: str, market: str) -> dict | None:
    """Get real-time quote for any market.

    HK/US: prefer akshare for richer data (turnover, amount, PE)
    JP/KR/EU: tradingview-ta only
    """
    # Handle global index codes (100.XXX format)
    if "." in code or code.startswith("100."):
        try:
            from ..services.stock_data import get_global_indices as _gi
            cached = _gi()
            for group in cached:
                for idx in group.get("indices", []):
                    if idx["code"] == code:
                        p = idx["price"]
                        cp = idx["change_pct"]
                        return {
                            "code": code, "market": idx.get("market", market),
                            "name": idx["name"], "price": p,
                            "change_pct": cp, "change_amount": round(p * cp / 100, 2) if cp else 0,
                            "open": p, "high": p, "low": p, "pre_close": p,
                            "volume": 0, "amount": 0, "turnover": 0, "source": "cache",
                        }
        except Exception:
            pass

    # Try akshare first for HK/US (richer data)
    if market in ("hk", "us"):
        try:
            quote = _akshare_quote(code, market)
            if quote:
                return quote
        except Exception:
            pass

    # Fallback: tradingview-ta
    tv = _get_tv_analysis(code, market)
    if not tv:
        return None

    ind = tv["indicators"]
    price = ind.get("close") or 0
    change_pct = ind.get("change") or 0
    change_amount = round(price * change_pct / 100, 2) if price and change_pct else 0
    pre_close = round(price - change_amount, 2) if price else 0
    return {
        "code": code,
        "market": market,
        "name": get_stock_name(code, market),
        "price": price,
        "change_pct": change_pct,
        "change_amount": change_amount,
        "open": ind.get("open") or price,
        "high": ind.get("high") or price,
        "low": ind.get("low") or price,
        "pre_close": pre_close,
        "volume": ind.get("volume") or 0,
        "amount": 0,
        "turnover": 0,
        "source": "tradingview",
    }


def _akshare_quote(code: str, market: str) -> dict | None:
    """Get quote from akshare for HK/US."""
    import akshare as ak

    if market == "hk":
        try:
            df = ak.stock_hk_spot_em()
            row = df[df["代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                return {
                    "code": code, "market": market,
                    "name": r.get("名称", code),
                    "price": float(r.get("最新价", 0) or 0),
                    "change_pct": float(r.get("涨跌幅", 0) or 0),
                    "open": float(r.get("今开", 0) or 0),
                    "high": float(r.get("最高", 0) or 0),
                    "low": float(r.get("最低", 0) or 0),
                    "volume": float(r.get("成交量", 0) or 0),
                    "amount": float(r.get("成交额", 0) or 0),
                    "turnover": float(r.get("换手率", 0) or 0),
                    "pe": float(r.get("市盈率", 0) or 0) if "市盈率" in df.columns else None,
                    "source": "akshare",
                }
        except Exception as e:
            logger.warning(f"akshare HK quote failed for {code}: {e}")

    elif market == "us":
        try:
            df = ak.stock_us_spot_em()
            row = df[df["代码"] == code]
            if not row.empty:
                r = row.iloc[0]
                return {
                    "code": code, "market": market,
                    "name": r.get("名称", code),
                    "price": float(r.get("最新价", 0) or 0),
                    "change_pct": float(r.get("涨跌幅", 0) or 0),
                    "open": float(r.get("今开", 0) or 0),
                    "high": float(r.get("最高", 0) or 0),
                    "low": float(r.get("最低", 0) or 0),
                    "volume": float(r.get("成交量", 0) or 0),
                    "amount": float(r.get("成交额", 0) or 0),
                    "pe": float(r.get("市盈率", 0) or 0) if "市盈率" in df.columns else None,
                    "source": "akshare",
                }
        except Exception as e:
            logger.warning(f"akshare US quote failed for {code}: {e}")

    return None


def search_global_stocks(keyword: str, market: str = "hk") -> list[dict]:
    """Search stocks by keyword — static popular list first, then akshare fallback."""
    results = []

    # Always try static popular list first (fast)
    popular = search_popular(keyword, market)
    for s in popular:
        results.append({"code": s["code"], "name": s["name"], "market": market})

    # If static list found results, return immediately
    if results:
        return results[:10]

    # Fallback to akshare for HK/US
    if market == "hk":
        try:
            import akshare as ak
            df = ak.stock_hk_spot_em()
            if keyword.isdigit():
                mask = df["代码"].str.contains(keyword, na=False)
            else:
                mask = df["名称"].str.contains(keyword, na=False)
            matched = df[mask].head(10)
            for _, r in matched.iterrows():
                results.append({
                    "code": r["代码"], "name": r["名称"], "market": "hk",
                })
        except Exception:
            pass
    elif market == "us":
        try:
            import akshare as ak
            name_df = ak.get_us_stock_name()
            if keyword.isalpha():
                mask_upper = name_df["name"].str.contains(keyword.upper(), na=False)
                name_matched = name_df[mask_upper].head(10)
                for _, r in name_matched.iterrows():
                    code = str(r.get("cname", "")).strip()
                    if code:
                        results.append({"code": code, "name": r["name"], "market": "us"})
        except Exception:
            pass

    return results[:10]


def get_global_kline(code: str, market: str, days: int = 120, klt: str = "101") -> list[dict]:
    """Get historical K-line data using akshare (HK/US) or yfinance (JP/KR)."""
    import akshare as ak

    try:
        if market == "hk":
            period = "daily"
            df = ak.stock_hk_hist(symbol=code, period=period, adjust="qfq")
        elif market == "us":
            period = "daily"
            df = ak.stock_us_hist(symbol=code, period=period, adjust="qfq")
        elif market in ("kr", "jp"):
            # Use EastMoney API for global indices, Yahoo for stocks
            from curl_cffi import requests
            em_code = code  # e.g. "100.KS11", "100.N225"
            import time as _time
            # Simple in-memory cache to reduce API calls (keyed by code+days)
            _kline_cache = getattr(get_global_kline, "_cache", {})
            cache_key = f"{em_code}:{days}"
            cache_entry = _kline_cache.get(cache_key)
            if cache_entry and (_time.time() - cache_entry[0]) < 300:
                return cache_entry[1]
            for attempt in range(2):
                try:
                    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
                    params = {
                        "secid": em_code,
                        "fields1": "f1,f2,f3,f4,f5,f6",
                        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
                        "klt": klt if klt.isdigit() else "101",
                        "fqt": "1",
                        "end": "20500101",
                        "lmt": str(days + 100),
                        "ut": "f057cbcbce2a86e2866ab8877db1d059",
                        "forcect": "1",
                    }
                    r = requests.get(url, params=params,
                                    headers={"Referer": "https://quote.eastmoney.com"}, timeout=10)
                    data = r.json().get("data", {})
                    klines_raw = data.get("klines", [])
                    if not klines_raw:
                        return []
                    kline = []
                    for line in klines_raw[-days:]:
                        parts = line.split(",")
                        if len(parts) >= 6:
                            kline.append({
                                "date": parts[0],
                                "open": round(float(parts[1]), 2),
                                "close": round(float(parts[2]), 2),
                                "high": round(float(parts[3]), 2),
                                "low": round(float(parts[4]), 2),
                                "volume": int(float(parts[5])),
                            })
                    return kline
                    # Cache on success
                    _kline_cache[cache_key] = (_time.time(), kline)
                    get_global_kline._cache = _kline_cache
                    return kline
                except Exception as e:
                    if attempt < 1:
                        _time.sleep(1)
            # Try without impersonation as fallback
            try:
                r = requests.get(url, params=params,
                                headers={"Referer": "https://quote.eastmoney.com"}, timeout=10,
                                impersonate="chrome110")
                data = r.json().get("data", {})
                klines_raw = data.get("klines", [])
                if klines_raw:
                    kline = []
                    for line in klines_raw[-days:]:
                        parts = line.split(",")
                        if len(parts) >= 6:
                            kline.append({
                                "date": parts[0], "open": round(float(parts[1]), 2),
                                "close": round(float(parts[2]), 2), "high": round(float(parts[3]), 2),
                                "low": round(float(parts[4]), 2), "volume": int(float(parts[5])),
                            })
                    _kline_cache[cache_key] = (_time.time(), kline)
                    get_global_kline._cache = _kline_cache
                    return kline
            except Exception:
                pass
            logger.warning(f"EastMoney kline failed for {market}:{code}: {e}")
            return []
        else:
            return []

        if df is None or df.empty:
            return []

        kline = []
        for _, row in df.tail(days).iterrows():
            kline.append({
                "date": str(row.get("日期", ""))[:10],
                "open": float(row.get("开盘", 0) or 0),
                "high": float(row.get("最高", 0) or 0),
                "low": float(row.get("最低", 0) or 0),
                "close": float(row.get("收盘", 0) or 0),
                "volume": float(row.get("成交量", 0) or 0),
            })
        return kline

    except Exception as e:
        logger.warning(f"get_global_kline failed for {market}:{code}: {e}")
        return []


def get_global_indicators(code: str, market: str) -> dict:
    """Get comprehensive technical indicators + buy/sell signals via TradingView."""
    tv = _get_tv_analysis(code, market)
    if not tv:
        return {"error": f"无法获取{market}:{code}的技术指标"}

    ind = tv["indicators"]
    summary = tv["summary"]

    return {
        "code": code,
        "market": market,
        "price": ind.get("close"),
        "rsi": round(ind.get("RSI", 0), 1),
        "rsi_signal": "超买" if ind.get("RSI", 50) > 70 else ("超卖" if ind.get("RSI", 50) < 30 else "中性"),
        "macd": {
            "macd": round(ind.get("MACD.macd", 0), 3),
            "signal": round(ind.get("MACD.signal", 0), 3),
            "histogram": round(ind.get("MACD.macd", 0) - ind.get("MACD.signal", 0), 3),
        },
        "ma": {
            "ma5": ind.get("SMA5"),
            "ma10": ind.get("SMA10"),
            "ma20": ind.get("SMA20"),
            "ma50": ind.get("SMA50"),
        },
        "boll": {
            "upper": ind.get("BB.upper"),
            "mid": ind.get("SMA20"),
            "lower": ind.get("BB.lower"),
        },
        "stoch_kd": {
            "k": round(ind.get("Stoch.K", 0), 1),
            "d": round(ind.get("Stoch.D", 0), 1),
        },
        "adx": round(ind.get("ADX", 0), 1),
        "cci": round(ind.get("CCI20", 0), 1),
        "recommendation": summary.get("RECOMMENDATION", "NEUTRAL"),
        "buy_count": summary.get("BUY", 0),
        "sell_count": summary.get("SELL", 0),
        "neutral_count": summary.get("NEUTRAL", 0),
        "source": "tradingview",
    }


def get_global_indices() -> list[dict]:
    """Get major global market indices."""
    try:
        import akshare as ak
        df = ak.index_global_spot_em()
        if df is None or df.empty:
            return []
        # Key indices
        key_codes = ["HSI", "DJIA", "IXIC", "SPX", "N225"]
        indices = []
        for _, row in df.iterrows():
            code = str(row.get("代码", ""))
            if code in key_codes:
                indices.append({
                    "code": code,
                    "name": str(row.get("名称", "")),
                    "price": float(row.get("最新价", 0) or 0),
                    "change_pct": float(row.get("涨跌幅", 0) or 0),
                })
        return indices
    except Exception as e:
        logger.warning(f"Global indices failed: {e}")
        return []
