import { useState } from "react";
import { Card, Tag, Typography, Row, Col, Statistic } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined } from "@ant-design/icons";
import KlineChart from "./KlineChart";
import { useTheme } from "../api/ThemeContext";
import { getKlineData, getIndicators } from "../api/client";
import type { StockQuote, KlineItem, IndicatorsData } from "../types";

const { Text } = Typography;

interface Props {
  stockCode: string;
  stockName: string;
  market: string;
  quote: StockQuote;
  initialKline: KlineItem[];
  initialIndicators?: IndicatorsData | null;
}

export default function ChatStockCard({
  stockCode, stockName, market,
  quote, initialKline, initialIndicators,
}: Props) {
  const [kline, setKline] = useState<KlineItem[]>(initialKline);
  const [indicators, setIndicators] = useState<IndicatorsData | null>(initialIndicators || null);
  const [klt, setKlt] = useState("101");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { isDark } = useTheme();
  const isUp = quote.change_pct >= 0;

  const handlePeriodChange = async (newKlt: string) => {
    setKlt(newKlt);
    setLoading(true);
    setError(null);
    try {
      const [klineRes, indRes] = await Promise.all([
        getKlineData(stockCode, market, 500, newKlt),
        getIndicators(stockCode, market, 10000, newKlt),
      ]);
      setKline(klineRes.kline || []);
      setIndicators(indRes.indicators || null);
    } catch (e: any) {
      setError(e.message || "加载失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="stock-card-enter card-hover" style={{ animationDelay: "0.2s", marginTop: 8 }}>
      {/* Quote card */}
      <Card size="small" style={{ marginBottom: 8, background: "var(--bg-secondary)", border: "1px solid var(--border-color)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
          <Tag color="blue">{quote.code}</Tag>
          <Text strong>{quote.name}</Text>
          <Text style={{ fontSize: 18, fontWeight: 700, color: isUp ? "#ef4444" : "#22c55e" }}>
            {quote.price.toFixed(2)}
          </Text>
          <Text style={{ fontSize: 14, color: isUp ? "#ef4444" : "#22c55e" }}>
            {isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            {isUp ? "+" : ""}{quote.change_pct.toFixed(2)}%
          </Text>
        </div>
        <Row gutter={8}>
          <Col span={4}>
            <Statistic title="开盘" value={quote.open} precision={2} valueStyle={{ fontSize: 12 }} />
          </Col>
          <Col span={4}>
            <Statistic title="最高" value={quote.high} precision={2} valueStyle={{ fontSize: 12 }} />
          </Col>
          <Col span={4}>
            <Statistic title="最低" value={quote.low} precision={2} valueStyle={{ fontSize: 12 }} />
          </Col>
          <Col span={4}>
            <Statistic title="昨收" value={quote.pre_close} precision={2} valueStyle={{ fontSize: 12 }} />
          </Col>
          <Col span={4}>
            <Statistic
              title="成交额"
              value={quote.amount > 1e8 ? quote.amount / 1e8 : quote.amount}
              precision={2}
              suffix={quote.amount > 1e8 ? "亿" : "元"}
              valueStyle={{ fontSize: 12 }}
            />
          </Col>
          <Col span={4}>
            <Statistic title="换手率" value={quote.turnover} precision={2} suffix="%" valueStyle={{ fontSize: 12 }} />
          </Col>
        </Row>
      </Card>

      {/* Full K-line chart */}
      {error && (
        <div style={{ padding: 8, color: "#cf1322", fontSize: 12, marginBottom: 8 }}>{error}</div>
      )}
      <KlineChart
        isDark={isDark}
        data={kline}
        stockName={stockName}
        stockCode={stockCode}
        indicators={indicators}
        klt={klt}
        onPeriodChange={handlePeriodChange}
      />
    </div>
  );
}
