import { useNavigate, useLocation } from "react-router-dom";
import {
  RobotOutlined, LineChartOutlined, StarOutlined,
  DollarOutlined, WalletOutlined, ReadOutlined,
} from "@ant-design/icons";

const items = [
  { key: "home", label: "AI 对话", path: "/home", icon: <RobotOutlined /> },
  { key: "market", label: "行情", path: "/market", icon: <LineChartOutlined /> },
  { key: "watchlist", label: "自选", path: "/watchlist", icon: <StarOutlined /> },
  { key: "funds", label: "基金", path: "/funds", icon: <DollarOutlined /> },
  { key: "holdings", label: "持有", path: "/holdings", icon: <WalletOutlined /> },
  { key: "news", label: "新闻", path: "/news", icon: <ReadOutlined /> },
];

/** Left module navigation rail (icon + label), replaces the old bottom nav. */
export default function ModuleNav() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <nav className="glass-panel module-nav">
      {items.map((it) => {
        const active = location.pathname.startsWith(it.path);
        return (
          <div
            key={it.key}
            className={"module-nav-item" + (active ? " active" : "")}
            onClick={() => navigate(it.path)}
          >
            <span className="module-nav-icon">{it.icon}</span>
            <span className="module-nav-label">{it.label}</span>
          </div>
        );
      })}
    </nav>
  );
}
