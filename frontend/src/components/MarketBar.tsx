import { useState, useEffect } from "react";
import { Tag } from "antd";
import { getMarketIndices, getGlobalIndices } from "../api/client";
import type { MarketIndex } from "../types";

export default function MarketBar() {
  const [indices, setIndices] = useState<MarketIndex[]>([]);

  useEffect(() => {
    const load = async () => {
      try {
        const [cnData, globalData] = await Promise.all([
          getMarketIndices(),
          getGlobalIndices(),
        ]);
        const cn = (cnData.indices || []).slice(0, 3);
        const gl = (globalData.indices || []).slice(0, 4);
        setIndices([...cn, ...gl]);
      } catch {
        // silent
      }
    };
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  if (indices.length === 0) return null;

  return (
    <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
      {indices.map((idx) => {
        const isUp = idx.change_pct >= 0;
        return (
          <div key={idx.code} style={{ fontSize: 12 }}>
            <span style={{ color: "#888", marginRight: 4 }}>{idx.name}</span>
            <span style={{ fontWeight: 600, marginRight: 4 }}>
              {idx.price.toFixed(2)}
            </span>
            <Tag
              color={isUp ? "red" : "green"}
              style={{ fontSize: 11, margin: 0, padding: "0 4px", lineHeight: "18px" }}
            >
              {isUp ? "+" : ""}
              {idx.change_pct.toFixed(2)}%
            </Tag>
          </div>
        );
      })}
    </div>
  );
}
