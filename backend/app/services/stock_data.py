"""Stock data service using akshare + direct eastmoney API."""
import akshare as ak
from curl_cffi import requests
import pandas as pd
from typing import Optional
from ..config import QUOTE_POLL_CHUNK_SIZE
from .cache_utils import memo_ttl


def _safe_float(v, default: float = 0.0) -> float:
    """Parse EastMoney numeric fields that may be '-' or empty."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return default

def search_stocks(keyword: str) -> list[dict]:
    """Search stocks by keyword (name or code)."""
    try:
        df = ak.stock_info_a_code_name()
        mask = df["name"].str.contains(keyword, na=False) | df["code"].str.contains(keyword, na=False)
        results = df[mask].head(20)
        return [{"code": r["code"], "name": r["name"]} for _, r in results.iterrows()]
    except Exception:
        return []

@memo_ttl(5)
def get_realtime_quote(code: str, market: str = "sz") -> Optional[dict]:
    # Known A-share index codes -> EastMoney secids
    index_secids = {
        "000001": "1.000001", "399001": "0.399001", "399006": "0.399006",
        "000688": "1.000688", "000300": "1.000300",
    }

    # Global index (codes with dot like "100.HSI") -> Sina codes
    if "." in code:
        sina_map = {
            "100.HSI": "rt_hkHSI", "100.HSCEI": "rt_hkHSCEI",
            "100.DJIA": "int_dji", "100.NDX": "int_nasdaq", "100.SPX": "int_sp500",
            "100.N225": "int_nikkei", "100.FTSE": "int_ftse", "100.GDAXI": "int_dax30",
        }
        sc = sina_map.get(code)
        if sc:
            try:
                url = f"https://hq.sinajs.cn/list={sc}"
                r = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=10)
                t = r.text
                if '=""' not in t:
                    parts = t.split('"')
                    if len(parts) >= 2:
                        fld = parts[1].split(",")
                        if len(fld) >= 4:
                            if sc.startswith("rt_"):
                                if len(fld) >= 9:
                                    nm, pr = fld[1], float(fld[2])
                                    cp = float(fld[8]); ca = float(fld[7])
                                else:
                                    raise ValueError("bad hk format")
                            else:
                                nm, pr = fld[0], float(fld[1])
                                ca = float(fld[2]); cp = float(fld[3])
                            return {"code": code, "name": nm, "price": round(pr,2),
                                    "change_pct": round(cp,2), "change_amount": round(ca,2),
                                    "volume": 0, "amount": 0, "high": pr+abs(ca), "low": pr-abs(ca),
                                    "open": pr-ca, "pre_close": pr-ca, "turnover": 0}
            except Exception:
                pass
        return None

    # A-share index: try EastMoney, fallback Sina
    if code in index_secids:
        # Try EastMoney
        try:
            secid = index_secids[code]
            params = {"secid": secid, "fields": "f43,f57,f58,f169,f170"}
            r = requests.get("https://push2.eastmoney.com/api/qt/stock/get", params=params, timeout=10)
            d = r.json().get("data", {})
            if d and d.get("f43"):
                pr = round(float(d["f43"])/100, 2)
                cp = round(float(d.get("f170",0))/100, 2)
                ca = round(float(d.get("f169",0))/100, 2)
                return {"code": code, "name": str(d.get("f58","")), "price": pr,
                        "change_pct": cp, "change_amount": ca, "volume": 0, "amount": 0,
                        "high": pr+abs(ca), "low": pr-abs(ca), "open": pr-ca, "pre_close": pr-ca, "turnover": 0}
        except Exception:
            pass
        # Sina fallback
        try:
            idx_prefix = f"s_{market}" if market in ("sh","sz") else "s_sh"
            url = f"https://hq.sinajs.cn/list={idx_prefix}{code}"
            r = requests.get(url, headers={"Referer":"https://finance.sina.com.cn"}, timeout=10)
            t = r.text
            if '=""' not in t:
                parts = t.split('"')
                if len(parts)>=2:
                    fld = parts[1].split(",")
                    if len(fld)>=4:
                        nm, pr = fld[0], float(fld[1])
                        ca, cp = float(fld[2]), float(fld[3])
                        return {"code":code,"name":nm,"price":round(pr,2),"change_pct":round(cp,2),
                                "change_amount":round(ca,2),"volume":0,"amount":0,
                                "high":pr+abs(ca),"low":pr-abs(ca),"open":pr-ca,"pre_close":pr-ca,"turnover":0}
        except Exception:
            pass
        return None

    # Regular stock: EastMoney first, Sina fallback
    try:
        # Global index support (codes with dot like "100.HSI")
        if "." in code:
            secid = code
        else:
            secid = f"1.{code}" if code.startswith(("6","9")) else f"0.{code}"
        params = {
            "secid": secid,
            "fields": "f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f169,f170"
        }
        STOCK_API = "https://push2.eastmoney.com/api/qt/stock/get"
        r = requests.get(STOCK_API, params=params, timeout=10)
        r.raise_for_status()
        d = r.json().get("data", {})
        if d and d.get("f43"):
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
        pass
    # Sina fallback
    try:
        prefix = "sh" if code.startswith(("6","9")) else "sz"
        url = f"https://hq.sinajs.cn/list={prefix}{code}"
        r = requests.get(url, headers={"Referer":"https://finance.sina.com.cn"}, timeout=10)
        t = r.text
        if "=" not in t or t.strip().endswith('=""'):
            return None
        data = t.split('"')[1].split(",")
        if len(data) < 10:
            return None
        price = float(data[3])
        pre_close = float(data[2])
        change_pct = round((price-pre_close)/pre_close*100,2) if pre_close>0 else 0
        return {
            "code":code,"name":data[0],"price":price,"change_pct":change_pct,
            "change_amount":round(price-pre_close,2),"volume":int(float(data[8])),
            "amount":round(float(data[9]),2),"high":float(data[4]),"low":float(data[5]),
            "open":float(data[1]),"pre_close":pre_close,"turnover":0,
        }
    except Exception:
        return None


def get_batch_quotes(codes: list[str]) -> dict[str, dict]:
    """Batch-fetch realtime quotes via EastMoney ulist.np/get, chunked <=50.

    Returns {code: quote_dict} with the same shape as get_realtime_quote.
    Codes that fail (or global codes) fall back to per-code get_realtime_quote.
    """
    if not codes:
        return {}

    index_secids = {
        "000001": "1.000001", "399001": "0.399001", "399006": "0.399006",
        "000688": "1.000688", "000300": "1.000300",
    }
    results: dict[str, dict] = {}
    seen: set[str] = set()
    unique = [c for c in codes if not (c in seen or seen.add(c))]
    chunks = [unique[i:i + QUOTE_POLL_CHUNK_SIZE] for i in range(0, len(unique), QUOTE_POLL_CHUNK_SIZE)]

    for chunk in chunks:
        secid_map: dict[str, str] = {}
        for code in chunk:
            if "." in code:
                continue  # global codes (e.g. 100.HSI) -> per-code fallback
            secid_map[code] = index_secids.get(code) or (
                f"1.{code}" if code.startswith(("6", "9")) else f"0.{code}"
            )
        if secid_map:
            try:
                url = "https://push2.eastmoney.com/api/qt/ulist.np/get"
                params = {
                    "fltt": 2,
                    "fields": "f2,f3,f4,f5,f6,f8,f12,f14,f15,f16,f17,f18",
                    "secids": ",".join(secid_map.values()),
                }
                r = requests.get(url, params=params, headers={"Referer": "https://quote.eastmoney.com"}, timeout=10)
                data = r.json().get("data", {}) or {}
                for item in data.get("diff", []) or []:
                    code = item.get("f12")
                    if not code:
                        continue
                    results[code] = {
                        "code": code,
                        "name": str(item.get("f14", "")),
                        "price": round(_safe_float(item.get("f2")), 2),
                        "change_pct": round(_safe_float(item.get("f3")), 2),
                        "change_amount": round(_safe_float(item.get("f4")), 2),
                        "volume": int(_safe_float(item.get("f5"))),
                        "amount": round(_safe_float(item.get("f6")), 2),
                        "turnover": round(_safe_float(item.get("f8")), 2),
                        "high": round(_safe_float(item.get("f15")), 2),
                        "low": round(_safe_float(item.get("f16")), 2),
                        "open": round(_safe_float(item.get("f17")), 2),
                        "pre_close": round(_safe_float(item.get("f18")), 2),
                    }
            except Exception:
                pass
        # Fallback for codes missing from the batch response
        for code in chunk:
            if code in results:
                continue
            market = "sh" if code.startswith(("6", "9")) else "sz"
            q = get_realtime_quote(code, market)
            if q:
                results[code] = q
    return results


@memo_ttl(30)
def get_kline_data(code: str, market: str = "sz", days: int = 10000, klt: str = "101") -> list[dict]:
    index_secids = {
        "000001": "1.000001", "399001": "0.399001", "399006": "0.399006",
        "000688": "1.000688", "000300": "1.000300",
    }

    def _parse_em_kline(resp, scale=1):
        data = resp.json().get("data", {})
        kls = data.get("klines", []) if data else []
        result = []
        for line in kls:
            p = line.split(",")
            if len(p) >= 6:
                result.append({
                    "date": p[0], "open": float(p[1])/scale, "close": float(p[2])/scale,
                    "high": float(p[3])/scale, "low": float(p[4])/scale,
                    "volume": int(float(p[5])), "amount": round(float(p[2])/scale*int(float(p[5])), 2),
                })
        return result[-days:] if len(result) > days else result

    def _fetch_sina_kline(symbol: str, scale: str, limit: int) -> list[dict]:
        """Fetch K-line from Sina Finance. scale: 240=daily, 1200=weekly, 7200=monthly."""
        try:
            url = f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=no&datalen={limit}"
            r = requests.get(url, headers={"Referer": "https://finance.sina.com.cn"}, timeout=15)
            r.raise_for_status()
            raw = r.json()
            if not raw or not isinstance(raw, list):
                return []
            result = []
            for item in raw[-limit:]:
                result.append({
                    "date": item["day"],
                    "open": float(item["open"]),
                    "close": float(item["close"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "volume": int(float(item.get("volume", 0))),
                    "amount": round(float(item["close"]) * int(float(item.get("volume", 0))), 2),
                })
            return result[-days:] if len(result) > days else result
        except Exception as e:
            print(f"Sina kline err {symbol}: {e}")
            return []

    # Global index K-line
    if "." in code:
        try:
            pm = {"101":"101","102":"102","103":"103"}
            emk = pm.get(klt, "101")
            url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={code}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt={emk}&fqt=1&end=20500101&lmt={min(days,10000)}"
            r = requests.get(url, headers={"Referer":"https://quote.eastmoney.com"}, timeout=15)
            return _parse_em_kline(r)
        except Exception as e:
            print(f"Global kline em err {code}: {e}")
        # Sina fallback for HK/global
        try:
            sina_map_global = {
                "100.HSI": "hkHSI", "100.HSCEI": "hkHSCEI",
                "100.N225": "nikkei225",
            }
            sn = sina_map_global.get(code)
            if sn:
                scale_map = {"101": "240", "102": "1200", "103": "7200"}
                scale = scale_map.get(klt, "240")
                result = _fetch_sina_kline(sn, scale, days)
                if result:
                    return result
        except Exception as e:
            print(f"Global kline sina fallback err {code}: {e}")
        return []

    # A-share index K-line
    if code in index_secids:
        try:
            secid = index_secids[code]
            url = f"https://push2his.eastmoney.com/api/qt/stock/kline/get?secid={secid}&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt={klt}&fqt=1&end=20500101&lmt={min(days,10000)}"
            r = requests.get(url, headers={"Referer":"https://quote.eastmoney.com"}, timeout=15)
            return _parse_em_kline(r)
        except Exception as e:
            print(f"Index kline em err {code}: {e}")
        # Sina fallback
        try:
            scale_map = {"101": "240", "102": "1200", "103": "7200"}
            scale = scale_map.get(klt, "240")
            sx = "sh" if code == "000001" or code == "000688" or code == "000016" or code == "000300" else "sz"
            symbol = f"{sx}{code}"
            result = _fetch_sina_kline(symbol, scale, days)
            if result:
                return result
        except Exception as e:
            print(f"Index kline sina fallback err {code}: {e}")
        return []

    # Regular stock
    try:
        # Global index support (codes with dot like "100.HSI")
        if "." in code:
            secid = code
        else:
            secid = f"1.{code}" if code.startswith(("6","9")) else f"0.{code}"
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": klt,
            "fqt": "1",
            "end": "20500101",
            "lmt": str(min(days, 10000)),
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
    except Exception as e:
        print(f"Stock kline em err {code}: {e}")
        # Sina fallback
        try:
            scale_map = {"101": "240", "102": "1200", "103": "7200"}
            scale = scale_map.get(klt, "240")
            sx = "sh" if code.startswith(("6", "9")) else "sz"
            symbol = f"{sx}{code}"
            result = _fetch_sina_kline(symbol, scale, days)
            if result:
                return result
        except Exception as e2:
            print(f"Stock kline sina fallback err {code}: {e2}")
        # akshare fallback (last resort)
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



def get_intraday(code: str, date: str = "", klt: str = "5") -> list[dict]:
    """Get intraday 5-min bars for a specific date. Falls back to synthetic data from daily K-line."""
    try:
        # Global index support (codes with dot like "100.HSI")
        if "." in code:
            secid = code
        else:
            secid = f"1.{code}" if code.startswith(("6","9")) else f"0.{code}"
        params = {
            "secid": secid,
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": klt,
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

        # No data for target date - find the most recent date with bars
        if klines:
            date_bars = {}
            for line in klines:
                parts = line.split(",")
                d = parts[0][:10]
                if d not in date_bars:
                    date_bars[d] = []
                date_bars[d].append({
                    "time": parts[0],
                    "price": float(parts[2]),
                    "volume": int(parts[5]),
                    "avg_price": float(parts[6]) / max(int(parts[5]), 1),
                })
            if date_bars:
                latest_date = max(date_bars.keys())
                result = date_bars[latest_date]
                for bar in result:
                    bar["fallback_date"] = latest_date
                return result

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

@memo_ttl(10)
def get_market_indices() -> list[dict]:
    """Get A-share indices. Tries EastMoney batch, then individual quotes."""
    results = []
    try:
        em = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&fields=f2,f3,f12,f14&secids=1.000001,0.399001,0.399006,1.000688,1.000300"
        r = requests.get(em, headers={"Referer":"https://quote.eastmoney.com"}, timeout=10)
        for it in r.json().get("data",{}).get("diff",[]):
            results.append({"name":it["f14"], "code":it["f12"].split(".")[-1],
                           "price":round(float(it["f2"])/100,2), "change_pct":float(it["f3"])})
    except Exception:
        pass
    # Fill missing via individual quotes
    all_idx = [("000001","sh"),("399001","sz"),("399006","sz"),("000688","sh"),("000300","sh")]
    have = {r["code"] for r in results}
    for cd, mk in all_idx:
        if cd not in have:
            try:
                q = get_realtime_quote(cd, mk)
                if q: results.append({"name":q["name"],"code":cd,"price":q["price"],"change_pct":q["change_pct"]})
            except Exception:
                pass
    return results

# ── News ──────────────────────────────────────────────
@memo_ttl(120)
def get_news(page: int = 1, limit: int = 20) -> dict:
    import time as _t
    url = f"https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num={limit}&page={page}&_={int(_t.time())}"
    try:
        r = requests.get(url, headers={"Referer":"https://finance.sina.com.cn"}, timeout=15)
        data = r.json()
        items = []
        for it in data.get("result",{}).get("data",[]):
            items.append({"title":it.get("title",""),"url":it.get("url",""),"intro":it.get("intro",""),
                          "ctime":it.get("ctime",""),"source":it.get("source","新浪财经")})
        return {"news":items, "total":data.get("result",{}).get("total",0)}
    except Exception as e:
        print(f"get_news err: {e}")
        return {"news":[], "total":0}

# ── Fund Search ────────────────────────────────────────
_fund_cache: dict = {}
_fund_cache_ts: float = 0

@memo_ttl(300)
def search_funds(keyword: str) -> list[dict]:
    global _fund_cache, _fund_cache_ts
    import time as _t
    kw = keyword.strip().lower()
    now = _t.time()
    if not _fund_cache or (now - _fund_cache_ts) > 3600:
        try:
            df = ak.fund_name_em()
            _fund_cache = {row["基金代码"]: {"code":row["基金代码"],"name":row["基金简称"],
                "pinyin":row["拼音全称"],"pinyin_short":row["拼音缩写"],"fund_type":row["基金类型"]}
                for _,row in df.iterrows()}
            _fund_cache_ts = now
        except Exception as e:
            print(f"search_funds err: {e}"); return []
    results = []
    for cd, info in _fund_cache.items():
        if kw in info["code"] or kw in info["name"].lower() or kw in info["pinyin"].lower() or kw in info["pinyin_short"].lower():
            results.append(info)
    results.sort(key=lambda x: (x["code"]!=keyword, x["code"]))
    return results[:30]

# ── Fund NAV ───────────────────────────────────────────
@memo_ttl(300)
def get_fund_nav(code: str) -> dict:
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty: return {"error":"基金未找到"}
        try:
            idf = ak.fund_individual_basic_info_xq(symbol=code)
            info = dict(zip(idf["item"], idf["value"]))
        except Exception:
            info = {}
        df.columns = ["date","nav","daily_return"]
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
        df["daily_return"] = pd.to_numeric(df["daily_return"], errors="coerce")
        df = df.dropna(subset=["nav"]).sort_values("date")
        if df.empty: return {"error":"无净值数据"}
        nl = df.to_dict(orient="records")
        lt = nl[-1]
        def cr(days):
            if len(nl)<2: return None
            si = max(0, len(nl)-1-days)
            sn, en = nl[si]["nav"], lt["nav"]
            if sn and sn>0: return round((en/sn-1)*100,2)
            return None
        periods = {"近1月":cr(22),"近3月":cr(66),"近6月":cr(132),"近1年":cr(252),"近2年":cr(504),"近5年":cr(1260)}
        if len(nl)>1 and nl[0]["nav"] and nl[0]["nav"]>0:
            periods["成立以来"] = round((lt["nav"]/nl[0]["nav"]-1)*100,2)
        return {"code":code,"name":info.get("基金名称",""),"fund_type":info.get("基金类型",""),
                "company":info.get("基金公司",""),"setup_date":info.get("成立时间",""),
                "manager":info.get("基金经理",""),"nav":lt["nav"],"daily_return":lt.get("daily_return"),
                "nav_date":lt["date"],"period_returns":periods,"nav_history":nl}
    except Exception as e:
        print(f"get_fund_nav err {code}: {e}")
        return {"error":str(e)}

# ── Fund Recommendations ───────────────────────────────
import concurrent.futures as _cf
import threading as _threading

_fund_rank_cache: dict = {}
_fund_rank_lock = _threading.Lock()


def _fund_rank(sym: str):
    """Fetch & memoize the akshare fund rank DataFrame for a symbol (2 min)."""
    import time as _t
    now = _t.time()
    with _fund_rank_lock:
        hit = _fund_rank_cache.get(sym)
        if hit and (now - hit[0]) < 120:
            return hit[1]
    df = ak.fund_open_fund_rank_em(symbol=sym)
    with _fund_rank_lock:
        _fund_rank_cache[sym] = (now, df)
    return df


@memo_ttl(300)
def get_fund_recommendations() -> dict:
    import time as _t, random as _rd
    now = _t.time()

    def pick(sym, cnt=8, sc="近1年"):
        try:
            df = _fund_rank(sym)
            df = df.dropna(subset=[sc]).sort_values(sc, ascending=False)
            pool = df.head(30)
            sel = pool.sample(n=min(cnt, len(pool)), random_state=int(now) % 10000)
            return [{"code": str(r["基金代码"]), "name": str(r["基金简称"]),
                     "nav": float(r["单位净值"]) if pd.notna(r["单位净值"]) else None,
                     "daily_return": float(r["日增长率"]) if pd.notna(r["日增长率"]) else None,
                     "return_1m": float(r["近1月"]) if pd.notna(r["近1月"]) else None,
                     "return_1y": float(r["近1年"]) if pd.notna(r["近1年"]) else None}
                    for _, r in sel.iterrows()]
        except Exception as e:
            print(f"pick({sym}) err: {e}"); return []

    def gold_oil(cnt=8):
        try:
            df = _fund_rank("全部")  # reuse the cached "全部" table
            m = df["基金简称"].str.contains("黄金|石油", na=False, case=False)
            go = df[m].dropna(subset=["近1年"]).sort_values("近1年", ascending=False)
            pool = go.head(min(30, len(go)))
            sel = pool.sample(n=min(cnt, len(pool)), random_state=int(now) % 10000 + 1)
            return [{"code": str(r["基金代码"]), "name": str(r["基金简称"]),
                     "nav": float(r["单位净值"]) if pd.notna(r["单位净值"]) else None,
                     "daily_return": float(r["日增长率"]) if pd.notna(r["日增长率"]) else None,
                     "return_1m": float(r["近1月"]) if pd.notna(r["近1月"]) else None,
                     "return_1y": float(r["近1年"]) if pd.notna(r["近1年"]) else None}
                    for _, r in sel.iterrows()]
        except Exception as e:
            print(f"gold_oil err: {e}"); return []

    with _cf.ThreadPoolExecutor(max_workers=4) as ex:
        f_hot = ex.submit(pick, "全部", 8, "近1年")
        f_bond = ex.submit(pick, "债券型", 8, "近1年")
        f_index = ex.submit(pick, "指数型", 8, "近1年")
        f_qdii = ex.submit(pick, "QDII", 8, "近1年")
        f_comm = ex.submit(gold_oil, 8)
        res = {
            "hot": f_hot.result(),
            "bond": f_bond.result(),
            "index": f_index.result(),
            "qdii": f_qdii.result(),
            "commodity": f_comm.result(),
        }
    return res

# ── Fund Holdings ──────────────────────────────────────
@memo_ttl(300)
def get_fund_holdings(code: str) -> dict:
    try:
        sdf = ak.fund_portfolio_hold_em(symbol=code)
        if sdf is None or sdf.empty:
            return {"stocks":[],"industries":[],"quarter":""}
        lq = sdf["季度"].iloc[0]
        ls = sdf[sdf["季度"]==lq].head(10)
        stocks = [{"code":str(r["股票代码"]),"name":str(r["股票名称"]),"pct":float(r["占净值比例"])} for _,r in ls.iterrows()]
        try:
            idf = ak.fund_portfolio_industry_allocation_em(symbol=code)
            li = idf["截止时间"].iloc[0] if not idf.empty else ""
            lid = idf[idf["截止时间"]==li].head(10)
            industries = [{"name":str(r["行业类别"]),"pct":float(r["占净值比例"])} for _,r in lid.iterrows()]
        except Exception:
            industries = []
        return {"quarter":lq,"stocks":stocks,"industries":industries}
    except Exception as e:
        print(f"get_fund_holdings err {code}: {e}")
        return {"stocks":[],"industries":[],"quarter":""}

# ── Global Indices ─────────────────────────────────────
_gi_cache: list = []
_gi_cache_ts: float = 0

def get_global_indices() -> list[dict]:
    global _gi_cache, _gi_cache_ts
    import time as _t
    now = _t.time()
    if _gi_cache and (now - _gi_cache_ts) < 300:
        return _gi_cache
    groups = [
        ("中国", [("上证指数","1.000001","sh"),("深证成指","0.399001","sz"),
                  ("创业板指","0.399006","sz"),("科创50","1.000688","sh"),("沪深300","1.000300","sh")]),
        ("港股", [("恒生指数","100.HSI","hk"),("国企指数","100.HSCEI","hk")]),
        ("美股", [("道琼斯","100.DJIA","us"),("纳斯达克","100.NDX","us"),("标普500","100.SPX","us")]),
        ("日本", [("日经225","100.N225","jp")]),
        ("韩国", [("韩国KOSPI","100.KS11","kr")]),
        ("欧洲", [("英国富时100","100.FTSE","uk"),("德国DAX30","100.GDAXI","de")]),
        ("台湾", [("台湾加权","100.TWII","tw")]),
    ]
    sina_data = {}
    try:
        ac = "s_sh000001,s_sz399001,s_sz399006,s_sh000688,s_sh000300"
        r = requests.get(f"https://hq.sinajs.cn/list={ac}", headers={"Referer":"https://finance.sina.com.cn"}, timeout=10)
        for ln in r.text.strip().split("\n"):
            if '=""' in ln: continue
            parts = ln.split('"')
            if len(parts)>=2:
                fld = parts[1].split(",")
                if len(fld)>=4:
                    sina_data[fld[0]] = {"price":float(fld[1]), "change_pct":float(fld[3])}
    except Exception as e:
        print(f"Global sina err: {e}")
    em_map = {}
    try:
        es = "100.HSI,100.HSCEI,100.DJIA,100.NDX,100.SPX,100.N225,100.KS11,100.FTSE,100.GDAXI,100.TWII"
        r = requests.get(f"https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&fields=f2,f3,f12,f14&secids={es}",
                        headers={"Referer":"https://quote.eastmoney.com"}, timeout=10)
        for it in r.json().get("data",{}).get("diff",[]):
            em_map["100." + it.get("f12","")] = {"price":it["f2"], "change_pct":it["f3"]}
    except Exception as e:
        print(f"Global em err: {e}")
    # Fallback: always run if EastMoney returned no data (empty or failed)
    if not em_map:
        # Also try znb_ prefix for Korea/Taiwan (Sina global index codes)
        try:
            r_znb = requests.get("https://hq.sinajs.cn/list=znb_KOSPI,znb_TWJQ",
                                headers={"Referer":"https://finance.sina.com.cn"}, timeout=10)
            for ln in r_znb.text.strip().split("\n"):
                if '=""' in ln: continue
                parts = ln.split('"')
                if len(parts)>=2:
                    fld = parts[1].split(",")
                    if len(fld)>=4:
                        znb_code = ln.split("=")[0].replace("var hq_str_","").strip()
                        if znb_code == "znb_KOSPI":
                            em_map["100.KS11"] = {"price": float(fld[1]), "change_pct": float(fld[3])}
                        elif znb_code == "znb_TWJQ":
                            em_map["100.TWII"] = {"price": float(fld[1]), "change_pct": float(fld[3])}
        except Exception as e:
            print(f"Global znb fallback err: {e}")
        for code, mkt in [("100.HSI","hk"),("100.HSCEI","hk"),("100.DJIA","us"),
                          ("100.NDX","us"),("100.SPX","us"),("100.N225","jp"),
                          ("100.FTSE","uk"),("100.GDAXI","de")]:
            try:
                q = get_realtime_quote(code, mkt)
                if q:
                    em_map[code] = {"price": q["price"], "change_pct": q["change_pct"]}
            except Exception:
                pass
    result = []
    for country, indices in groups:
        items = []
        for name, secid, market in indices:
            info = sina_data.get(name) if market in ("sh","sz") else em_map.get(secid)
            if info and info.get("price") is not None:
                items.append({"name":name,"code":secid,"market":market,
                             "price":round(info["price"],2) if market in ("sh","sz") else round(float(info["price"]),2),
                             "change_pct":round(info["change_pct"],2)})
        if items:
            result.append({"country":country,"indices":items})
    # Only update cache if we got at least 3 country groups (China + some global)
    if len(result) >= 3:
        _gi_cache = result
        _gi_cache_ts = now
    elif not _gi_cache:
        # Don't cache incomplete results; return what we have but don't persist
        pass
    return result if len(result) >= 2 else (_gi_cache or result)
