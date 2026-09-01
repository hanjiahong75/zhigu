"""Unit tests for the strategy signal service (M3)."""

import unittest

from app.services import signal_service as ss
from app.services.signal_service import (
    DEFAULT_WEIGHTS,
    boll_signal,
    compose_signal,
    compute_signal,
    ma_signal,
    rsi_signal,
    volume_signal,
)


def _kline(closes, volumes=None):
    """Build synthetic K-line bars from close prices."""
    bars = []
    for i, c in enumerate(closes):
        v = (volumes or [1000] * len(closes))[i]
        bars.append({
            "date": f"2026-01-{i + 1:02d}",
            "open": round(c - 0.1, 2),
            "close": round(c, 2),
            "high": round(c + 0.2, 2),
            "low": round(c - 0.2, 2),
            "volume": v,
            "amount": round(c * v, 2),
        })
    return bars


class MaSignalTest(unittest.TestCase):
    def test_golden_cross(self):
        closes = [10.0] * 30 + [10.0, 12.0]
        sig = ma_signal(closes)
        self.assertTrue(sig["available"])
        self.assertEqual(sig["score"], 1.0)
        self.assertIn("金叉", sig["detail"])

    def test_death_cross(self):
        closes = [10.0] * 30 + [10.0, 8.0]
        sig = ma_signal(closes)
        self.assertTrue(sig["available"])
        self.assertEqual(sig["score"], -1.0)
        self.assertIn("死叉", sig["detail"])

    def test_bullish_alignment(self):
        closes = [10.0 + 0.3 * i for i in range(30)]
        sig = ma_signal(closes)
        self.assertEqual(sig["score"], 0.5)
        self.assertIn("多头", sig["detail"])


class RsiSignalTest(unittest.TestCase):
    def test_overbought(self):
        closes = [float(i) for i in range(1, 21)]  # rising prices
        sig = rsi_signal(closes)
        self.assertEqual(sig["score"], -0.8)
        self.assertIn("超买", sig["detail"])

    def test_oversold(self):
        closes = [float(i) for i in range(20, 0, -1)]  # falling prices
        sig = rsi_signal(closes)
        self.assertEqual(sig["score"], 0.8)
        self.assertIn("超卖", sig["detail"])


class BollSignalTest(unittest.TestCase):
    def test_upper_breakout(self):
        closes = [10.0] * 20 + [20.0]
        sig = boll_signal(closes)
        self.assertTrue(sig["available"])
        self.assertEqual(sig["score"], 1.0)
        self.assertIn("上穿", sig["detail"])

    def test_lower_breakout(self):
        closes = [10.0] * 20 + [1.0]
        sig = boll_signal(closes)
        self.assertEqual(sig["score"], -1.0)


class VolumeSignalTest(unittest.TestCase):
    def test_volume_price_up(self):
        closes = [10.0] * 6 + [11.0]
        volumes = [10.0] * 6 + [100.0]
        sig = volume_signal(closes, volumes)
        self.assertEqual(sig["score"], 0.5)
        self.assertIn("量价配合", sig["detail"])

    def test_volume_price_down(self):
        closes = [10.0] * 6 + [9.0]
        volumes = [10.0] * 6 + [100.0]
        sig = volume_signal(closes, volumes)
        self.assertEqual(sig["score"], -0.5)
        self.assertIn("放量下跌", sig["detail"])


class ComposeSignalTest(unittest.TestCase):
    def _component(self, score, name="测试", weight=None):
        return {
            "name": name, "score": score,
            "weight": weight or DEFAULT_WEIGHTS.get(name, 0.2),
            "detail": name, "available": True,
        }

    def test_all_bullish(self):
        comps = [self._component(1.0, n) for n in DEFAULT_WEIGHTS]
        result = compose_signal(comps)
        self.assertEqual(result["score"], 1.0)
        self.assertEqual(result["rating"], "强烈买入")
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["confidence"], 1.0)

    def test_mixed_rating_buy(self):
        scores = {"ma": 1.0, "macd": -1.0, "rsi": 0.5, "boll": 0.0, "volume": 0.5}
        comps = [self._component(scores[n], n) for n in DEFAULT_WEIGHTS]
        result = compose_signal(comps)
        self.assertEqual(result["score"], 0.25)
        self.assertEqual(result["rating"], "买入")
        self.assertEqual(result["confidence"], 0.32)

    def test_no_available(self):
        comps = [{"name": n, "score": 0.0, "weight": 0.2, "detail": "", "available": False}
                 for n in DEFAULT_WEIGHTS]
        result = compose_signal(comps)
        self.assertEqual(result["rating"], "观望")
        self.assertEqual(result["score"], 0.0)


class ComputeSignalTest(unittest.TestCase):
    def test_compute_signal_with_kline(self):
        closes = [10.0 + 0.1 * i for i in range(60)]
        kline = _kline(closes, [1000] * 59 + [2000])
        result = compute_signal("600519", "sh", kline=kline, name="测试股份")
        self.assertNotIn("error", result)
        self.assertEqual(result["code"], "600519")
        self.assertEqual(result["name"], "测试股份")
        self.assertIn(result["rating"], ["强烈买入", "买入", "观望", "卖出", "强烈卖出"])
        self.assertGreaterEqual(result["coverage"], 0.2)
        self.assertTrue(result["components"])

    def test_empty_kline_returns_error(self):
        result = compute_signal("000001", "sz", kline=[], name="测试")
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
