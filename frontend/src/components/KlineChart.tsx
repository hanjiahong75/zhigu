import { useEffect, useRef, useState, useCallback } from "react";
import {
  createChart, ColorType, CrosshairMode, LineStyle,
  type Time,
} from "lightweight-charts";
import type { KlineItem, IndicatorsData } from "../types";
import { getIntraday, PERIODS } from "../api/client";

interface Props {
  isDark?: boolean;
  data: KlineItem[];
  stockName: string;
  stockCode: string;
  indicators?: IndicatorsData | null;
  klt: string;
  onPeriodChange: (klt: string) => void;
  onLoadMore?: () => void;
  prevClose?: number;
}

const MA_COLORS = ["#ff6b6b", "#ffa726", "#42a5f5", "#ab47bc"];
const BOLL_COLORS = { upper: "#4fc3f7", mid: "#ffa726", lower: "#4fc3f7" };
const MACD_COLORS = { dif: "#42a5f5", dea: "#ffa726", up: "#ef444466", down: "#22c55e66" };
const RSI_COLORS = ["#ef4444", "#f59e0b", "#3b82f6"];

interface Visibility { ma: boolean; boll: boolean; volume: boolean; macd: boolean; rsi: boolean; }
interface TooltipInfo { x: number; y: number; item: KlineItem; changePct: number; prevClose: number; }

interface IntradayBar { time: string; price: number; volume: number; avg_price: number; }
interface IntradayState {
  bars: IntradayBar[]; date: string; loading: boolean; synthetic?: boolean; error?: string;
}

/** Convert date string to Time for lightweight-charts.
 *  Daily format "YYYY-MM-DD" stays as string; intraday "YYYY-MM-DD HH:MM" becomes Unix timestamp. */
function toTime(dateStr: string): Time {
  if (dateStr.includes(" ")) {
    const [date, time] = dateStr.split(" ");
    const [y, m, d] = date.split("-").map(Number);
    const [hh, mm] = time.split(":").map(Number);
    return Date.UTC(y, m - 1, d, hh, mm, 0) / 1000 as Time;
  }
  return dateStr as Time;
}

// dropdownStyle moved inside component

