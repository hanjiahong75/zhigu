import { useState, useEffect } from "react";
import { useRef } from "react";
import { useNavigate } from "react-router-dom";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { ConfigProvider, theme, Layout, Typography, Badge, App as AntApp, Button, Dropdown, Popover, Segmented, Switch } from "antd";
import { UserOutlined, SettingOutlined } from "@ant-design/icons";
import zhCN from "antd/locale/zh_CN";
import MarketBar from "./components/MarketBar";
import ModuleNav from "./components/ModuleNav";
import StockDetailModal from "./components/StockDetailModal";
import StockSearch from "./components/StockSearch";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/HomePage";
import RegisterPage from "./pages/RegisterPage";
import SettingsPage from "./pages/SettingsPage";
import NewsPage from "./pages/NewsPage";
import MarketPage from "./pages/MarketPage";
import WatchlistPage from "./pages/WatchlistPage";
import FundPage from "./pages/FundPage";
import HoldingsPage from "./pages/HoldingsPage";
import { AuthProvider, useAuth } from "./api/auth";
import { ThemeProvider, useTheme } from "./api/ThemeContext";
import { ChatProvider, useChat } from "./api/ChatContext";
import type { StockQuote } from "./types";
import { getWatchlist, getWatchlistQuotes } from "./api/client";
import "./animations.css";

const { Header, Content } = Layout;
const { Title } = Typography;
const ALERT_THRESHOLD = 3;
const ALERT_COOLDOWN_MS = 30 * 60 * 1000;
const ALERT_ESCALATE_PP = 3;
const ALERT_MAX = 50;
const INDEX_CODES = new Set(["000001", "000300", "000016", "000688", "399001", "399006"]);

interface AlertItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  ts: number;
}

/* Pages that show the shared search bar */
const SEARCH_PAGES = ["/news", "/market", "/watchlist", "/funds", "/holdings"];

