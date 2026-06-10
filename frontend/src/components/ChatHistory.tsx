import { useState, useEffect } from "react";
import { List, Typography, Tag, Spin } from "antd";
import { MessageOutlined, ClockCircleOutlined, UserOutlined } from "@ant-design/icons";
import { getChatHistory } from "../api/client";
import type { ChatHistoryItem } from "../types";

const { Text, Paragraph } = Typography;

interface Props {
  onSelect: (code: string, name: string, market: string) => void;
  refreshTrigger: number;
}

export default function ChatHistory({ onSelect, refreshTrigger }: Props) {
  const [records, setRecords] = useState<ChatHistoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const data = await getChatHistory(50);
      setRecords(data);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [refreshTrigger]);

  const getMarket = (code: string) => code.startsWith("6") || code.startsWith("9") ? "sh" : "sz";

  const formatTime = (iso: string) => {
    if (!iso) return "";
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      const hours = Math.floor(diff / 3600000);
      if (hours < 1) return "刚刚";
      if (hours < 24) return hours + "小时前";
      const days = Math.floor(hours / 24);
      if (days < 7) return days + "天前";
      return iso.slice(0, 10);
    } catch {
      return "";
    }
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
        <MessageOutlined /> 对话历史
        {records.length > 0 && (
          <span style={{ fontSize: 11, color: "#aaa", fontWeight: 400, marginLeft: 4 }}>
            {records.length}条
          </span>
        )}
      </div>
      {loading ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin size="small" />
        </div>
      ) : records.length === 0 ? (
        <div style={{ padding: 16, textAlign: "center", color: "#bbb", fontSize: 12 }}>
          暂无分析记录，搜索股票开始分析
        </div>
      ) : (
        <List
          size="small"
          dataSource={records}
          renderItem={(r) => (
            <List.Item
              style={{
                cursor: "pointer",
                padding: "10px 8px",
                borderRadius: 6,
                display: "block",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = "#f0f0f0")}
              onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
              onClick={() => onSelect(r.stock_code, r.stock_name, getMarket(r.stock_code))}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <Tag
                  color={r.stock_code.startsWith("6") ? "red" : "green"}
                  style={{ fontSize: 10, margin: 0, padding: "0 4px", lineHeight: "16px" }}
                >
                  {r.stock_code}
                </Tag>
                <Text strong style={{ fontSize: 13 }}>{r.stock_name}</Text>
                <span style={{ flex: 1 }} />
                <Text style={{ fontSize: 10, color: "#bbb" }}>
                  <ClockCircleOutlined style={{ marginRight: 2 }} />
                  {formatTime(r.created_at)}
                </Text>
              </div>
              {r.user_message && (
                <div style={{ fontSize: 11, color: "#1677ff", marginBottom: 2 }}>
                  <UserOutlined style={{ marginRight: 4 }} />
                  {r.user_message}
                </div>
              )}
              <Paragraph
                style={{ margin: 0, fontSize: 11, color: "#888", lineHeight: "16px" }}
                ellipsis={{ rows: r.user_message ? 1 : 2 }}
              >
                {r.content.replace(/\n/g, " ").slice(0, 80)}
              </Paragraph>
            </List.Item>
          )}
        />
      )}
    </div>
  );
}
