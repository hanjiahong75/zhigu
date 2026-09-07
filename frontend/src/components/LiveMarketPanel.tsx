import { useEffect, useState } from "react";
import { Tag, Tooltip, Button, Switch, Select, Input } from "antd";
import {
  ReloadOutlined, RightOutlined, LeftOutlined, StockOutlined,
  PlusOutlined, DeleteOutlined, EyeOutlined,
} from "@ant-design/icons";
import {
  getWatchlist, getStockSignal,
  getThreadWatches, addThreadWatch, removeThreadWatch, refreshThreadWatch,
  type ThreadWatch,
} from "../api/client";
import { useQuoteStream } from "../api/useQuoteStream";
import { useChat } from "../api/ChatContext";
import type { WatchlistItem, StockQuote } from "../types";

interface SignalInfo {
  rating: string;
  score: number;
  confidence: number;
  summary?: string;
}

const RATING_COLOR: Record<string, string> = {
  "强烈买入": "red",
  "买入": "red",
  "观望": "default",
  "卖出": "green",
  "强烈卖出": "green",
};

function marketOfCode(code: string): string {
  return code.startsWith("6") || code.startsWith("9") ? "sh" : "sz";
}

function ratingTag(rating: string | undefined) {
  const r = rating || "--";
  return <Tag color={RATING_COLOR[r] || "default"} style={{ margin: 0 }}>{r}</Tag>;
}

