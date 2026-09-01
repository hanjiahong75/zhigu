import { useState, useEffect, useRef } from "react";
import { Modal, Descriptions, Tag, Typography, Button, message, Skeleton, Row, Col, Statistic } from "antd";
import { PlusOutlined, CheckOutlined, ArrowUpOutlined, ArrowDownOutlined, RobotOutlined } from "@ant-design/icons";
import { getStockQuote, getKlineData, getIndicators, addToWatchlist, getWatchlist, removeFromWatchlist } from "../api/client";
import { useTheme } from "../api/ThemeContext";
import KlineChart from "./KlineChart";
import type { StockQuote, KlineItem } from "../types";

const { Text, Title } = Typography;

interface Props {
  open: boolean;
  stockCode: string;
  stockName: string;
  market: string;
  onClose: () => void;
  onAskAI: (code: string, name: string) => void;
}

export default function StockDetailModal({ open, stockCode, stockName, market, onClose, onAskAI }: Props) {
  const [quote, setQuote] = useState<StockQuote | null>(null);
  const [kline, setKline] = useState<KlineItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [klt, setKlt] = useState("101");
  const [indicators, setIndicators] = useState<any>(null);
  const [inWatchlist, setInWatchlist] = useState(false);
  const [fetchDays, setFetchDays] = useState(300);
  const loadingMore = useRef(false);
  const { isDark } = useTheme();

  useEffect(() => {
    if (!open || !stockCode) return;
    setFetchDays(500);  // Reset on new stock
    getWatchlist().then((items: any[]) => {
      setInWatchlist(items.some((i: any) => i.code === stockCode));
    }).catch(() => {});
    setLoading(true);
    setError(null);
    Promise.all([
      getStockQuote(stockCode, market),
      getKlineData(stockCode, market, fetchDays, klt),
      getIndicators(stockCode, market, fetchDays, klt),
    ])
      .then(([q, k, ind]) => {
        setQuote(q);
        setKline(k.kline || []);
        setIndicators(ind.indicators || null);
      })
      .catch((e) => setError(e.message || "加载失败"))
      .finally(() => setLoading(false));
  }, [open, stockCode, market, klt]);

  const handleLoadMore = async () => {
    if (loadingMore.current) return;
    loadingMore.current = true;
    const newDays = fetchDays + 300;
    setFetchDays(newDays);
    try {
      const [k, ind] = await Promise.all([
        getKlineData(stockCode, market, newDays, klt),
        getIndicators(stockCode, market, newDays, klt),
      ]);
      setKline(k.kline || []);
      setIndicators(ind.indicators || null);
    } catch { /* ignore */ }
    finally { loadingMore.current = false; }
  };

  const handleToggleWatchlist = async () => {
    if (inWatchlist) {
      try {
        await removeFromWatchlist(stockCode);
        setInWatchlist(false);
        message.success("已从自选移除");
      } catch { message.error("移除失败"); }
    } else {
      try {
        await addToWatchlist(stockCode, stockName, market);
        setInWatchlist(true);
        message.success(`已添加 ${stockName}`);
      } catch { message.error("添加失败"); }
    }
  };

  const isUp = quote ? quote.change_pct >= 0 : true;

  const handlePeriodChange = async (newKlt: string) => {
    setKlt(newKlt);
    try {
      const [k, ind] = await Promise.all([
        getKlineData(stockCode, market, fetchDays, newKlt),
        getIndicators(stockCode, market, fetchDays, newKlt),
      ]);
      setKline(k.kline || []);
      setIndicators(ind.indicators || null);
    } catch { /* ignore */ }
  };

  return (
    <Modal
      title={null}
      open={open}
      onCancel={onClose}
      footer={null}
      width={720}
      destroyOnClose
      styles={{ body: { padding: "24px", background: "var(--bg-primary)" } }}
    >
      {loading ? (
        <Skeleton active paragraph={{ rows: 6 }} />
      ) : error ? (
        <div style={{ textAlign: "center", padding: 40, color: "#ef4444" }}>{error}</div>
      ) : quote ? (
        <div>
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Tag color={stockCode.startsWith("6") ? "red" : "green"}>{stockCode}</Tag>
              <Title level={4} style={{ margin: 0, color: "var(--text-primary)" }}>{stockName}</Title>
            </div>
            <Text style={{ fontSize: 22, fontWeight: 700, color: isUp ? "#ef4444" : "#22c55e" }}>
              {quote.price.toFixed(2)}
            </Text>
          </div>

          {/* Price change */}
          <div style={{ marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
            <Text style={{ fontSize: 14, color: isUp ? "#ef4444" : "#22c55e" }}>
              {isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              {isUp ? "+" : ""}{quote.change_amount.toFixed(2)} ({isUp ? "+" : ""}{quote.change_pct}%)
            </Text>
          </div>

          {/* Key stats */}
          <Row gutter={[8, 8]} style={{ marginBottom: 16 }}>
            <Col span={8}>
              <Statistic title="开盘" value={quote.open} precision={2} valueStyle={{ fontSize: 13 }} />
            </Col>
            <Col span={8}>
              <Statistic title="最高" value={quote.high} precision={2} valueStyle={{ fontSize: 13, color: "#ef4444" }} />
            </Col>
            <Col span={8}>
              <Statistic title="最低" value={quote.low} precision={2} valueStyle={{ fontSize: 13, color: "#22c55e" }} />
            </Col>
            <Col span={8}>
              <Statistic title="昨收" value={quote.pre_close} precision={2} valueStyle={{ fontSize: 13 }} />
            </Col>
            <Col span={8}>
              <Statistic title="成交额" value={quote.amount > 1e8 ? quote.amount / 1e8 : quote.amount} precision={2} suffix={quote.amount > 1e8 ? "亿" : "元"} valueStyle={{ fontSize: 13 }} />
            </Col>
            <Col span={8}>
              <Statistic title="换手率" value={quote.turnover} precision={2} suffix="%" valueStyle={{ fontSize: 13 }} />
            </Col>
          </Row>

          {/* K-line mini chart */}
          {kline.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <KlineChart
                isDark={isDark}
                data={kline}
                stockName={stockName}
                stockCode={stockCode}
                indicators={indicators}
                klt={klt}
                onPeriodChange={handlePeriodChange}
                onLoadMore={handleLoadMore}
              />
            </div>
          )}

          {/* Actions */}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            {stockCode.length >= 6 && (
              <Button icon={inWatchlist ? <CheckOutlined /> : <PlusOutlined />} onClick={handleToggleWatchlist}>{inWatchlist ? "已加自选" : "加自选"}</Button>
            )}
            <Button type="primary" icon={<RobotOutlined />} onClick={() => { onClose(); onAskAI(stockCode, stockName); }}>
              问AI
            </Button>
          </div>
        </div>
      ) : null}
    </Modal>
  );
}