function AppLayout() {
  const { user, logout } = useAuth();
  const { isDark } = useTheme();
  const { setInput, searchRefresh } = useChat();
  const navigate = useNavigate();
  const location = useLocation();
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [alertOpen, setAlertOpen] = useState(false);
  const [alertThreshold, setAlertThreshold] = useState<number>(() => Number(localStorage.getItem("zhigu_alert_threshold")) || ALERT_THRESHOLD);
  const [includeIndex, setIncludeIndex] = useState<boolean>(() => localStorage.getItem("zhigu_alert_index") === "1");
  const lastReportRef = useRef<Map<string, { abs: number; up: boolean; ts: number }>>(new Map());
  const [detailStock, setDetailStock] = useState<{ code: string; name: string; market: string } | null>(null);

  const showSearch = SEARCH_PAGES.some((p) => location.pathname.startsWith(p));

  useEffect(() => {
    const poll = async () => {
      try {
        const items = await getWatchlist();
        if (items.length === 0) return;
        const quotes = await getWatchlistQuotes(items.map((i: { code: string }) => i.code));
        const now = Date.now();
        const added: AlertItem[] = [];
        quotes.forEach((q: StockQuote) => {
          const code = q.code;
          const isIndex = INDEX_CODES.has(code) || code.includes(".");
          if (isIndex && !includeIndex) return;
          const abs = Math.abs(q.change_pct || 0);
          if (abs < alertThreshold) return;
          const prev = lastReportRef.current.get(code);
          const up = (q.change_pct || 0) > 0;
          const escalated = !!prev && abs - prev.abs >= ALERT_ESCALATE_PP;
          const reversed = !!prev && up !== prev.up;
          const cooled = !!prev && (now - prev.ts < ALERT_COOLDOWN_MS) && !escalated && !reversed;
          if (cooled) return;
          lastReportRef.current.set(code, { abs, up, ts: now });
          added.push({ code, name: q.name, price: q.price || 0, change_pct: q.change_pct || 0, ts: now });
        });
        if (added.length > 0) setAlerts((prevList) => [...added, ...prevList].slice(0, ALERT_MAX));
      } catch { /* silent */ }
    };
    poll();
    const timer = setInterval(poll, 30000);
    return () => clearInterval(timer);
  }, [searchRefresh, alertThreshold, includeIndex]);

  const userMenuItems = [
    { key: "settings", icon: <SettingOutlined />, label: "设置" },
    { key: "logout", icon: <SettingOutlined />, label: "退出登录", danger: true },
  ];

  const handleUserMenu = ({ key }: { key: string }) => {
    if (key === "logout") logout();
    else navigate("/settings");
  };

  const handleSearchSelect = (code: string, name: string, market: string) => {
    setDetailStock({ code, name, market });
  };

  const handleAskAI = (code: string, name: string) => {
    setInput(name + "(" + code + ") 怎么样？");
    navigate("/home");
  };

  const handleSelectIndex = (code: string, name: string, market: string) => {
    // Use provided market from global indices, or infer from A-share codes
    const mkt = market || (code.startsWith("3") ? "sz" : "sh");
    setDetailStock({ code, name, market: mkt });
  };

  const openAlertStock = (a: AlertItem) => {
    const market = a.code.includes(".") ? "us" : (a.code.startsWith("6") || a.code.startsWith("9") ? "sh" : "sz");
    setDetailStock({ code: a.code, name: a.name, market });
    setAlertOpen(false);
  };

  const changeAlertThreshold = (v: number | string) => {
    setAlertThreshold(Number(v));
    localStorage.setItem("zhigu_alert_threshold", String(v));
  };

  const changeIncludeIndex = (v: boolean) => {
    setIncludeIndex(v);
    localStorage.setItem("zhigu_alert_index", v ? "1" : "0");
  };

  const alertContent = (
    <div style={{ width: 340 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>异动详情</span>
        <Segmented
          size="small"
          value={alertThreshold}
          onChange={changeAlertThreshold}
          options={[{ label: "3%", value: 3 }, { label: "5%", value: 5 }, { label: "8%", value: 8 }]}
        />
      </div>
      <div style={{ marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
        <Switch size="small" checked={includeIndex} onChange={changeIncludeIndex} />
        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>含指数（上证/恒生等）</span>
      </div>
      {alerts.length === 0 ? (
        <div style={{ color: "var(--text-muted)", fontSize: 12, padding: "8px 0" }}>暂无预警</div>
      ) : (
        <div style={{ maxHeight: 260, overflow: "auto" }}>
          {alerts.map((a, i) => (
            <div
              key={i}
              onClick={() => openAlertStock(a)}
              style={{
                padding: "8px 6px", borderBottom: "1px solid var(--border-color)", cursor: "pointer",
                display: "flex", justifyContent: "space-between", alignItems: "center",
              }}
            >
              <span style={{ fontSize: 12 }}>{a.name} <span style={{ color: "var(--text-muted)" }}>{a.code}</span></span>
              <span style={{ fontSize: 12, color: a.change_pct >= 0 ? "#ef4444" : "#22c55e" }}>
                {a.change_pct >= 0 ? "+" : ""}{a.change_pct.toFixed(2)}% · {a.price.toFixed(2)} ·{" "}
                {new Date(a.ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          ))}
        </div>
      )}
      <div style={{ marginTop: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>共 {alerts.length} 条 · 同股30分钟冷却</span>
        <Button size="small" type="text" onClick={() => setAlerts([])}>清空</Button>
      </div>
    </div>
  );


  return (
    <Layout style={{ height: "100vh", overflow: "hidden", background: "var(--bg-primary)" }}>
      <Header className="glass-nav" style={{
        display: "flex", alignItems: "center", padding: "0 24px", height: 56,
      }}>
        <Title level={4} style={{ margin: 0, cursor: "pointer", color: "var(--text-primary)" }}
          onClick={() => navigate("/home")}>知股</Title>
        <span style={{ marginLeft: 8, color: "var(--text-muted)", fontSize: 13 }}>AI投研助手</span>
        <div style={{ flex: 1 }} />
        {alerts.length > 0 && (
          <Popover content={alertContent} trigger="click" open={alertOpen} onOpenChange={setAlertOpen} placement="bottomRight">
            <Badge count={alerts.length} size="small" style={{ marginRight: 16 }}>
              <span style={{ color: "#ef4444", fontSize: 12, cursor: "pointer" }}>异动预警</span>
            </Badge>
          </Popover>
        )}
        <MarketBar />
        <div style={{ width: 8 }} />
        <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenu }} placement="bottomRight">
          <Button type="text" icon={<UserOutlined />} style={{ marginLeft: 8 }}>
            {user?.nickname || user?.username || "用户"}
          </Button>
        </Dropdown>
      </Header>

      <Content style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
        <div className="bg-aurora" aria-hidden="true">
          <div className="auth-blob auth-blob-1" />
          <div className="auth-blob auth-blob-2" />
          <div className="auth-blob auth-blob-3" />
        </div>
        {/* Left module navigation */}
        <ModuleNav />
        {/* Content area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden", position: "relative", zIndex: 1 }}>
          {/* Top bar: shared search (all pages except holdings) */}
          {showSearch && (
            <div className="glass-nav" style={{
              padding: "10px 24px", flexShrink: 0,
            }}>
              <StockSearch
                onSelect={handleSearchSelect}
                onWatchlistChange={() => {}}
              />
            </div>
          )}

          {/* Page content area (flex: 1, overflow auto) — animated on route change */}
          <div
            key={location.pathname}
            className="apple-fade-in"
            style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}
          >
            <Routes location={location}>
              <Route path="/home" element={<HomePage />} />
              <Route path="/news" element={<NewsPage />} />
              <Route path="/market" element={<MarketPage onSelectIndex={handleSelectIndex} />} />
              <Route path="/watchlist" element={<WatchlistPage onSelectStock={handleSearchSelect} />} />
              <Route path="/funds" element={<FundPage />} />
              <Route path="/holdings" element={<HoldingsPage />} />
              <Route path="*" element={<Navigate to="/home" replace />} />
            </Routes>
          </div>

          <StockDetailModal
            open={!!detailStock}
            stockCode={detailStock?.code || ""}
            stockName={detailStock?.name || ""}
            market={detailStock?.market || "sz"}
            onClose={() => setDetailStock(null)}
            onAskAI={handleAskAI}
          />
        </div>
      </Content>
    </Layout>
  );
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/settings" element={<RequireAuth><SettingsPage /></RequireAuth>} />
      <Route path="/*" element={<RequireAuth><AppLayout /></RequireAuth>} />
    </Routes>
  );
}

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div style={{ minHeight: "100vh", background: "var(--bg-primary)" }} />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function ThemedApp() {
  const { isDark } = useTheme();
  return (
    <ConfigProvider
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: { colorPrimary: "#1677ff", borderRadius: 8 },
      }}
      locale={zhCN}
    >
      <AntApp>
        <ChatProvider>
          <AppRoutes />
        </ChatProvider>
      </AntApp>
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <BrowserRouter>
          <ThemedApp />
        </BrowserRouter>
      </ThemeProvider>
    </AuthProvider>
  );
}