/** Right sidebar of the chat workbench: thread watch list + watchlist quotes/signals (M4/M5). */
export default function LiveMarketPanel() {
  const { threadId, messages } = useChat();
  const [expanded, setExpanded] = useState(true);
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [signals, setSignals] = useState<Record<string, SignalInfo>>({});
  const [loadingSignals, setLoadingSignals] = useState(false);
  // watch state (M5)
  const [watches, setWatches] = useState<ThreadWatch[]>([]);
  const [watchSignals, setWatchSignals] = useState<Record<string, SignalInfo>>({});
  const [addCode, setAddCode] = useState("");
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [auto, setAuto] = useState(() => localStorage.getItem("zhigu_watch_auto") !== "off");
  const [intervalSec, setIntervalSec] = useState(() => Number(localStorage.getItem("zhigu_watch_interval") || "10") || 10);

  const codes = items.map((i) => i.code);
  const watchCodes = watches.map((w) => w.code);
  const liveQuotes = useQuoteStream(codes, intervalSec, expanded && codes.length > 0);
  const liveWatchQuotes = useQuoteStream(watchCodes, intervalSec, expanded && auto && watchCodes.length > 0);

  const persistAuto = (v: boolean) => {
    setAuto(v);
    localStorage.setItem("zhigu_watch_auto", v ? "on" : "off");
  };
  const persistInterval = (v: number) => {
    setIntervalSec(v);
    localStorage.setItem("zhigu_watch_interval", String(v));
  };

  useEffect(() => {
    (async () => {
      try {
        setItems(await getWatchlist());
      } catch {
        /* silent */
      }
    })();
  }, []);

  const loadWatches = async () => {
    if (!threadId) {
      setWatches([]);
      return;
    }
    try {
      setWatches(await getThreadWatches(threadId));
    } catch {
      /* silent */
    }
  };

  useEffect(() => {
    loadWatches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, messages]);

  const loadSignals = async () => {
    if (items.length === 0) return;
    setLoadingSignals(true);
    try {
      const next: Record<string, SignalInfo> = {};
      await Promise.all(items.map(async (item) => {
        try {
          const s = await getStockSignal(item.code, item.market || marketOfCode(item.code));
          if (!s.error) next[item.code] = s;
        } catch {
          /* silent */
        }
      }));
      setSignals(next);
    } finally {
      setLoadingSignals(false);
    }
  };

  const loadWatchSignals = async () => {
    if (watches.length === 0) return;
    const next: Record<string, SignalInfo> = {};
    await Promise.all(watches.map(async (w) => {
      try {
        const s = await getStockSignal(w.code, w.market || marketOfCode(w.code));
        if (!s.error) next[w.code] = s;
      } catch {
        /* silent */
      }
    }));
    setWatchSignals(next);
  };

  useEffect(() => {
    if (expanded) {
      loadSignals();
      loadWatchSignals();
    }
    const timer = setInterval(() => {
      if (expanded) {
        loadSignals();
        loadWatchSignals();
      }
    }, 60000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expanded, items, watches]);

  const handleAddWatch = async () => {
    const code = addCode.trim();
    if (!code || !threadId) return;
    try {
      await addThreadWatch(threadId, code, marketOfCode(code), "");
      setAddCode("");
      await loadWatches();
      await loadWatchSignals();
    } catch {
      /* silent */
    }
  };

  const handleRemoveWatch = async (code: string) => {
    if (!threadId) return;
    try {
      await removeThreadWatch(threadId, code);
      await loadWatches();
    } catch {
      /* silent */
    }
  };

  const handleRefreshWatch = async (code: string) => {
    if (!threadId) return;
    setBusy((p) => ({ ...p, [code]: true }));
    try {
      await refreshThreadWatch(threadId, code);
      await loadWatches();
      await loadWatchSignals();
    } catch {
      /* silent */
    } finally {
      setBusy((p) => ({ ...p, [code]: false }));
    }
  };

  if (!expanded) {
    return (
      <div style={{ borderLeft: "1px solid var(--border-color)", background: "var(--bg-secondary)", display: "flex", alignItems: "center", padding: "8px 6px" }}>
        <Button type="text" size="small" icon={<LeftOutlined />} onClick={() => setExpanded(true)} title="展开实时行情/信号" />
      </div>
    );
  }

  return (
    <div className="glass-panel" style={{
      width: 300, flexShrink: 0, borderLeft: "1px solid var(--border-color)",
      display: "flex", flexDirection: "column", overflow: "hidden",
    }}>
      <div style={{
        padding: "10px 12px", borderBottom: "1px solid var(--border-color)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)", display: "flex", alignItems: "center", gap: 6 }}>
          <StockOutlined /> 实时行情/信号
        </span>
        <span style={{ display: "flex", gap: 4 }}>
          <Button type="text" size="small" icon={<ReloadOutlined spin={loadingSignals} />} onClick={() => { loadSignals(); loadWatchSignals(); }} title="刷新信号" />
          <Button type="text" size="small" icon={<RightOutlined />} onClick={() => setExpanded(false)} title="收起" />
        </span>
      </div>

      <div style={{
        padding: "6px 12px", borderBottom: "1px solid var(--border-color)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <span style={{ fontSize: 11, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
          <EyeOutlined /> 自动盯盘
          <Switch size="small" checked={auto} onChange={persistAuto} />
        </span>
        <span style={{ fontSize: 11, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 4 }}>
          间隔
          <Select
            size="small"
            value={intervalSec}
            style={{ width: 70 }}
            onChange={persistInterval}
            options={[5, 10, 15].map((s) => ({ value: s, label: `${s}秒` }))}
          />
        </span>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "8px 12px" }}>
        {/* Thread watch block */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
            盯盘（当前对话）
          </div>
          {threadId ? (
            <div style={{ display: "flex", gap: 4, marginBottom: 6 }}>
              <Input
                size="small"
                placeholder="代码，如600519"
                value={addCode}
                onChange={(e) => setAddCode(e.target.value)}
                onPressEnter={handleAddWatch}
              />
              <Button size="small" icon={<PlusOutlined />} onClick={handleAddWatch} title="添加盯盘" />
            </div>
          ) : null}
          {watches.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 11, lineHeight: "18px" }}>
              对话中分析过的股票会自动加入盯盘，行情/信号变化时会推送更新建议
            </div>
          ) : watches.map((w) => {
            const q: StockQuote | undefined = liveWatchQuotes[w.code];
            const sig = watchSignals[w.code];
            const rating = sig?.rating || w.last_rating;
            const isUp = q ? q.change_pct >= 0 : true;
            return (
              <div key={w.code} style={{ padding: "6px 0", borderBottom: "1px dashed var(--border-color)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 500 }}>
                    {w.name || w.code} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>{w.code}</span>
                  </span>
                  <span style={{ display: "flex", gap: 2, alignItems: "center" }}>
                    <Tooltip title={sig?.summary || rating}>
                      {ratingTag(rating)}
                    </Tooltip>
                    <Button type="text" size="small" loading={busy[w.code]} icon={<ReloadOutlined />} onClick={() => handleRefreshWatch(w.code)} title="刷新建议" />
                    <Button type="text" size="small" icon={<DeleteOutlined />} onClick={() => handleRemoveWatch(w.code)} title="取消盯盘" />
                  </span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
                  <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>
                    {q ? q.price.toFixed(2) : w.last_price ? w.last_price.toFixed(2) : "--"}
                  </span>
                  <span style={{ fontSize: 11, color: isUp ? "#e03131" : "#2f9e44" }}>
                    {q ? `${q.change_pct >= 0 ? "+" : ""}${q.change_pct.toFixed(2)}%` : "--"}
                  </span>
                </div>
                {sig && (
                  <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2 }}>
                    得分 {sig.score.toFixed(2)} · 置信度 {sig.confidence.toFixed(2)}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Watchlist block */}
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)", marginBottom: 6 }}>
            自选股
          </div>
          {items.length === 0 ? (
            <div style={{ color: "var(--text-muted)", fontSize: 12, textAlign: "center", marginTop: 24 }}>
              暂无自选股，先在上方搜索添加
            </div>
          ) : items.map((item) => {
            const q: StockQuote | undefined = liveQuotes[item.code];
            const sig = signals[item.code];
            const isUp = q ? q.change_pct >= 0 : true;
            return (
              <div key={item.code} style={{ padding: "8px 0", borderBottom: "1px solid var(--border-color)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontSize: 12, color: "var(--text-primary)", fontWeight: 500 }}>
                    {item.name} <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>{item.code}</span>
                  </span>
                  {sig ? (
                    <Tooltip title={sig.summary || `${sig.rating}（得分 ${sig.score}，置信度 ${sig.confidence}）`}>
                      {ratingTag(sig.rating)}
                    </Tooltip>
                  ) : (
                    <Tag style={{ margin: 0 }}>--</Tag>
                  )}
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 4 }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>
                    {q ? q.price.toFixed(2) : "--"}
                  </span>
                  <span style={{ fontSize: 11, color: isUp ? "#e03131" : "#2f9e44" }}>
                    {q ? `${q.change_pct >= 0 ? "+" : ""}${q.change_pct.toFixed(2)}%` : "--"}
                  </span>
                </div>
                {sig && (
                  <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>
                    得分 {sig.score.toFixed(2)} · 置信度 {sig.confidence.toFixed(2)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
