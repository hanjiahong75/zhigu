"""Stock data service using akshare + direct eastmoney API."""
import akshare as ak
from curl_cffi import requests
from typing import Optional

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
    try:
        secid = f"1.{code}" if code.startswith(("6","9")) else f"0.{code}"
        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f169,f170"
        }
        STOCK_API = "https://push2.eastmoney.com/api/qt/stock/get"
        r = requests.get(STOCK_API, params=params, timeout=15)
        r.raise_for_status()
        d = r.json().get("data", {})
        if not d:
            return None
        scale = 100 if code.startswith(("6","0","3")) else 1
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
        }
    except Exception:
        return None

def get_kline_data(code: str, market: str = "sz", days: int = 120, klt: str = "101") -> list[dict]:
    try:
        secid = f"1.{code}" if code.startswith(("6","9")) else f"0.{code}"
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": klt,
            "fqt": "1",
            "end": "20500101",
            "lmt": "10000",
        }
        KLIST_API = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
        r = requests.get(KLIST_API, params=params, timeout=15)
        r.raise_for_status()
        klines = r.json().get("data", {}).get("klines", [])
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
        try:
            period_map = {"1":"1","5":"5","15":"15","30":"30","60":"60","120":"120","101":"daily","102":"weekly","103":"monthly"}
            period = period_map.get(klt, "daily")
            df = ak.stock_zh_a_hist(symbol=code, period=period, adjust="qfq")
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



def get_intraday(code: str, date: str = "") -> list[dict]:
    """Get intraday 5-min bars for a specific date. Falls back to synthetic data from daily K-line."""
    try:
        secid = f"1.{code}" if code.startswith(("6","9")) else f"0.{code}"
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "5",
            "fqt": "1",
            "end": "20500101",
            "lmt": "5000",
        }
        r = requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get", params=params, timeout=15)
        r.raise_for_status()
        klines = r.json().get("data", {}).get("klines", [])
        target = date if date else (klines[-1].split(",")[0][:10] if klines else "")

        # Try real 5-min data first
        real_bars = []
        for line in klines:
            parts = line.split(",")
            if parts[0][:10] == target:
                real_bars.append({
                    "time": parts[0],
                    "price": float(parts[2]),
                    "volume": int(parts[5]),
                    "avg_price": float(parts[6]) / max(int(parts[5]), 1),
                })
        if real_bars:
            return real_bars

        # Fallback: synthetic data from daily K-line
        try:
            daily = get_kline_data(code, "sz", 10000)
            for d in daily:
                if d["date"] == target:
                    # Interpolate O->H->L->C into 48 points (matching 5-min)
                    synthetic = []
                    times = [
                        ("09:35", d["open"]),
                        ("10:00", d["open"] + (d["high"] - d["open"]) * 0.6),
                        ("10:30", d["high"]),
                        ("11:00", d["high"] - (d["high"] - d["open"]) * 0.3),
                        ("11:30", d["open"] + (d["close"] - d["open"]) * 0.4),
                        ("13:05", d["open"] + (d["close"] - d["open"]) * 0.3),
                        ("14:00", d["low"]),
                        ("14:30", d["low"] + (d["close"] - d["low"]) * 0.4),
                        ("15:00", d["close"]),
                    ]
                    for t, p in times:
                        synthetic.append({
                            "time": f"{target} {t}",
                            "price": round(p, 2),
                            "volume": d["volume"] // len(times),
                            "avg_price": round(p, 2),
                        })
                    return synthetic
        except Exception:
            pass
        return []
    except Exception:
        return []

def get_market_indices() -> list[dict]:
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
                "fields": "f43,f57,f58,f169,f170"
            }
            STOCK_API = "https://push2.eastmoney.com/api/qt/stock/get"
            r = requests.get(STOCK_API, params=params, timeout=15)
            r.raise_for_status()
            d = r.json().get("data", {})
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