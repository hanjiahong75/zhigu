import { useState, useEffect } from "react";
import { Card, Statistic, Spin, Button, Tag, Typography } from "antd";
import { WalletOutlined, UpOutlined, DownOutlined, PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { getPortfolio, getPortfolioRisk, getPortfolioDiagnosis } from "../api/client";
import type { Portfolio, PortfolioItem, DiagnosisData } from "../types";

const { Text } = Typography;

interface RiskData {
  sharpe_ratio: number | null;
  max_drawdown: number | null;
  message: string | null;
}

const SIGNAL_MAP: Record<string, { color: string; label: string; icon: string }> = {
  green:  { color: "#52c41a", label: "健康", icon: "🟢" },
  yellow: { color: "#faad14", label: "观察", icon: "🟡" },
  red:    { color: "#ff4d4f", label: "关注", icon: "🔴" },
  grey:   { color: "#d9d9d9", label: "不足", icon: "⚪" },
};

export default function PortfolioOverviewCard() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [risk, setRisk] = useState<RiskData | null>(null);
  const [diagnosis, setDiagnosis] = useState<DiagnosisData | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();

  useEffect(() => { loadData(); }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const p = await getPortfolio();
      setPortfolio(p);
      if (p?.items?.length > 0) {
        const [r, d] = await Promise.all([
          getPortfolioRisk().catch(() => null),
          getPortfolioDiagnosis().catch(() => null),
        ]);
        setRisk(r);
        setDiagnosis(d);
      }
    } catch { /* silent */ }
    setLoading(false);
  };

  if (loading) return null;

  const hasHoldings = portfolio && portfolio.items && portfolio.items.length > 0;
  const totalHoldingAmount = hasHoldings ? portfolio!.items.reduce((s: number, i: PortfolioItem) => s + (i.holding_amount || 0), 0) : 0;
  const totalHoldingReturn = hasHoldings ? portfolio!.items.reduce((s: number, i: PortfolioItem) => s + (i.holding_return || 0), 0) : 0;
  const totalCostAmount = hasHoldings ? portfolio!.items.reduce((s: number, i: PortfolioItem) => s + (i.cost_amount || 0), 0) : 0;
  const totalReturnRate = totalCostAmount > 0 ? (totalHoldingReturn / totalCostAmount * 100) : 0;

  if (!hasHoldings) {
    return (
      <div style={{ padding: "16px 20px", margin: "0 16px 8px", borderRadius: 12, background: "var(--bg-secondary)", border: "1px solid var(--border-color)" }} className="card-hover">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 40, height: 40, borderRadius: "50%", background: "var(--bg-sidebar)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <WalletOutlined style={{ fontSize: 18, color: "var(--text-muted)" }} />
            </div>
            <div>
              <Text strong style={{ fontSize: 14, color: "var(--text-primary)" }}>我的持仓</Text>
              <Text style={{ fontSize: 12, color: "var(--text-muted)", display: "block" }}>截图导入你的基金持仓，开启投研之旅</Text>
            </div>
          </div>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => navigate("/holdings")}>添加持仓</Button>
        </div>
      </div>
    );
  }

  const signalCounts: Record<string, number> = { green: 0, yellow: 0, red: 0, grey: 0 };
  diagnosis?.items?.forEach((d) => {
    if (signalCounts[d.signal] !== undefined) signalCounts[d.signal]++;
  });

  const profitColor = totalHoldingReturn >= 0 ? "#cf1322" : "#3f8600";

  return (
    <div style={{ padding: "0 16px 4px" }}>
      <Card className="card-hover" size="small" style={{ borderRadius: 12, border: "1px solid var(--border-color)", background: "var(--bg-secondary)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }} onClick={() => setCollapsed(!collapsed)}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <WalletOutlined style={{ color: "#1677ff", fontSize: 16 }} />
            <Text strong style={{ fontSize: 14, color: "var(--text-primary)" }}>我的持仓</Text>
            <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>{portfolio!.items.length} 只基金</Text>
            <div style={{ display: "flex", gap: 4, marginLeft: 4 }}>
              {signalCounts.green > 0 && <Tag color={SIGNAL_MAP.green.color} style={{ fontSize: 10, margin: 0, padding: "0 5px", lineHeight: "18px" }}>{signalCounts.green}</Tag>}
              {signalCounts.yellow > 0 && <Tag color={SIGNAL_MAP.yellow.color} style={{ fontSize: 10, margin: 0, padding: "0 5px", lineHeight: "18px" }}>{signalCounts.yellow}</Tag>}
              {signalCounts.red > 0 && <Tag color={SIGNAL_MAP.red.color} style={{ fontSize: 10, margin: 0, padding: "0 5px", lineHeight: "18px" }}>{signalCounts.red}</Tag>}
            </div>
          </div>
          {collapsed ? <DownOutlined style={{ fontSize: 10, color: "var(--text-muted)" }} /> : <UpOutlined style={{ fontSize: 10, color: "var(--text-muted)" }} />}
        </div>
        {!collapsed && (
          <div style={{ marginTop: 10 }}>
            <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 4 }}>
              <Statistic title="持有金额" value={totalHoldingAmount} precision={0} suffix="元" valueStyle={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)" }} />
              <Statistic title="累计收益" value={totalHoldingReturn} precision={0} suffix="元" valueStyle={{ fontSize: 14, color: profitColor }} />
              <Statistic title="收益率" value={totalReturnRate} precision={2} suffix="%" valueStyle={{ fontSize: 14, color: profitColor }} />
            </div>
            <div style={{ marginTop: 8, textAlign: "right" }}>
              <Button size="small" type="link" onClick={() => navigate("/holdings")}>管理持仓 →</Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}