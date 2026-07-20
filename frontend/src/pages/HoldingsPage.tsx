import { Button, Typography } from "antd";
import { RobotOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import PortfolioPanel from "../components/PortfolioPanel";

const { Text } = Typography;

export default function HoldingsPage() {
  const navigate = useNavigate();

  return (
    <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ flex: 1, overflow: "auto", padding: "8px 0" }}>
        <PortfolioPanel />
      </div>
      <div style={{
        padding: "10px 24px", borderTop: "1px solid var(--border-color)",
        background: "var(--bg-secondary)", flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <Text style={{ fontSize: 12, color: "var(--text-muted)" }}>
          截图导入或管理你的基金持仓
        </Text>
        <Button type="primary" size="small" icon={<RobotOutlined />} onClick={() => navigate("/home")}>
          AI 投研提问
        </Button>
      </div>
    </div>
  );
}