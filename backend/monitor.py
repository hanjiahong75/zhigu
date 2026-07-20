"""Standalone market monitor daemon.

Polls watchlist stocks during A-share trading hours and writes alerts to a JSON file.
Run: python monitor.py

Trading hours:
- Morning: 09:30-11:30
- Afternoon: 13:00-15:00
- Polling interval: 5 minutes during market, 30 minutes off-market
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, time as dtime
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.models.database import SessionLocal
from app.models.stock import WatchlistItem
from app.services.stock_data import get_realtime_quote, get_kline_data
from app.services.technical import calc_all_indicators

logger = logging.getLogger("monitor")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler()],
)

ALERTS_FILE = Path(__file__).resolve().parent / "data" / "alerts.json"
MARKET_OPEN_MORNING = dtime(9, 30)
MARKET_CLOSE_MORNING = dtime(11, 30)
MARKET_OPEN_AFTERNOON = dtime(13, 0)
MARKET_CLOSE_AFTERNOON = dtime(15, 0)
POLL_INTERVAL_MARKET = 300   # 5 minutes
POLL_INTERVAL_OFF = 1800     # 30 minutes
CHANGE_THRESHOLD = 3.0       # Alert on >=3% change


def is_market_open() -> bool:
    """Check if A-share market is currently open."""
    now = datetime.now()
    t = now.time()
    # Skip weekends
    if now.weekday() >= 5:
        return False
    return (MARKET_OPEN_MORNING <= t <= MARKET_CLOSE_MORNING) or            (MARKET_OPEN_AFTERNOON <= t <= MARKET_CLOSE_AFTERNOON)


def get_watchlist():
    """Get active watchlist stocks from DB."""
    db = SessionLocal()
    try:
        items = db.query(WatchlistItem).filter(WatchlistItem.is_active == True).all()
        return [{"code": i.code, "name": i.name, "market": i.market} for i in items]
    finally:
        db.close()


def check_stock(stock: dict) -> list[dict]:
    """Check a single stock for alert conditions. Returns list of alert dicts."""
    alerts = []
    code = stock["code"]
    name = stock["name"]
    market = stock["market"]

    try:
        quote = get_realtime_quote(code, market)
        if not quote:
            return alerts

        price = quote.get("price", 0)
        change_pct = quote.get("change_pct", 0)
        turnover = quote.get("turnover", 0)
        volume = quote.get("volume", 0)

        # Condition 1: Significant price change
        if abs(change_pct) >= CHANGE_THRESHOLD:
            direction = "📈" if change_pct > 0 else "📉"
            alerts.append({
                "type": "price_change",
                "stock_code": code,
                "stock_name": name,
                "message": f"{direction} {name}({code}) {'涨' if change_pct > 0 else '跌'}{abs(change_pct):.1f}%",
                "price": price,
                "change_pct": change_pct,
                "time": datetime.now().strftime("%H:%M:%S"),
            })

        # Condition 2: High turnover (unusual volume)
        if turnover > 10:
            alerts.append({
                "type": "high_turnover",
                "stock_code": code,
                "stock_name": name,
                "message": f"🔄 {name}({code}) 换手率{ turnover:.1f}%，成交活跃",
                "price": price,
                "turnover": turnover,
                "time": datetime.now().strftime("%H:%M:%S"),
            })

        # Condition 3: Technical signals (MA crossover, RSI extremes)
        try:
            kline = get_kline_data(code, market, 120, "101")
            if kline and len(kline) >= 30:
                indicators = calc_all_indicators(kline)
                # RSI extremes
                rsi = indicators.get("rsi", {}).get("rsi14", [])
                if rsi and rsi[-1] is not None:
                    if rsi[-1] > 70:
                        alerts.append({
                            "type": "rsi_overbought",
                            "stock_code": code,
                            "stock_name": name,
                            "message": f"⚠️ {name}({code}) RSI={rsi[-1]:.0f}，进入超买区",
                            "price": price,
                            "rsi": round(rsi[-1], 1),
                            "time": datetime.now().strftime("%H:%M:%S"),
                        })
                    elif rsi[-1] < 30:
                        alerts.append({
                            "type": "rsi_oversold",
                            "stock_code": code,
                            "stock_name": name,
                            "message": f"💡 {name}({code}) RSI={rsi[-1]:.0f}，进入超卖区",
                            "price": price,
                            "rsi": round(rsi[-1], 1),
                            "time": datetime.now().strftime("%H:%M:%S"),
                        })
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"Check failed for {code} {name}: {e}")

    return alerts


def save_alerts(alerts: list[dict]):
    """Save alerts to JSON file."""
    os.makedirs(ALERTS_FILE.parent, exist_ok=True)
    with open(ALERTS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "alerts": alerts[-20:],  # Keep last 20 alerts
        }, f, ensure_ascii=False, indent=2)


def run_once():
    """Single polling cycle."""
    stocks = get_watchlist()
    if not stocks:
        logger.info("No watchlist stocks to monitor")
        return

    logger.info(f"Checking {len(stocks)} stocks...")
    all_alerts = []
    for stock in stocks:
        stock_alerts = check_stock(stock)
        all_alerts.extend(stock_alerts)

    if all_alerts:
        save_alerts(all_alerts)
        for a in all_alerts:
            logger.info(f"ALERT: {a['message']}")
    else:
        logger.info("No alerts triggered")


def main():
    """Main loop."""
    logger.info("Monitor daemon started")
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"Polling cycle failed: {e}")

        if is_market_open():
            interval = POLL_INTERVAL_MARKET
            logger.info(f"Market open, next poll in {interval}s")
        else:
            interval = POLL_INTERVAL_OFF
            logger.info(f"Market closed, next poll in {interval}s")

        time.sleep(interval)


if __name__ == "__main__":
    main()
