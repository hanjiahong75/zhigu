from curl_cffi import requests
import json

r = requests.get("http://127.0.0.1:8000/api/kline?code=600519&market=sh&days=10000&klt=101", timeout=15)
d = r.json()
k = d.get("kline", [])
print(f"Kline count: {len(k)}")
if k:
    print(f"First: {k[0]['date']}")
    print(f"Last: {k[-1]['date']}")
