import { Card, Tag, Spin, Statistic, Row, Col } from "antd";
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
    <Card className="card-hover stock-card-enter"
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
      <Card className="card-hover stock-card-enter"
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
        <Card className="card-hover stock-card-enter"
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
        <Card className="card-hover stock-card-enter"
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

