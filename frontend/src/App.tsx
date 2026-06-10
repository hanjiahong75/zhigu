import { useState, useEffect } from "react";
import { ConfigProvider, theme, Layout, Typography, Badge, App as AntApp } from "antd";
import zhCN from "antd/locale/zh_CN";
import ChatPanel from "./components/ChatPanel";
import MarketBar from "./components/MarketBar";
import type { WatchlistItem, StockQuote } from "./types";
import { getWatchlist, getWatchlistQuotes } from "./api/client";

const { Header, Content } = Layout;
const { Title } = Typography;

const ALERT_THRESHOLD = 3;

function App() {
  const [alerts, setAlerts] = useState<string[]>([]);
  const [watchlistRefresh, setWatchlistRefresh] = useState(0);

  useEffect(() => {
    const poll = async () => {
      try {
        const items = await getWatchlist();
        if (items.length === 0) return;
        const codes = items.map((i: WatchlistItem) => i.code);
        const quotes = await getWatchlistQuotes(codes);
        const newAlerts: string[] = [];
        quotes.forEach((q: StockQuote) => {
          if (Math.abs(q.change_pct) >= ALERT_THRESHOLD) {
            const dir = q.change_pct > 0 ? "涨" : "跌";
            newAlerts.push(`${q.name}(${q.code}) ${dir}${Math.abs(q.change_pct)}%`);
          }
        });
        if (newAlerts.length > 0) setAlerts(newAlerts);
      } catch { /* silent */ }
    };
    poll();
    const timer = setInterval(poll, 30000);
    return () => clearInterval(timer);
  }, [watchlistRefresh]);

  useEffect(() => {
    if (alerts.length === 0) return;
    const t = setTimeout(() => setAlerts([]), 10000);
    return () => clearTimeout(t);
  }, [alerts]);

  return (
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: { colorPrimary: "#1677ff", borderRadius: 8 },
      }}
      locale={zhCN}
    >
      <AntApp>
        <Layout style={{ minHeight: "100vh" }}>
          <Header
            style={{
              background: "#fff", borderBottom: "1px solid #f0f0f0",
              display: "flex", alignItems: "center", padding: "0 24px", height: 56,
            }}
          >
            <Title level={4} style={{ margin: 0 }}>知股</Title>
            <span style={{ marginLeft: 8, color: "#888", fontSize: 13 }}>AI投研助手</span>
            <div style={{ flex: 1 }} />
            {alerts.length > 0 && (
              <Badge count={alerts.length} size="small" style={{ marginRight: 16 }}>
                <span style={{ color: "#ef4444", fontSize: 12, cursor: "pointer" }} title={alerts.join("\n")}>
                  异动告警
                </span>
              </Badge>
            )}
            <MarketBar />
          </Header>
          <Content style={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column", flex: 1 }}>
            <ChatPanel />
          </Content>
        </Layout>
      </AntApp>
    </ConfigProvider>
  );
}

export default App;