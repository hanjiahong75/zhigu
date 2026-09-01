import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { ConfigProvider, theme, Layout, Typography, Badge, App as AntApp, Button, Dropdown } from "antd";
import { UserOutlined, SettingOutlined } from "@ant-design/icons";
import zhCN from "antd/locale/zh_CN";
import MarketBar from "./components/MarketBar";
import BottomNav from "./components/BottomNav";
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

/* Pages that show the shared search bar */
const SEARCH_PAGES = ["/news", "/market", "/watchlist", "/funds", "/holdings"];

function AppLayout() {
  const { user, logout } = useAuth();
  const { isDark } = useTheme();
  const { setInput, searchRefresh } = useChat();
  const navigate = useNavigate();
  const location = useLocation();
  const [alerts, setAlerts] = useState<string[]>([]);
  const [detailStock, setDetailStock] = useState<{ code: string; name: string; market: string } | null>(null);

  const showSearch = SEARCH_PAGES.some((p) => location.pathname.startsWith(p));

  useEffect(() => {
    const poll = async () => {
      try {
        const items = await getWatchlist();
        if (items.length === 0) return;
        const quotes = await getWatchlistQuotes(items.map((i: { code: string }) => i.code));
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
  }, [searchRefresh]);

  useEffect(() => {
    if (alerts.length === 0) return;
    const t = setTimeout(() => setAlerts([]), 10000);
    return () => clearTimeout(t);
  }, [alerts]);

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
          <Badge count={alerts.length} size="small" style={{ marginRight: 16 }}>
            <span style={{ color: "#ef4444", fontSize: 12, cursor: "pointer" }}
              title={alerts.join("\n")}>异动预警</span>
          </Badge>
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

          {/* Bottom nav */}
          <BottomNav />
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
