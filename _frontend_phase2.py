import pathlib

# ============================================================
# 3. ChatHistory.tsx - show user_message prominently
# ============================================================
chat = r'''import { useState, useEffect } from "react";
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
'''
pathlib.Path("frontend/src/components/ChatHistory.tsx").write_text(chat, encoding="utf-8")
print("3. ChatHistory.tsx updated")

# ============================================================
# 4. AnalysisPanel.tsx - add memoryContext and summary props
# ============================================================
panel = r'''import { Card, Tag, Spin, Statistic, Row, Col } from "antd";
import {
  RiseOutlined,
  FallOutlined,
  ArrowUpOutlined,
  ArrowDownOutlined,
  HistoryOutlined,
  FileTextOutlined,
} from "@ant-design/icons";
import type { StockQuote } from "../types";

interface Props {
  analysis: string;
  quote: StockQuote;
  loading: boolean;
  memoryContext?: string;
  summary?: string;
}

function renderMarkdown(text: string): string {
  let html = text
    .replace(/^### (.+)$/gm, '<h3 style="color:#1677ff;font-size:16px;margin:16px 0 8px;border-bottom:1px solid #e8f4ff;padding-bottom:6px;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size:18px;margin:20px 0 10px;">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br/>");

  html = html.replace(
    /\|(.+)\|/g,
    (match) => {
      if (match.includes("---")) return "";
      const cells = match.split("|").filter((c) => c.trim());
      const isHeader =
        cells.length > 0 &&
        cells.every((c) => /^[\s\u4e00-\u9fff]+$/.test(c.trim()));
      const tag = isHeader ? "th" : "td";
      const row = cells.map((c) => `<${tag}>${c.trim()}</${tag}>`).join("");
      return `<tr>${row}</tr>`;
    }
  );

  html = `<p>${html}</p>`;
  html = html.replace(
    /(<tr>.*?<\/tr>)/gs,
    (table) =>
      `<table style="width:100%;border-collapse:collapse;margin:12px 0;"><tbody>${table}</tbody></table>`
  );

  return html;
}

export default function AnalysisPanel({ analysis, quote, loading, memoryContext, summary }: Props) {
  const isUp = quote.change_pct >= 0;

  return (
    <Card
      title={
        <span>
          <Tag color="blue">{quote.code}</Tag>
          {quote.name}
          <span
            style={{
              marginLeft: 12,
              fontSize: 20,
              fontWeight: 700,
              color: isUp ? "#ef4444" : "#22c55e",
            }}
          >
            {quote.price.toFixed(2)}
          </span>
          <span
            style={{
              marginLeft: 8,
              fontSize: 14,
              color: isUp ? "#ef4444" : "#22c55e",
            }}
          >
            {isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            {isUp ? "+" : ""}
            {quote.change_pct.toFixed(2)}%
          </span>
        </span>
      }
      style={{ marginBottom: 16 }}
    >
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Statistic title="开盘" value={quote.open} precision={2} />
        </Col>
        <Col span={4}>
          <Statistic title="最高" value={quote.high} precision={2} />
        </Col>
        <Col span={4}>
          <Statistic title="最低" value={quote.low} precision={2} />
        </Col>
        <Col span={4}>
          <Statistic title="昨收" value={quote.pre_close} precision={2} />
        </Col>
        <Col span={4}>
          <Statistic
            title="成交额"
            value={quote.amount > 1e8 ? quote.amount / 1e8 : quote.amount}
            precision={2}
            suffix={quote.amount > 1e8 ? "亿" : "元"}
          />
        </Col>
        <Col span={4}>
          <Statistic title="换手率" value={quote.turnover} precision={2} suffix="%" />
        </Col>
      </Row>
      <Card
        title="AI 投研分析"
        style={{ background: "#fafcff", border: "1px solid #e8f4ff" }}
      >
        {loading ? (
          <div style={{ textAlign: "center", padding: 24 }}>
            <Spin /> 正在生成分析...
          </div>
        ) : (
          <div
            style={{ lineHeight: 1.8, fontSize: 14, color: "#333" }}
            dangerouslySetInnerHTML={{ __html: renderMarkdown(analysis) }}
          />
        )}
      </Card>
      {memoryContext && (
        <Card
          size="small"
          title={<span><HistoryOutlined /> 记忆上下文</span>}
          style={{ marginTop: 12, background: "#fafafa", border: "1px solid #e8e8e8" }}
        >
          <pre style={{ margin: 0, fontSize: 12, color: "#666", whiteSpace: "pre-wrap", lineHeight: "18px" }}>
            {memoryContext}
          </pre>
        </Card>
      )}
      {summary && (
        <Card
          size="small"
          title={<span><FileTextOutlined /> 投资日志摘要</span>}
          style={{ marginTop: 12, background: "#fffbe6", border: "1px solid #ffe58f" }}
        >
          <pre style={{ margin: 0, fontSize: 12, color: "#666", whiteSpace: "pre-wrap", lineHeight: "18px" }}>
            {summary}
          </pre>
        </Card>
      )}
    </Card>
  );
}
'''
pathlib.Path("frontend/src/components/AnalysisPanel.tsx").write_text(panel, encoding="utf-8")
print("4. AnalysisPanel.tsx updated")