import { useState, useEffect } from "react";
import { Typography } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import { getGlobalIndices } from "../api/client";

const { Text } = Typography;

interface IndexItem {
  name: string;
  code: string;
  market: string;
  price: number;
  change_pct: number;
}
interface CountryGroup {
  country: string;
  indices: IndexItem[];
}

interface Props {
  onSelectIndex?: (code: string, name: string, market: string) => void;
}

const FLAGS: Record<string, string> = {
  "中国": "🇨🇳", "港股": "🇭🇰", "美股": "🇺🇸",
  "日本": "🇯🇵", "韩国": "🇰🇷", "欧洲": "🇪🇺", "台湾": "🏳️",
};

export default function MarketPage({ onSelectIndex }: Props) {
  const [groups, setGroups] = useState<CountryGroup[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getGlobalIndices()
      .then(setGroups)
      .catch(() => setGroups([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center" }}>
        <Text style={{ color: "var(--text-muted)", fontSize: 13 }}>加载中...</Text>
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflow: "auto" }}>
      {groups.map((group) => (
        <div key={group.country} style={{ padding: "12px 20px 0" }}>
          <Text strong style={{ fontSize: 13, color: "var(--text-primary)" }}>
            {FLAGS[group.country] || ""} {group.country}
          </Text>
          <div style={{
            display: "flex", gap: 10, marginTop: 8,
            paddingBottom: 16, borderBottom: "1px solid var(--border-color)",
            flexWrap: "wrap",
          }}>
            {group.indices.map((idx) => (
              <div
                key={idx.code}
                onClick={() => onSelectIndex?.(idx.code, idx.name, idx.market)}
                style={{
                  flex: "1 1 160px", maxWidth: 220, minWidth: 150,
                  padding: "10px 14px", borderRadius: 8,
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border-color)",
                  cursor: "pointer",
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "var(--bg-secondary)")}
              >
                <Text style={{ fontSize: 11, color: "var(--text-secondary)" }}>{idx.name}</Text>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginTop: 4, flexWrap: "wrap" }}>
                  <Text style={{
                    fontSize: 18, fontWeight: 600,
                    color: idx.change_pct >= 0 ? "#ef4444" : "#22c55e",
                  }}>
                    {idx.price.toLocaleString()}
                  </Text>
                  <Text style={{
                    fontSize: 13,
                    color: idx.change_pct >= 0 ? "#ef4444" : "#22c55e",
                  }}>
                    {idx.change_pct >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                    {" "}{idx.change_pct > 0 ? "+" : ""}{idx.change_pct}%
                  </Text>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
