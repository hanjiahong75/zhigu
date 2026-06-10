import os
path = r'D:\知股app - 前后端分离版本\backend\app\services\stock_data.py'

content = """\"\"\"Stock data service using akshare + direct eastmoney API.\"\"\"
import akshare as ak
import requests
from typing import Optional

# Session with proxy disabled
_session = requests.Session()
_session.trust_env = False

STOCK_API = "https://push2.eastmoney.com/api/qt/stock/get"
KLIST_API = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
INDEX_API = "https://push2.eastmoney.com/api/qt/stock/get"


def _make_request(url: str, params: dict, timeout: int = 15) -> dict:
    """Make a request with no proxy."""
    r = _session.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _get_secid(code: str) -> str:
    """Convert stock code to eastmoney secid format."""
    if code.startswith(("6", "9")):
        return f"1.{code}"  # Shanghai
    else:
        return f"0.{code}"  # Shenzhen / Beijing


def search_stocks(keyword: str) -> list[dict]:
    """Search stocks by keyword (name or code)."""
    try:
        df = ak.stock_info_a_code_name()
        mask = df["name"].str.contains(keyword, na=False) | df["code"].str.contains(keyword, na=False)
        results = df[mask].head(20)
        return [{"code": r["code"], "name": r["name"]} for _, r in results.iterrows()]
    except Exception:
        return []


def get_realtime_quote(code: str, market: str = "sz") -> Optional[dict]:
    """Get realtime quote for a single stock using eastmoney individual API."""
    try:
        secid = _get_secid(code)
        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f116,f117,f169,f170,f171,f172"
        }
        data = _make_request(STOCK_API, params)
        d = data.get("data", {})
        if not d:
            return None

        scale = 100 if code.startswith(("6", "0", "3")) else 1
        return {
            "code": code,
            "name": str(d.get("f58", "")),
            "price": round(float(d.get("f43", 0)) / scale, 2),
            "change_pct": round(float(d.get("f170", 0)) / 100, 2),
            "change_amount": round(float(d.get("f169", 0)) / 100, 2),
            "volume": int(d.get("f47", 0) or 0),
            "amount": round(float(d.get("f48", 0) or 0), 2),
            "high": round(float(d.get("f44", 0)) / scale, 2),
            "low": round(float(d.get("f45", 0)) / scale, 2),
            "open": round(float(d.get("f46", 0)) / scale, 2),
            "pre_close": round(float(d.get("f60", 0)) / scale, 2),
            "turnover": round(float(d.get("f50", 0)) / 100, 2),
            "total_cap": round(float(d.get("f116", 0) or 0), 2),
            "float_cap": round(float(d.get("f117", 0) or 0), 2),
        }
    except Exception:
        return None


def get_kline_data(code: str, market: str = "sz", days: int = 120) -> list[dict]:
    """Get historical K-line data using eastmoney K-line API."""
    try:
        secid = _get_secid(code)
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",  # daily
            "fqt": "1",    # 前复权
            "end": "20500101",
            "lmt": str(days),
        }
        data = _make_request(KLIST_API, params)
        klines = data.get("data", {}).get("klines", [])
        if not klines:
            return []

        result = []
        for line in klines:
            parts = line.split(",")
            result.append({
                "date": parts[0],
                "open": float(parts[1]),
                "close": float(parts[2]),
                "high": float(parts[3]),
                "low": float(parts[4]),
                "volume": int(parts[5]),
                "amount": float(parts[6]),
            })
        return result
    except Exception:
        # Fallback to akshare
        try:
            df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
            if df is None or df.empty:
                return []
            df = df.tail(days)
            result = []
            for _, r in df.iterrows():
                result.append({
                    "date": str(r.iloc[0])[:10],
                    "open": float(r.iloc[1]),
                    "close": float(r.iloc[2]),
                    "high": float(r.iloc[3]),
                    "low": float(r.iloc[4]),
                    "volume": int(r.iloc[5]),
                    "amount": float(r.iloc[6]),
                })
            return result
        except Exception:
            return []


def get_market_indices() -> list[dict]:
    """Get major market indices."""
    index_map = {
        "1.000001": "上证指数",
        "0.399001": "深证成指",
        "0.399006": "创业板指",
        "1.000688": "科创50",
        "1.000300": "沪深300",
    }
    results = []
    for secid, name in index_map.items():
        try:
            params = {
                "secid": secid,
                "fields": "f43,f44,f45,f46,f57,f58,f169,f170"
            }
            data = _make_request(INDEX_API, params)
            d = data.get("data", {})
            if d:
                results.append({
                    "name": name,
                    "code": secid.split(".")[1],
                    "price": round(float(d.get("f43", 0)) / 100, 2),
                    "change_pct": round(float(d.get("f170", 0)) / 100, 2),
                })
        except Exception:
            continue
    return results
"""

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')
