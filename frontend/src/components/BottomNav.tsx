import { useNavigate, useLocation } from "react-router-dom";
import {
  LineChartOutlined, StarOutlined, WalletOutlined,
  ReadOutlined, DollarOutlined,
} from "@ant-design/icons";

const tabs = [
  { key: "news", label: "新闻", icon: <ReadOutlined />, path: "/news" },
  { key: "market", label: "行情", icon: <LineChartOutlined />, path: "/market" },
  { key: "watchlist", label: "自选", icon: <StarOutlined />, path: "/watchlist" },
  { key: "funds", label: "基金", icon: <DollarOutlined />, path: "/funds" },
  { key: "holdings", label: "持有", icon: <WalletOutlined />, path: "/holdings" },
];

export default function BottomNav() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div style={{
      display: "flex", height: 52, flexShrink: 0,
      borderTop: "1px solid var(--border-color)",
      background: "var(--bg-secondary)",
    }}>
      {tabs.map((tab) => {
        const active = location.pathname.startsWith(tab.path);
        return (
          <div
            key={tab.key}
            onClick={() => navigate(tab.path)}
            style={{
              flex: 1, display: "flex", flexDirection: "column",
              alignItems: "center", justifyContent: "center",
              cursor: "pointer", gap: 2, userSelect: "none",
              color: active ? "#1677ff" : "var(--text-muted)",
              background: active ? "var(--thread-active-bg)" : "transparent",
              borderTop: active ? "2px solid #1677ff" : "2px solid transparent",
              transition: "all 0.15s ease",
            }}
          >
            <span style={{ fontSize: 16 }}>{tab.icon}</span>
            <span style={{ fontSize: 10, fontWeight: active ? 600 : 400 }}>{tab.label}</span>
          </div>
        );
      })}
    </div>
  );
}