export default function KlineChart({ data, stockName, stockCode, indicators, klt, onPeriodChange, onLoadMore, isDark, prevClose: prevCloseProp }: Props) {
  const mainRef = useRef<HTMLDivElement>(null);
  const bgColor = isDark ? "#1a1a1a" : "#ffffff";
  const textColor = isDark ? "#d9d9d9" : "#333333";
  const gridColor = isDark ? "#333333" : "#f0f0f0";
  const dropdownStyle: React.CSSProperties = {
    padding: "2px 8px", fontSize: 12, borderRadius: 6, border: "1px solid #d9d9d9",
    background: bgColor, cursor: "pointer", outline: "none", color: textColor,
    height: 28, minWidth: 70,
  };
  const macdRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const chartsRef = useRef<ReturnType<typeof createChart>[]>([]);
  const mainChartRef = useRef<ReturnType<typeof createChart> | null>(null);
  const candleSeriesRef = useRef<any>(null);
  const volumeSeriesRef = useRef<any>(null);
  const prevDataRef = useRef<KlineItem[]>([]);
  const onLoadMoreRef = useRef(onLoadMore);
  onLoadMoreRef.current = onLoadMore;
  const [vis, setVis] = useState<Visibility>({ ma: true, boll: true, volume: true, macd: true, rsi: true });
  const [tooltip, setTooltip] = useState<TooltipInfo | null>(null);
  const [intraday, setIntraday] = useState<IntradayState | null>(null);
  const [showIntraday, setShowIntraday] = useState(false);
  const [todayIntraday, setTodayIntraday] = useState<IntradayState | null>(null);

  const toggle = (key: keyof Visibility) => setVis((v) => ({ ...v, [key]: !v[key] }));
  const btnStyle = (active: boolean, color: string) => ({
    padding: "1px 8px", fontSize: 11, borderRadius: 10, cursor: "pointer",
    border: `1px solid ${active ? color : "#e0e0e0"}`,
    background: active ? color : bgColor, color: active ? "#fff" : textColor,
    transition: "all 0.15s", lineHeight: "20px", userSelect: "none" as const,
  });

  const isIntraday = (k: string) => ["1","5","15","30","60","120"].includes(k);

  const handleClick = useCallback(async (param: any) => {
    if (!param.time || !param.point) { setTooltip(null); setIntraday(null); return; }
    const item = data.find((d: KlineItem) => d.date === param.time);
    if (!item) { setTooltip(null); setIntraday(null); return; }
    const _idx = data.findIndex((d: KlineItem) => d.date === item.date);
    const _prevClose = _idx > 0 ? data[_idx - 1].close : item.open;
    const _changePct = _prevClose > 0 ? ((item.close - _prevClose) / _prevClose) * 100 : 0;
    setTooltip({ x: Math.min(param.point.x + 12, 500), y: Math.max(param.point.y - 10, 60), item, changePct: _changePct, prevClose: _prevClose });

    // Fetch intraday data for non-intraday klt values
    if (isIntraday(klt)) { setIntraday(null); return; }
    const targetDate = item.date.length > 10 ? item.date.slice(0, 10) : item.date;
    setIntraday({ bars: [], date: targetDate, loading: true });
    try {
      const result = await getIntraday(stockCode, targetDate);
      if (result.bars && result.bars.length > 0) {
        setIntraday({ bars: result.bars, date: targetDate, loading: false, synthetic: result.synthetic });
      } else {
        setIntraday({ bars: [], date: targetDate, loading: false, error: "该日无分时数据" });
      }
    } catch (e: any) {
      setIntraday({ bars: [], date: targetDate, loading: false, error: e.message || "加载失败" });
    }
  }, [data, stockCode, klt]);

  const fetchTodayIntraday = useCallback(async () => {
    const today = new Date().toISOString().slice(0, 10);
    setTodayIntraday((prev: IntradayState | null) => prev ? { ...prev, loading: true } : { bars: [], date: today, loading: true });
    try {
      const result = await getIntraday(stockCode, today, "1");
      if (result.bars && result.bars.length > 0) {
        setTodayIntraday({ bars: result.bars, date: result.date || today, loading: false, synthetic: result.synthetic, fallback_date: result.fallback_date || "" });
      } else {
        setTodayIntraday({ bars: [], date: today, loading: false, error: "今日暂无分时数据" });
      }
    } catch (e: any) {
      setTodayIntraday({ bars: [], date: today, loading: false, error: e.message || "加载失败" });
    }
  }, [stockCode]);

  // Auto-refresh intraday during trading hours (UTC+8: 9:30-11:30, 13:00-15:00)
  useEffect(() => {
    if (!showIntraday) return;
    fetchTodayIntraday();
    const timer = setInterval(() => {
      const now = new Date();
      const minutes = now.getHours() * 60 + now.getMinutes();
      const isTrading = (minutes >= 570 && minutes <= 690) || (minutes >= 780 && minutes <= 900);
      if (isTrading) fetchTodayIntraday();
    }, 30000);
    return () => clearInterval(timer);
  }, [showIntraday, fetchTodayIntraday]);

  const mainH = isIntraday(klt) ? 400 : 300;
  const subH = 100;

  useEffect(() => {
    if (!mainRef.current || data.length === 0) return;
    chartsRef.current.forEach((c) => c.remove());
    chartsRef.current = [];

    const mainChart = createChart(mainRef.current, {
      layout: { background: { type: ColorType.Solid, color: bgColor }, textColor },
      width: mainRef.current.clientWidth, height: mainH,
      grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: {
        borderColor: "#e8e8e8",
        timeVisible: isIntraday(klt),
        barSpacing: isIntraday(klt) ? 3 : undefined,
      },
      rightPriceScale: { borderColor: "#e8e8e8" },
    });

    mainChart.subscribeClick(handleClick);

    const candleSeries = mainChart.addCandlestickSeries({
      upColor: "#ef4444", downColor: "#22c55e",
      borderDownColor: "#22c55e", borderUpColor: "#ef4444",
      wickDownColor: "#22c55e", wickUpColor: "#ef4444",
    });
    candleSeries.setData(data.map((d: KlineItem) => ({
      time: toTime(d.date),
      open: d.open, high: d.high, low: d.low, close: d.close,
    })));

    if (vis.volume) {
      const volSeries = mainChart.addHistogramSeries({
        color: "#d1d5db", priceFormat: { type: "volume" }, priceScaleId: "volume",
      });
      mainChart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });
      volSeries.setData(data.map((d: KlineItem) => ({
        time: toTime(d.date), value: d.volume,
        color: d.close >= d.open ? "rgba(239,68,68,0.35)" : "rgba(34,197,94,0.35)",
      })));
    }

    if (vis.ma && indicators?.ma && !isIntraday(klt)) {
      (["ma5","ma10","ma20","ma60"] as const).forEach((key, idx) => {
        const vals = indicators.ma[key]; if (!vals) return;
        const ld = data.map((d: KlineItem, i: number) => vals[i] != null ? { time: toTime(d.date), value: vals[i]! } : null).filter(Boolean) as any[];
        if (ld.length > 0) { const s = mainChart.addLineSeries({ color: MA_COLORS[idx], lineWidth: 1, priceLineVisible: false, lastValueVisible: false }); s.setData(ld); }
      });
    }

    if (vis.boll && indicators?.bollinger && !isIntraday(klt)) {
      const { upper, mid, lower } = indicators.bollinger;
      [upper, mid, lower].forEach((vals, idx) => {
        const colors = [BOLL_COLORS.upper, BOLL_COLORS.mid, BOLL_COLORS.lower];
        const ld = data.map((d: KlineItem, i: number) => vals[i] != null ? { time: toTime(d.date), value: vals[i]! } : null).filter(Boolean) as any[];
        if (ld.length > 0) { const s = mainChart.addLineSeries({ color: colors[idx], lineWidth: 1, lineStyle: idx === 1 ? LineStyle.Solid : LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false }); s.setData(ld); }
      });
    }

    chartsRef.current.push(mainChart);
    mainChartRef.current = mainChart;

    let macdChart: ReturnType<typeof createChart> | null = null;
    if (vis.macd && macdRef.current && !isIntraday(klt)) {
      macdChart = createChart(macdRef.current, {
        layout: { background: { type: ColorType.Solid, color: bgColor }, textColor },
        width: macdRef.current.clientWidth, height: subH,
        grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
        crosshair: { mode: CrosshairMode.Normal },
        timeScale: { borderColor: "#e8e8e8", visible: false },
        rightPriceScale: { borderColor: "#e8e8e8" },
      });
      if (indicators?.macd) {
        const { dif, dea, macd } = indicators.macd;
        const d1 = data.map((d: KlineItem, i: number) => dif[i] != null ? { time: toTime(d.date), value: dif[i]! } : null).filter(Boolean) as any[];
        const d2 = data.map((d: KlineItem, i: number) => dea[i] != null ? { time: toTime(d.date), value: dea[i]! } : null).filter(Boolean) as any[];
        const d3 = data.map((d: KlineItem, i: number) => macd[i] != null ? { time: toTime(d.date), value: macd[i]!, color: macd[i]! >= 0 ? MACD_COLORS.up : MACD_COLORS.down } : null).filter(Boolean) as any[];
        if (d1.length) { const s = macdChart.addLineSeries({ color: MACD_COLORS.dif, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }); s.setData(d1); }
        if (d2.length) { const s = macdChart.addLineSeries({ color: MACD_COLORS.dea, lineWidth: 1, priceLineVisible: false, lastValueVisible: false }); s.setData(d2); }
        if (d3.length) { const s = macdChart.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false }); s.setData(d3); }
      }
      chartsRef.current.push(macdChart);
    }

    let rsiChart: ReturnType<typeof createChart> | null = null;
    if (vis.rsi && rsiRef.current && !isIntraday(klt)) {
      rsiChart = createChart(rsiRef.current, {
        layout: { background: { type: ColorType.Solid, color: bgColor }, textColor },
        width: rsiRef.current.clientWidth, height: subH,
        grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
        crosshair: { mode: CrosshairMode.Normal },
        timeScale: { borderColor: "#e8e8e8", timeVisible: true },
        rightPriceScale: { borderColor: "#e8e8e8" },
      });
      if (indicators?.rsi) {
        (["rsi6","rsi14","rsi24"] as const).forEach((key, idx) => {
          const vals = indicators.rsi[key]; if (!vals) return;
          const ld = data.map((d: KlineItem, i: number) => vals[i] != null ? { time: toTime(d.date), value: vals[i]! } : null).filter(Boolean) as any[];
          if (ld.length > 0) { const s = rsiChart!.addLineSeries({ color: RSI_COLORS[idx], lineWidth: 1, priceLineVisible: false, lastValueVisible: false }); s.setData(ld); }
        });
        [70,30].forEach((level) => {
          const s = rsiChart!.addLineSeries({ color: "#ddd", lineWidth: 1, lineStyle: LineStyle.Dotted, priceLineVisible: false, lastValueVisible: false });
          s.setData(data.map((d: KlineItem) => ({ time: toTime(d.date), value: level })));
        });
      }
      chartsRef.current.push(rsiChart);
    }

    const subCharts = [macdChart, rsiChart].filter(Boolean) as ReturnType<typeof createChart>[];
    mainChart.timeScale().subscribeVisibleTimeRangeChange((range: any) => {
      if (range) subCharts.forEach((c) => c.timeScale().setVisibleRange(range));
    });

    // Detect scroll to far left for loading earlier data
    let loadMoreCooldown = false;
    mainChart.timeScale().subscribeVisibleLogicalRangeChange((range: any) => {
      if (!range || !onLoadMoreRef.current) return;
      // When user scrolls within 10 bars of the earliest loaded data
      if (range.from <= 10 && !loadMoreCooldown) {
        loadMoreCooldown = true;
        onLoadMoreRef.current();
        // Reset cooldown after a short delay so the next scroll can trigger again
        setTimeout(() => { loadMoreCooldown = false; }, 1500);
      }
    });
    // Show only last 50 bars by default, user can scroll left for more
    const totalBars = data.length;
    if (totalBars > 50) {
      mainChart.timeScale().setVisibleLogicalRange({ from: totalBars - 50, to: totalBars - 1 });
    } else {
      mainChart.timeScale().fitContent();
    }

    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width;
        if (w > 0) {
          mainChart.applyOptions({ width: w });
          subCharts.forEach((c) => c.applyOptions({ width: w }));
        }
      }
    });
    if (mainRef.current) ro.observe(mainRef.current);
    return () => {
      ro.disconnect();
      chartsRef.current.forEach((c) => c.remove());
      chartsRef.current = [];
    };
  }, [data.length === 0 ? 'empty' : klt, vis, isDark]);  // Only recreate on klt/vis/dark change, NOT on data change

  // Update chart data in-place when data prop changes (loadMore)
  useEffect(() => {
    if (!mainChartRef.current || !candleSeriesRef.current) return;
    const candleData = data.map((d: KlineItem) => ({
      time: toTime(d.date),
      open: d.open, high: d.high, low: d.low, close: d.close,
    }));
    candleSeriesRef.current.setData(candleData);

    const volData = data.map((d: KlineItem, i: number) => {
      const prevClose = i > 0 ? data[i - 1].close : d.open;
      return {
        time: toTime(d.date),
        value: d.volume,
        color: d.close >= prevClose ? "rgba(239,68,68,0.4)" : "rgba(34,197,94,0.4)",
      };
    });
    volumeSeriesRef.current.setData(volData);

    prevDataRef.current = data;
  }, [data]);

  if (data.length === 0) {
    return <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", background: bgColor, borderRadius: 8, color: textColor, marginBottom: 16 }}>暂无K线数据</div>;
  }

  const item = tooltip?.item;
  const changePct = tooltip?.changePct ?? 0;
  const prevClose = tooltip?.prevClose ?? (item?.open ?? 1);

  return (
    <div style={{ marginBottom: 16, position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>{stockName} - {showIntraday ? "分时图" : "K线图"}</h3>
        <select
          value={klt}
          onChange={(e) => onPeriodChange(e.target.value)}
          style={dropdownStyle}
        >
          {Object.entries(PERIODS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <span style={btnStyle(showIntraday, "#1677ff")} onClick={() => { setShowIntraday(!showIntraday); }}>今日分时</span>
          {!showIntraday && (
            <>
              <span style={{ color: "#ddd", fontSize: 11, lineHeight: "22px" }}>|</span>
              <span style={btnStyle(vis.ma, MA_COLORS[2])} onClick={() => toggle("ma")}>MA</span>
              <span style={btnStyle(vis.boll, BOLL_COLORS.upper)} onClick={() => toggle("boll")}>BOLL</span>
              <span style={btnStyle(vis.volume, "#9e9e9e")} onClick={() => toggle("volume")}>量</span>
              <span style={{ color: "#ddd", fontSize: 11, lineHeight: "22px" }}>|</span>
              <span style={btnStyle(vis.macd, MACD_COLORS.dif)} onClick={() => toggle("macd")}>MACD</span>
              <span style={btnStyle(vis.rsi, RSI_COLORS[0])} onClick={() => toggle("rsi")}>RSI</span>
            </>
          )}
        </div>
      </div>

      {showIntraday ? (
        <div style={{ borderRadius: 8, overflow: "hidden", border: "1px solid #f0f0f0" }}>
          {todayIntraday?.loading ? (
            <div style={{ height: 400, display: "flex", alignItems: "center", justifyContent: "center", color: "#bbb" }}>加载中...</div>
          ) : todayIntraday?.error ? (
            <div style={{ height: 100, display: "flex", alignItems: "center", justifyContent: "center", color: "#bbb" }}>{todayIntraday.error}</div>
          ) : todayIntraday?.bars && todayIntraday.bars.length > 0 ? (
            <>
              {todayIntraday.fallback_date && (
                <div style={{ padding: "4px 12px", background: "#fff7e6", borderBottom: "1px solid #ffd591", fontSize: 12, color: "#ad6800", textAlign: "center" }}>
                  今日休市，显示最近交易日 <b>{todayIntraday.fallback_date}</b> 分时图
                </div>
              )}
              <IntradayLineChart bars={todayIntraday.bars} prevClose={prevCloseProp ?? 0} isDark={isDark} />
            </>
          ) : (
            <div style={{ height: 100, display: "flex", alignItems: "center", justifyContent: "center", color: "#bbb" }}>暂无数据</div>
          )}
        </div>
      ) : (
        <div style={{ borderRadius: 8, overflow: "hidden", border: "1px solid #f0f0f0", position: "relative" }}>
          <div ref={mainRef} style={{ minHeight: mainH }} />
          <div ref={macdRef} style={{ height: vis.macd ? subH : 0, overflow: "hidden" }} />
          <div ref={rsiRef} style={{ height: vis.rsi ? subH : 0, overflow: "hidden" }} />
        </div>
      )}

      {tooltip && item && (
        <div style={{
          position: "absolute", left: tooltip.x, top: Math.max(tooltip.y - 90, 10),
          background: bgColor, border: `1px solid ${isDark ? "#444" : "#e0e0e0"}`, borderRadius: 8,
          padding: "10px 14px", boxShadow: "0 4px 16px rgba(0,0,0,0.1)",
          fontSize: 12, lineHeight: "20px", zIndex: 100, minWidth: 160,
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
            <span style={{ fontWeight: 600, fontSize: 13, color: "#333" }}>
              {item.date.length > 10 ? item.date : item.date}
            </span>
            <span
              onClick={() => { setTooltip(null); setIntraday(null); }}
              style={{ cursor: "pointer", fontSize: 16, color: "#aaa", lineHeight: 1, paddingLeft: 8 }}
              title="关闭"
            >x</span>
          </div>
          <div>开盘: <b>{item.open.toFixed(2)}</b></div>
          <div>最高: <b style={{ color: "#ef4444" }}>{item.high.toFixed(2)}</b></div>
          <div>最低: <b style={{ color: "#22c55e" }}>{item.low.toFixed(2)}</b></div>
          <div>收盘: <b>{item.close.toFixed(2)}</b></div>
          <div>涨幅: <b style={{ color: changePct >= 0 ? "#ef4444" : "#22c55e" }}>{changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%</b></div>
          <div>成交量: <b>{(item.volume / 10000).toFixed(0)}万手</b></div>
          <div>成交额: <b>{(item.amount / 1e8).toFixed(2)}亿</b></div>
        </div>
      )}

      {intraday && (
        <div style={{
          marginTop: 12, padding: "12px 16px",
          background: bgColor, borderRadius: 8,
          border: "1px solid #e8e8e8", boxShadow: "0 2px 12px rgba(0,0,0,0.06)",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 600 }}>
              {stockName} · {intraday.date} 分时图
              {intraday.synthetic && <span style={{ fontSize: 10, color: "#faad14", marginLeft: 8, fontWeight: 400 }}>（由日线合成）</span>}
            </span>
            <span onClick={() => setIntraday(null)} style={{ cursor: "pointer", fontSize: 18, color: "#aaa", lineHeight: 1 }}>×</span>
          </div>
          {intraday.loading ? (
            <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: "#bbb" }}>加载中...</div>
          ) : intraday.error ? (
            <div style={{ height: 100, display: "flex", alignItems: "center", justifyContent: "center", color: "#bbb", fontSize: 13 }}>
              {intraday.error}
            </div>
          ) : intraday.bars.length > 0 ? (
            <IntradayLineChart bars={intraday.bars} prevClose={prevClose} isDark={isDark} />
          ) : (
            <div style={{ height: 100, display: "flex", alignItems: "center", justifyContent: "center", color: "#bbb" }}>暂无数据</div>
          )}
        </div>
      )}
    </div>
  );
}

function IntradayLineChart({ bars, prevClose, isDark }: { bars: IntradayBar[]; prevClose: number; isDark?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);

  const bgColor = isDark ? "#1a1a1a" : "#ffffff";
  const textColor = isDark ? "#d9d9d9" : "#333333";

  useEffect(() => {
    if (!ref.current || bars.length === 0) return;
    try {
    const chart = createChart(ref.current, {
      layout: { background: { type: ColorType.Solid, color: bgColor }, textColor },
      width: ref.current.clientWidth, height: 260,
      grid: { vertLines: { visible: false }, horzLines: { color: "#f0f0f0" } },
      crosshair: { mode: CrosshairMode.Normal },
      timeScale: { borderColor: "#e8e8e8", timeVisible: true, barSpacing: bars.length > 50 ? 2 : 4 },
      rightPriceScale: { borderColor: "#e8e8e8" },
    });

    // Convert "YYYY-MM-DD HH:MM" string to Unix timestamp (seconds) for lightweight-charts intraday
    const toTimestamp = (t: string) => {
      const [date, time] = t.split(" ");
      const [y, m, d] = date.split("-").map(Number);
      const [hh, mm] = time.split(":").map(Number);
      return Date.UTC(y, m - 1, d, hh, mm, 0) / 1000;
    };
    const priceData = bars.map((b: IntradayBar) => ({ time: toTimestamp(b.time) as Time, value: b.price }));
    const areaSeries = chart.addAreaSeries({
      lineColor: "#1677ff", topColor: "rgba(22,119,255,0.2)", bottomColor: "rgba(22,119,255,0.02)",
      lineWidth: 2, priceLineVisible: false, lastValueVisible: true,
    });
    areaSeries.setData(priceData);

    if (prevClose > 0) {
      const refLine = chart.addLineSeries({
        color: "#ffa726", lineWidth: 1, lineStyle: LineStyle.Dashed,
        priceLineVisible: false, lastValueVisible: false,
      });
      refLine.setData([
        { time: toTimestamp(bars[0].time) as Time, value: prevClose },
        { time: toTimestamp(bars[bars.length - 1].time) as Time, value: prevClose },
      ]);
    }

    const volSeries = chart.addHistogramSeries({
      color: "rgba(22,119,255,0.12)", priceFormat: { type: "volume" }, priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.9, bottom: 0 } });
    volSeries.setData(bars.map((b: IntradayBar) => ({
      time: toTimestamp(b.time) as Time, value: b.volume,
      color: b.price >= (prevClose || 0) ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)",
    })));

    chart.timeScale().fitContent();
    const ro = new ResizeObserver(() => {
      const el = ref.current; if (el) requestAnimationFrame(() => chart.applyOptions({ width: el.clientWidth }));
    });
    if (ref.current) ro.observe(ref.current);
    return () => { ro.disconnect(); chart.remove(); };
    } catch (err) { console.error("IntradayLineChart error:", err); }
  }, [bars, prevClose]);

  return <div ref={ref} style={{ width: "100%", minHeight: 260, borderRadius: 8, overflow: "hidden" }} />;
}
