import { useState, useEffect } from "react";
import { List, Tag, Typography, Popconfirm, message } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { getWatchlist, getWatchlistQuotes, removeFromWatchlist } from "../api/client";
import type { WatchlistItem, StockQuote } from "../types";

const { Text } = Typography;
const ALERT_THRESHOLD = 3;

interface Props {
  onSelectStock?: (code: string, name: string, market: string) => void;
}

export default function WatchlistPage({ onSelectStock }: Props) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [quotes, setQuotes] = useState<StockQuote[]>([]);

  const load = async () => {
    try {
      const data = await getWatchlist();
      setItems(data);
      if (data.length > 0) {
        const codes = data.map((i: WatchlistItem) => i.code);
        const qs = await getWatchlistQuotes(codes);
        setQuotes(qs);
      }
    } catch { /* silent */ }
  };

  useEffect(() => { load(); }, []);
  useEffect(() => {
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, []);

  const handleRemove = async (code: string) => {
    try { await removeFromWatchlist(code); message.success("已移除"); load(); } catch { message.error("移除失败"); }
  };

  const getQuote = (code: string) => quotes.find((q) => q.code === code);

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
      <Text strong style={{ fontSize: 14, color: "var(--text-primary)" }}>自选股 ({items.length})</Text>
      {items.length === 0 ? (
        <div style={{ textAlign: "center", color: "var(--text-muted)", marginTop: 40, fontSize: 13 }}>
          暂无自选，在上方搜索栏搜索并添加
        </div>
      ) : (
        <List
          dataSource={items}
          style={{ marginTop: 8 }}
          renderItem={(item) => {
            const q = getQuote(item.code);
            const alert = q && Math.abs(q.change_pct) >= ALERT_THRESHOLD;
            const isUp = q ? q.change_pct >= 0 : true;
            return (
              <List.Item
                className="watchlist-item"
                onClick={() => onSelectStock?.(item.code, item.name, item.market || (item.code.startsWith("6") ? "sh" : "sz"))}
                style={{
                  padding: "8px 12px", borderRadius: 6,
                  background: alert ? "var(--thread-hover-bg)" : "transparent",
                }}
                actions={[
                  <Popconfirm key="del" title="移除此自选？" onConfirm={() => handleRemove(item.code)}>
                    <DeleteOutlined style={{ color: "var(--text-muted)" }} />
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <Tag color={item.code.startsWith("6") ? "red" : "green"} style={{ margin: 0 }}>
                        {item.code}
                      </Tag>
                      <Text strong style={{ fontSize: 13, color: "var(--text-primary)" }}>{item.name}</Text>
                      {alert && <span style={{ color: "#ef4444", fontSize: 11 }}>⚡异动</span>}
                    </div>
                  }
                  description={
                    q ? (
                      <span style={{ fontSize: 14, fontWeight: 600, color: isUp ? "#ef4444" : "#22c55e" }}>
                        {q.price.toFixed(2)} {isUp ? "+" : ""}{q.change_pct}%
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontSize: 11 }}>加载中...</span>
                    )
                  }
                />
              </List.Item>
            );
          }}
        />
      )}
    </div>
  );
}
