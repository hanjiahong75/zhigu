import { useState, useEffect } from "react";
import { List, Typography, Tag, Popconfirm, message } from "antd";
import { DeleteOutlined, StarOutlined } from "@ant-design/icons";
import { getWatchlist, removeFromWatchlist } from "../api/client";
import type { WatchlistItem, StockQuote } from "../types";

const { Text } = Typography;

interface Props {
  onSelect: (item: WatchlistItem) => void;
  refreshTrigger: number;
  quotes?: StockQuote[];
  alerts?: string[];
}

export default function Watchlist({ onSelect, refreshTrigger, quotes, alerts }: Props) {
  const [items, setItems] = useState<WatchlistItem[]>([]);

  const load = async () => {
    try {
      const data = await getWatchlist();
      setItems(data);
    } catch {
      // silent
    }
  };

  useEffect(() => {
    load();
  }, [refreshTrigger]);

  const handleRemove = async (code: string) => {
    try {
      await removeFromWatchlist(code);
      message.success("已移除");
      load();
    } catch {
      message.error("移除失败");
    }
  };

  const getQuote = (code: string): StockQuote | undefined => {
    return quotes?.find((q) => q.code === code);
  };

  const isAlerting = (code: string): boolean => {
    return alerts?.some((a) => a.includes(code)) ?? false;
  };

  return (
    <div style={{ padding: "12px 8px" }}>
      <div
        style={{
          padding: "0 8px 12px",
          fontSize: 13,
          fontWeight: 600,
          color: "#666",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <StarOutlined /> 自选股
        {quotes && quotes.length > 0 && (
          <span style={{ fontSize: 11, color: "#aaa", fontWeight: 400, marginLeft: 4 }}>
            {quotes.length}只
          </span>
        )}
      </div>
      {items.length === 0 ? (
        <div style={{ padding: 16, textAlign: "center", color: "#bbb", fontSize: 12 }}>
          暂无自选，搜索添加
        </div>
      ) : (
        <List
          size="small"
          dataSource={items}
          renderItem={(item) => {
            const q = getQuote(item.code);
            const alert = isAlerting(item.code);
            return (
              <List.Item
                style={{
                  cursor: "pointer",
                  padding: "6px 8px",
                  borderRadius: 6,
                  background: alert ? "#fff7e6" : undefined,
                }}
                onMouseEnter={(e) =>
                  (e.currentTarget.style.background = alert ? "#fff3d9" : "#f0f0f0")
                }
                onMouseLeave={(e) =>
                  (e.currentTarget.style.background = alert ? "#fff7e6" : "transparent")
                }
                onClick={() => onSelect(item)}
                actions={[
                  <Popconfirm
                    key="del"
                    title="确定移除此自选？"
                    onConfirm={(e) => {
                      e?.stopPropagation();
                      handleRemove(item.code);
                    }}
                    onCancel={(e) => e?.stopPropagation()}
                  >
                    <DeleteOutlined
                      style={{ fontSize: 12, color: "#ccc" }}
                      onClick={(e) => e.stopPropagation()}
                    />
                  </Popconfirm>,
                ]}
              >
                <List.Item.Meta
                  title={
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <Tag
                        color={item.code.startsWith("6") ? "red" : "green"}
                        style={{ fontSize: 10, margin: 0, padding: "0 4px", lineHeight: "16px" }}
                      >
                        {item.code}
                      </Tag>
                      <Text style={{ fontSize: 13 }}>{item.name}</Text>
                      {alert && <span style={{ fontSize: 11, color: "#ef4444" }}>⚡</span>}
                    </div>
                  }
                  description={
                    q ? (
                      <span style={{ fontSize: 12, color: q.change_pct >= 0 ? "#ef4444" : "#22c55e" }}>
                        {q.price.toFixed(2)}{" "}
                        <span style={{ fontWeight: 600 }}>
                          {q.change_pct > 0 ? "+" : ""}{q.change_pct}%
                        </span>
                      </span>
                    ) : (
                      <span style={{ fontSize: 11, color: "#ccc" }}>加载中...</span>
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
