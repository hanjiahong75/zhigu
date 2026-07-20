import { useState, useEffect, useRef } from "react";
import { Button, Spin, App, Typography, Card, Popconfirm } from "antd";
import {
  CameraOutlined, DeleteOutlined, LoadingOutlined,
  ArrowUpOutlined, ArrowDownOutlined,
} from "@ant-design/icons";
import {
  getPortfolio, uploadPortfolioImage, updatePortfolioItems, deletePortfolio,
} from "../api/client";
import type { Portfolio, PortfolioItem } from "../types";

const { Text } = Typography;

function formatMoney(v: number | undefined | null): string {
  if (v == null || isNaN(v)) return "-";
  const abs = Math.abs(v);
  if (abs >= 10000) return (v / 10000).toFixed(2) + "万";
  return v.toFixed(2);
}

function computeReturnRate(holdingReturn: number, costAmount: number): number | null {
  if (!costAmount || costAmount === 0) return null;
  return (holdingReturn / costAmount) * 100;
}

export default function PortfolioPanel() {
  const { message } = App.useApp();
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [loading, setLoading] = useState(false);
  const [ocrLoading, setOcrLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { loadPortfolio(); }, []);

  const loadPortfolio = async () => {
    setLoading(true);
    try {
      const data = await getPortfolio();
      if (data.items) {
        data.items = data.items.filter((item: PortfolioItem) => item.asset_type === "fund");
      }
      setPortfolio(data);
    } catch { message.error("加载持仓失败"); }
    setLoading(false);
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setOcrLoading(true);
    try {
      const result = await uploadPortfolioImage(file);
      if (result.items && result.items.length > 0) {
        const fundItems = result.items.filter((item: any) => item.asset_type === "fund");
        if (fundItems.length === 0) {
          message.warning("未识别到基金持仓，请确认图片中包含基金信息");
          return;
        }
        await updatePortfolioItems(fundItems);
        message.success(`成功导入 ${fundItems.length} 只基金`);
        loadPortfolio();
      } else {
        message.warning("未识别到持仓信息，请尝试更清晰的截图");
      }
    } catch (err: any) {
      message.error("识别失败：" + (err.message || "请重试"));
    } finally {
      setOcrLoading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRemoveFund = async (itemId: number) => {
    const items = portfolio?.items || [];
    const remaining = items.filter((i) => i.id !== itemId);
    try {
      if (remaining.length === 0) {
        await deletePortfolio();
        setPortfolio(null);
      } else {
        await updatePortfolioItems(remaining);
        loadPortfolio();
      }
      message.success("已移除");
    } catch { message.error("操作失败"); }
  };

  const handleClearAll = async () => {
    try {
      await deletePortfolio();
      setPortfolio(null);
      message.success("已清空");
    } catch { message.error("清空失败"); }
  };

  const fundItems: PortfolioItem[] = portfolio?.items || [];
  const hasFunds = fundItems.length > 0;

  // Compute totals
  const totalHoldingAmount = fundItems.reduce((sum, f) => sum + (f.holding_amount || 0), 0);
  const totalHoldingReturn = fundItems.reduce((sum, f) => sum + (f.holding_return || 0), 0);
  const totalCostAmount = fundItems.reduce((sum, f) => sum + (f.cost_amount || 0), 0);
  const totalReturnRate = computeReturnRate(totalHoldingReturn, totalCostAmount);
  const totalDailyReturn = fundItems.reduce((sum, f) => sum + (f.daily_return || 0), 0);

  if (loading) return <div style={{ textAlign: "center", padding: 40 }}><Spin /></div>;

  return (
    <div style={{ padding: "0 12px 12px" }}>
      {/* Action bar */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "8px 4px", gap: 8,
      }}>
        <div style={{ display: "flex", gap: 8 }}>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: "none" }}
            onChange={handleFileSelect}
          />
          <Button
            icon={ocrLoading ? <LoadingOutlined /> : <CameraOutlined />}
            onClick={() => fileInputRef.current?.click()}
            loading={ocrLoading}
            size="middle"
          >
            从相册选择
          </Button>
        </div>
        {hasFunds && (
          <Popconfirm title="确定清空所有基金持仓？" onConfirm={handleClearAll} okText="确定" cancelText="取消">
            <Button size="small" danger icon={<DeleteOutlined />}>清空</Button>
          </Popconfirm>
        )}
      </div>

      {ocrLoading && (
        <div style={{
          textAlign: "center", padding: "24px 12px",
          background: "var(--bg-secondary)", borderRadius: 12,
          border: "1px solid var(--border-color)", marginBottom: 8,
        }}>
          <Spin size="large" />
          <div style={{ marginTop: 12, fontSize: 13, color: "var(--text-muted)" }}>正在识别图片中的基金持仓...</div>
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>使用 OCR + AI 解析，请稍候</div>
        </div>
      )}

      {/* Total summary card */}
      {hasFunds && (
        <Card
          className="card-hover"
          size="small"
          style={{
            marginBottom: 12, borderRadius: 12,
            border: "1px solid var(--border-color)",
            background: "var(--bg-secondary)",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <div style={{ textAlign: "center", flex: 1, minWidth: 80 }}>
              <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>基金数</Text>
              <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)", marginTop: 2 }}>
                {fundItems.length} 只
              </div>
            </div>
            <div style={{ textAlign: "center", flex: 1, minWidth: 80 }}>
              <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>持有金额</Text>
              <div style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary)", marginTop: 2 }}>
                ¥{formatMoney(totalHoldingAmount)}
              </div>
            </div>
            <div style={{ textAlign: "center", flex: 1, minWidth: 80 }}>
              <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>当日收益</Text>
              <div style={{
                fontSize: 18, fontWeight: 700, marginTop: 2,
                color: totalDailyReturn >= 0 ? "#cf1322" : "#3f8600",
              }}>
                {totalDailyReturn >= 0 ? "+" : ""}¥{formatMoney(totalDailyReturn)}
              </div>
            </div>
            <div style={{ textAlign: "center", flex: 1, minWidth: 80 }}>
              <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>累计收益</Text>
              <div style={{
                fontSize: 18, fontWeight: 700, marginTop: 2,
                color: totalHoldingReturn >= 0 ? "#cf1322" : "#3f8600",
              }}>
                {totalHoldingReturn >= 0 ? "+" : ""}¥{formatMoney(totalHoldingReturn)}
              </div>
              {totalReturnRate != null && (
                <div style={{
                  fontSize: 11,
                  color: totalReturnRate >= 0 ? "#cf1322" : "#3f8600",
                }}>
                  {totalReturnRate >= 0 ? "+" : ""}{totalReturnRate.toFixed(2)}%
                </div>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Fund cards */}
      {hasFunds && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {fundItems.map((fund) => {
            const returnRate = computeReturnRate(fund.holding_return || 0, fund.cost_amount || 0);
            const dailyReturnVal = fund.daily_return || 0;
            const dailyReturnPct = fund.daily_return_pct || 0;
            const isPositive = (fund.holding_return || 0) >= 0;
            const dailyPositive = dailyReturnVal >= 0;

            return (
              <Card
                key={fund.id}
                className="card-hover"
                size="small"
                style={{
                  borderRadius: 12, border: "1px solid var(--border-color)",
                  background: "var(--bg-secondary)",
                }}
              >
                <div style={{ display: "flex", alignItems: "stretch", gap: 0 }}>
                  {/* Fund name + holding amount */}
                  <div style={{ flex: 2, minWidth: 0, paddingRight: 8, borderRight: "1px solid var(--border-color)" }}>
                    <Text
                      strong
                      style={{
                        fontSize: 14, color: "var(--text-primary)",
                        display: "block", lineHeight: "20px",
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                      }}
                    >
                      {fund.stock_name}
                    </Text>
                    <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>
                      持有 ¥{formatMoney(fund.holding_amount)}
                    </Text>
                    {fund.sector && (
                      <div style={{
                        marginTop: 4, display: "inline-block",
                        padding: "1px 8px", borderRadius: 10,
                        background: "var(--bg-sidebar)",
                        fontSize: 10, color: "var(--text-secondary)",
                      }}>
                        {fund.sector}
                      </div>
                    )}
                  </div>

                  {/* Daily return */}
                  <div style={{
                    flex: 1.5, minWidth: 80,
                    textAlign: "center", padding: "0 8px",
                    borderRight: "1px solid var(--border-color)",
                    display: "flex", flexDirection: "column", justifyContent: "center",
                  }}>
                    <div style={{
                      fontSize: 16, fontWeight: 700,
                      color: dailyPositive ? "#cf1322" : "#3f8600",
                    }}>
                      {dailyPositive ? "+" : ""}¥{formatMoney(dailyReturnVal)}
                    </div>
                    <div style={{
                      fontSize: 11, marginTop: 2,
                      color: dailyPositive ? "#cf1322" : "#3f8600",
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 2,
                    }}>
                      {dailyPositive ? <ArrowUpOutlined style={{ fontSize: 10 }} /> : <ArrowDownOutlined style={{ fontSize: 10 }} />}
                      {dailyReturnPct >= 0 ? "+" : ""}{dailyReturnPct.toFixed(2)}%
                    </div>
                  </div>

                  {/* Holding return */}
                  <div style={{
                    flex: 1.5, minWidth: 80,
                    textAlign: "center", padding: "0 8px",
                    display: "flex", flexDirection: "column", justifyContent: "center",
                  }}>
                    <div style={{
                      fontSize: 16, fontWeight: 700,
                      color: isPositive ? "#cf1322" : "#3f8600",
                    }}>
                      {isPositive ? "+" : ""}¥{formatMoney(fund.holding_return)}
                    </div>
                    <div style={{
                      fontSize: 11, marginTop: 2,
                      color: isPositive ? "#cf1322" : "#3f8600",
                      display: "flex", alignItems: "center", justifyContent: "center", gap: 2,
                    }}>
                      {returnRate != null
                        ? <>{returnRate >= 0 ? "+" : ""}{returnRate.toFixed(2)}%</>
                        : "-"}
                    </div>
                  </div>

                  {/* Delete */}
                  <div style={{
                    display: "flex", alignItems: "center", paddingLeft: 6,
                  }}>
                    <Button
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={() => handleRemoveFund(fund.id)}
                    />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Empty state */}
      {!hasFunds && !ocrLoading && (
        <div style={{
          textAlign: "center", padding: "40px 20px",
          background: "var(--bg-secondary)", borderRadius: 12,
          border: "1px dashed var(--border-color)",
        }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>📷</div>
          <Text style={{ fontSize: 14, color: "var(--text-primary)", display: "block" }}>
            暂无基金持仓
          </Text>
          <Text style={{ fontSize: 12, color: "var(--text-muted)", display: "block", marginTop: 4 }}>
            截图你的基金持仓页面，一键导入识别
          </Text>
        </div>
      )}
    </div>
  );
}