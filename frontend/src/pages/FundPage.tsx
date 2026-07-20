import { useState, useRef, useEffect, useCallback } from "react";
import { Modal, Typography, Tag, Spin, Empty, message } from "antd";
import { SearchOutlined, FundOutlined, PlusOutlined, CheckOutlined, ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import { createChart, ColorType } from "lightweight-charts";
import { searchFunds, getFundNav, getFundRecommendations, getFundHoldings, addToWatchlist, getWatchlist, removeFromWatchlist } from "../api/client";
import { useTheme } from "../api/ThemeContext";

const { Text } = Typography;

const CATEGORIES = [
  { key: "hot", label: "热门榜单", icon: "🔥" },
  { key: "bond", label: "债券基金", icon: "📊" },
  { key: "index", label: "指数基金", icon: "📈" },
  { key: "qdii", label: "海外基金", icon: "🌍" },
  { key: "commodity", label: "黄金石油", icon: "🛢️" },
] as const;

const PERIODS = [
  { key: "近1月", days: 22, label: "1月" },
  { key: "近3月", days: 66, label: "3月" },
  { key: "近6月", days: 132, label: "6月" },
  { key: "近1年", days: 252, label: "1年" },
  { key: "近2年", days: 504, label: "2年" },
  { key: "近5年", days: 1260, label: "5年" },
  { key: "成立以来", days: -1, label: "全部" },
];

interface FundSearchItem {
  code: string; name: string; pinyin: string; pinyin_short: string; fund_type: string;
}
interface FundCard {
  code: string; name: string; nav: number | null; daily_return: number | null;
  return_1m: number | null; return_1y: number | null;
}
interface FundDetail {
  code: string; name: string; fund_type: string; company: string; setup_date: string;
  manager: string; nav: number; daily_return: number | null; nav_date: string;
  period_returns: Record<string, number | null>;
  nav_history: Array<{ date: string; nav: number; daily_return: number | null }>;
}

export default function FundPage() {
  const { isDark } = useTheme();
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<FundSearchItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [recommendations, setRecommendations] = useState<Record<string, FundCard[]>>({});
  const [recLoading, setRecLoading] = useState(true);
  const [detail, setDetail] = useState<FundDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [chartPeriod, setChartPeriod] = useState("近1年");
  const [inWatchlist, setInWatchlist] = useState(false);
  const [holdings, setHoldings] = useState<{ quarter: string; stocks: Array<{ code: string; name: string; pct: number }>; industries: Array<{ name: string; pct: number }> } | null>(null);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<ReturnType<typeof createChart> | undefined>(undefined);
  const scrollRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const scrollAnimRef = useRef<Record<string, number>>({});

  const bgColor = isDark ? "#1a1a1a" : "#f5f5f5";
  const textColor = isDark ? "#ccc" : "#333";
  const gridColor = isDark ? "#2a2a2a" : "#e0e0e0";

  // Load recommendations on mount
  useEffect(() => {
    getFundRecommendations()
      .then(setRecommendations)
      .catch(() => {})
      .finally(() => setRecLoading(false));
  }, []);

  // Search
  const doSearch = useCallback((kw: string) => {
    if (!kw.trim()) { setResults([]); return; }
    setSearching(true);
    searchFunds(kw).then(setResults).catch(() => setResults([])).finally(() => setSearching(false));
  }, []);

  const handleInput = (val: string) => {
    setKeyword(val);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => doSearch(val), 300);
  };

  // Detail modal
  const openDetail = async (fund: FundSearchItem | FundCard) => {
    setDetailLoading(true);
    setModalOpen(true);
    try {
      const data = await getFundNav(fund.code);
      setDetail(data);
      getFundHoldings(fund.code).then(setHoldings).catch(() => setHoldings(null));
      const wl = await getWatchlist().catch(() => []);
      setInWatchlist(Array.isArray(wl) ? wl.some((i: any) => i.code === fund.code) : false);
    } catch {
      setDetail(null);
    }
    setDetailLoading(false);
  };

  const toggleWatchlist = async () => {
    if (!detail) return;
    try {
      if (inWatchlist) {
        await removeFromWatchlist(detail.code);
        setInWatchlist(false);
        message.success("已取消自选");
      } else {
        await addToWatchlist(detail.code, detail.name, "sz");
        setInWatchlist(true);
        message.success("已加自选");
      }
    } catch {
      message.error("操作失败");
    }
  };

  // Horizontal auto-scroll on hover
  useEffect(() => {
    const animFrames = scrollAnimRef.current;
    return () => { Object.values(animFrames).forEach(cancelAnimationFrame); };
  }, []);

  const startScroll = (key: string) => {
    const el = scrollRefs.current[key];
    if (!el) return;
    const speed = 0.4; // pixels per frame
    const scroll = () => {
      if (el.scrollLeft >= el.scrollWidth - el.clientWidth) {
        el.scrollLeft = 0;
      } else {
        el.scrollLeft += speed;
      }
      scrollAnimRef.current[key] = requestAnimationFrame(scroll);
    };
    scroll();
  };

  const stopScroll = (key: string) => {
    if (scrollAnimRef.current[key]) {
      cancelAnimationFrame(scrollAnimRef.current[key]);
      delete scrollAnimRef.current[key];
    }
  };

  // NAV chart
  useEffect(() => {
    if (!modalOpen || !chartRef.current || !detail?.nav_history?.length) return;
    const container = chartRef.current;
    const chart = createChart(container, {
      layout: { background: { type: ColorType.Solid, color: bgColor }, textColor },
      grid: { vertLines: { color: gridColor }, horzLines: { color: gridColor } },
      width: container.clientWidth, height: 320,
      timeScale: { timeVisible: true },
    });
    chartInstance.current = chart;

    let history = [...detail.nav_history];
    if (chartPeriod !== "成立以来") {
      const periodConf = PERIODS.find((p) => p.key === chartPeriod);
      if (periodConf && periodConf.days > 0) history = history.slice(-periodConf.days);
    }
    const data = history.filter((d) => d.nav != null).map((d) => ({ time: d.date, value: d.nav }));
    const lineSeries = chart.addLineSeries({ color: isDark ? "#4ea1f3" : "#2962FF", lineWidth: 2 });
    lineSeries.setData(data);
    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => { if (container.clientWidth > 0) chart.applyOptions({ width: container.clientWidth }); });
    ro.observe(container);
    return () => { ro.disconnect(); chart.remove(); };
  }, [modalOpen, detail, chartPeriod, isDark, bgColor, textColor, gridColor]);

  const formatPct = (v: number | null | undefined) => {
    if (v == null) return "-";
    return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
  };

  const pctColor = (v: number | null | undefined) => {
    if (v == null) return "var(--text-secondary)";
    if (v > 0) return "#ef4444";
    if (v < 0) return "#22c55e";
    return "var(--text-secondary)";
  };

  const FundCardItem = ({ fund }: { fund: FundCard }) => {
    return (
    <div
      onClick={() => openDetail(fund)}
      style={{
        minWidth: 180, maxWidth: 180, padding: 12, borderRadius: 8,
        background: "var(--bg-secondary)", cursor: "pointer",
        border: "1px solid var(--border-color)", flexShrink: 0,
        transition: "background 0.15s",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "var(--bg-secondary)")}
    >
      <Text strong style={{ fontSize: 13, color: "var(--text-primary)", display: "block", lineHeight: "18px", height: 36, overflow: "hidden" }}>
        {fund.name}
      </Text>
      <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>{fund.code}</Text>
      <div style={{ marginTop: 6, display: "flex", alignItems: "baseline", gap: 6 }}>
        <Text style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
          {fund.nav?.toFixed(4) ?? "-"}
        </Text>
        <Text style={{ fontSize: 12, color: pctColor(fund.daily_return) }}>
          {formatPct(fund.daily_return)}
        </Text>
      </div>
      <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
        <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>近1月</Text>
        <Text style={{ fontSize: 11, color: pctColor(fund.return_1m), fontWeight: 500 }}>
          {formatPct(fund.return_1m)}
        </Text>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>近1年</Text>
        <Text style={{ fontSize: 11, color: pctColor(fund.return_1y), fontWeight: 500 }}>
          {formatPct(fund.return_1y)}
        </Text>
      </div>
    </div>
  );
  };

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      {/* Search Bar */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "10px 16px", borderBottom: "1px solid var(--border-color)",
      }}>
        <SearchOutlined style={{ color: "var(--text-muted)", fontSize: 16 }} />
        <input
          type="text" placeholder="搜索基金代码、名称或拼音..."
          value={keyword}
          onChange={(e) => handleInput(e.target.value)}
          style={{ flex: 1, border: "none", outline: "none", fontSize: 14, background: "transparent", color: "var(--text-primary)" }}
        />
      </div>

      {/* Content: search results or recommendations */}
      <div style={{ flex: 1, overflow: "auto" }}>
        {keyword ? (
          // Search results
          <>
            {searching ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 40 }}><Spin /></div>
            ) : results.length === 0 ? (
              <Empty description="未找到相关基金" style={{ marginTop: 60 }} />
            ) : (
              results.map((fund) => (
                <div key={fund.code} onClick={() => openDetail(fund)}
                  style={{ padding: "12px 16px", borderBottom: "1px solid var(--border-color)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <FundOutlined style={{ color: "var(--text-muted)", fontSize: 16 }} />
                    <div>
                      <Text strong style={{ fontSize: 14, color: "var(--text-primary)" }}>{fund.name}</Text>
                      <Text style={{ fontSize: 12, color: "var(--text-muted)", marginLeft: 8 }}>{fund.code}</Text>
                    </div>
                  </div>
                  <Tag style={{ fontSize: 10, background: "var(--bg-secondary)", border: "none", color: "var(--text-secondary)" }}>{fund.fund_type}</Tag>
                </div>
              ))
            )}
          </>
        ) : (
          // Recommendations
          <div style={{ padding: "8px 0" }}>
            {recLoading ? (
              <div style={{ display: "flex", justifyContent: "center", padding: 60 }}><Spin size="large" /></div>
            ) : (
              CATEGORIES.map((cat) => {
                const funds = recommendations[cat.key] || [];
                if (!funds.length) return null;
                return (
                  <div key={cat.key} style={{ padding: "4px 0" }}>
                    <div style={{ padding: "8px 16px", display: "flex", alignItems: "center", gap: 6 }}>
                      <Text style={{ fontSize: 12 }}>{cat.icon}</Text>
                      <Text strong style={{ fontSize: 14, color: "var(--text-primary)" }}>{cat.label}</Text>
                    </div>
                    <div
                      ref={(el) => { scrollRefs.current[cat.key] = el; }}
                      onMouseEnter={() => startScroll(cat.key)}
                      onMouseLeave={() => stopScroll(cat.key)}
                      style={{
                        display: "flex", gap: 10, padding: "4px 16px 12px",
                        overflowX: "auto", scrollbarWidth: "none",
                      }}
                    >
                      {funds.map((fund) => (
                        <FundCardItem key={fund.code} fund={fund} />
                      ))}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        )}
      </div>

      {/* Detail Modal */}
      <Modal open={modalOpen} onCancel={() => { setModalOpen(false); setDetail(null); setHoldings(null); }} footer={null} width={720} title={null} styles={{ body: { padding: 0 } }}>
        {detailLoading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: 60 }}><Spin size="large" /></div>
        ) : detail ? (
          <div>
            <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border-color)" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div>
                  <Text strong style={{ fontSize: 18, color: "var(--text-primary)" }}>{detail.name}</Text>
                  <Text style={{ fontSize: 13, color: "var(--text-muted)", marginLeft: 8 }}>{detail.code}</Text>
                </div>
                <div onClick={toggleWatchlist} style={{ cursor: "pointer", color: inWatchlist ? "var(--text-muted)" : "var(--text-primary)" }}>
                  {inWatchlist ? <CheckOutlined /> : <PlusOutlined />}
                  <Text style={{ fontSize: 12, marginLeft: 4, color: "var(--text-secondary)" }}>{inWatchlist ? "已加自选" : "加自选"}</Text>
                </div>
              </div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginTop: 8 }}>
                <Text style={{ fontSize: 24, fontWeight: 700, color: "var(--text-primary)" }}>{detail.nav?.toFixed(4)}</Text>
                <Text style={{ fontSize: 14, color: pctColor(detail.daily_return) }}>
                  {detail.daily_return != null && (detail.daily_return > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />)} {formatPct(detail.daily_return)}
                </Text>
                <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>单位净值 ({detail.nav_date})</Text>
              </div>
              <div style={{ display: "flex", gap: 16, marginTop: 6, flexWrap: "wrap" }}>
                <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>{detail.fund_type}</Text>
                <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>{detail.company}</Text>
                {detail.manager && <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>基金经理: {detail.manager}</Text>}
                {detail.setup_date && <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>成立: {detail.setup_date}</Text>}
              </div>
            </div>
            <div style={{ padding: "12px 20px" }}>
              <Text strong style={{ fontSize: 13, color: "var(--text-primary)" }}>业绩表现</Text>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6, marginTop: 8 }}>
                {PERIODS.map((p) => {
                  const val = detail.period_returns?.[p.key];
                  return (
                    <div key={p.key} style={{ padding: "8px 10px", borderRadius: 6, background: "var(--bg-secondary)", textAlign: "center" }}>
                      <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>{p.key}</Text>
                      <div style={{ fontSize: 15, fontWeight: 600, color: pctColor(val), marginTop: 2 }}>{formatPct(val)}</div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div style={{ padding: "0 20px 12px" }}>
              <div style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
                {PERIODS.map((p) => (
                  <div key={p.key} onClick={() => setChartPeriod(p.key)}
                    style={{
                      padding: "4px 10px", borderRadius: 4, cursor: "pointer", fontSize: 12,
                      background: chartPeriod === p.key ? "var(--bg-hover)" : "transparent",
                      color: chartPeriod === p.key ? "var(--text-primary)" : "var(--text-muted)",
                      fontWeight: chartPeriod === p.key ? 600 : 400,
                      border: `1px solid ${chartPeriod === p.key ? "var(--border-color)" : "transparent"}`,
                    }}
                  >{p.label}</div>
                ))}
              </div>
              <div ref={chartRef} style={{ width: "100%", borderRadius: 6, overflow: "hidden" }} />
            </div>
            {/* Holdings */}
            {holdings && (holdings.stocks.length > 0 || holdings.industries.length > 0) && (
              <div style={{ padding: "12px 20px 16px", borderTop: "1px solid var(--border-color)" }}>
                <Text strong style={{ fontSize: 13, color: "var(--text-primary)" }}>最新持仓分布</Text>
                {holdings.quarter && (
                  <Text style={{ fontSize: 11, color: "var(--text-muted)", marginLeft: 8 }}>{holdings.quarter}</Text>
                )}
                {holdings.stocks.length > 0 && (
                  <>
                    <Text style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginTop: 8, marginBottom: 4 }}>前十大重仓股</Text>
                    {holdings.stocks.map((s, i) => (
                      <div key={s.code} style={{ display: "flex", alignItems: "center", padding: "3px 0", gap: 8 }}>
                        <Text style={{ fontSize: 11, color: "var(--text-muted)", width: 20, textAlign: "right" }}>{i + 1}</Text>
                        <Text style={{ fontSize: 12, color: "var(--text-primary)", flex: 1 }}>{s.name}</Text>
                        <Text style={{ fontSize: 11, color: "var(--text-muted)", width: 60, textAlign: "right" }}>{s.code}</Text>
                        <div style={{ width: 80, height: 6, background: "var(--bg-secondary)", borderRadius: 3, overflow: "hidden" }}>
                          <div style={{ width: `${Math.min(s.pct * 8, 100)}%`, height: "100%", background: "#ef4444", borderRadius: 3 }} />
                        </div>
                        <Text style={{ fontSize: 11, color: "var(--text-secondary)", width: 42, textAlign: "right" }}>{s.pct.toFixed(2)}%</Text>
                      </div>
                    ))}
                  </>
                )}
                {holdings.industries.length > 0 && (
                  <>
                    <Text style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginTop: 12, marginBottom: 4 }}>行业分布</Text>
                    {holdings.industries.slice(0, 6).map((ind) => (
                      <div key={ind.name} style={{ display: "flex", alignItems: "center", padding: "3px 0", gap: 8 }}>
                        <Text style={{ fontSize: 12, color: "var(--text-primary)", flex: 1 }}>{ind.name}</Text>
                        <div style={{ width: 100, height: 6, background: "var(--bg-secondary)", borderRadius: 3, overflow: "hidden" }}>
                          <div style={{ width: `${Math.min(ind.pct * 1.5, 100)}%`, height: "100%", background: "#2962FF", borderRadius: 3 }} />
                        </div>
                        <Text style={{ fontSize: 11, color: "var(--text-secondary)", width: 42, textAlign: "right" }}>{ind.pct.toFixed(2)}%</Text>
                      </div>
                    ))}
                  </>
                )}
              </div>
            )}
          </div>
        ) : (
          <div style={{ padding: 40, textAlign: "center" }}><Text style={{ color: "var(--text-muted)" }}>加载失败，请重试</Text></div>
        )}
      </Modal>
    </div>
  );
}
