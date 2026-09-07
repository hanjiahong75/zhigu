import { Typography, Spin, Input } from "antd";
import { SendOutlined, RobotOutlined, UserOutlined } from "@ant-design/icons";
import { Button, Tag } from "antd";
import ThreadSidebar from "../components/ThreadSidebar";
import ChatStockCard from "../components/ChatStockCard";
import LiveMarketPanel from "../components/LiveMarketPanel";
import { useChat, renderMarkdown } from "../api/ChatContext";

const { Text } = Typography;

export default function HomePage() {
  const {
    messages, input, setInput, loading, streaming, handleSend, stopGeneration, bottomRef,
  } = useChat();

  const suggestions = [
    "茅台现在怎么样？",
    "我的持仓风险如何？",
    "半导体板块怎么看？",
    "帮我看一下 300308 的买卖信号",
  ];

  const fmtTime = (iso?: string) => {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div style={{ flex: 1, display: "flex", overflow: "hidden", position: "relative" }}>
      {/* Left: Thread sidebar */}
      <ThreadSidebar />

      {/* Center: Chat conversation */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden" }}>
        {/* Chat messages — scrollable */}
        <div style={{
          flex: 1, overflow: "auto", padding: "12px 24px",
          display: "flex", flexDirection: "column", gap: 12,
        }}>
          {messages.length === 0 && !loading && (
            <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 13, marginTop: 40, lineHeight: "22px" }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🤖</div>
              <div>我是知股，你的AI投研助手</div>
            <div style={{ marginTop: 8, fontSize: 11 }}>
              试着问我："茅台现在怎么样？" "我的持仓风险如何？" "半导体板块怎么看？"
            </div>
            <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8, alignItems: "center" }}>
              {suggestions.map((s) => (
                <Button key={s} size="small" onClick={() => handleSend(s)} style={{ borderRadius: 16, maxWidth: 360 }}>
                  {s}
                </Button>
              ))}
            </div>
          </div>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={msg.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"}
              style={{
                display: "flex", gap: 10,
                flexDirection: msg.role === "user" ? "row-reverse" : "row",
              }}
            >
              <div style={{
                width: 30, height: 30, borderRadius: "50%", flexShrink: 0,
                background: msg.role === "user" ? "#1677ff" : "#52c41a",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                {msg.role === "user"
                  ? <UserOutlined style={{ color: "#fff", fontSize: 14 }} />
                  : <RobotOutlined style={{ color: "#fff", fontSize: 14 }} />}
              </div>
              <div style={{ maxWidth: "95%", minWidth: 0 }}>
                {msg.role === "assistant" && (msg.stock_data as any)?.source === "realtime" && (
                  <div style={{ marginBottom: 4, display: "flex", gap: 6, alignItems: "center" }}>
                    <Tag color="orange" style={{ margin: 0 }}>⚠ 实时更新</Tag>
                    {(msg.stock_data as any)?.signal_update && (
                      <Text style={{ fontSize: 11, color: "var(--text-muted)" }}>
                        {((msg.stock_data as any).signal_update.old_rating || "观望")} → {(msg.stock_data as any).signal_update.new_rating}
                      </Text>
                    )}
                  </div>
                )}
                <div style={{
                  padding: "10px 16px", borderRadius: 12,
                  background: msg.role === "user" ? "var(--bubble-user-bg)" : "var(--bubble-ai-bg)",
                  border: msg.role === "user" ? "1px solid var(--bubble-user-border)" : "1px solid var(--bubble-ai-border)",
                  fontSize: 13, lineHeight: "20px", color: "var(--bubble-ai-text)",
                  display: "inline-block", maxWidth: "100%",
                }}>
                  {msg.role === "assistant"
                    ? <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                    : <Text style={{ color: "var(--bubble-user-text)" }}>{msg.content}</Text>}
                </div>
                <div style={{
                  fontSize: 10, color: "var(--text-muted)", marginTop: 2,
                  textAlign: msg.role === "user" ? "right" : "left",
                }}>
                  {fmtTime(msg.created_at)}
                </div>
                {msg.role === "assistant" && msg.stock_data?.kline && msg.stock_data?.quote && (
                  <ChatStockCard
                    stockCode={msg.stock_data.stock_code || msg.stock_code}
                    stockName={msg.stock_data.stock_name || msg.stock_name}
                    market={msg.stock_data.market || "sz"}
                    quote={msg.stock_data.quote}
                    initialKline={msg.stock_data.kline}
                    initialIndicators={msg.stock_data.indicators || null}
                  />
                )}
              </div>
            </div>
          ))}
          {loading && !streaming && (
            <div style={{ display: "flex", gap: 10 }}>
              <div style={{
                width: 30, height: 30, borderRadius: "50%", background: "#52c41a",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <RobotOutlined style={{ color: "#fff", fontSize: 14 }} />
              </div>
              <div style={{
                padding: "10px 20px", borderRadius: 12,
                background: "var(--bubble-ai-bg)", border: "1px solid var(--bubble-ai-border)",
                fontSize: 13,
              }}>
                <Spin size="small" /> 思考中...
              </div>
            </div>
          )}
          {streaming && (
            <div style={{ display: "flex", gap: 10, alignItems: "center", paddingLeft: 40 }}>
              <div style={{ width: 8, height: 16, background: "#1677ff", animation: "caretBlink 1s step-end infinite" }} />
              <Text style={{ fontSize: 12, color: "var(--text-muted)" }}>正在生成…</Text>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div style={{
          padding: "10px 24px", borderTop: "1px solid var(--border-color)",
          background: "var(--bg-secondary)", flexShrink: 0,
          display: "flex", gap: 8, alignItems: "center",
        }}>
          <Input.Search
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onSearch={(v) => handleSend(v)}
            placeholder="输入你的问题，如：茅台现在怎么样？"
            enterButton={<SendOutlined />}
            loading={loading}
            size="large"
          />
          {streaming && (
            <Button danger size="large" onClick={stopGeneration}>停止</Button>
          )}
        </div>
      </div>

      {/* Right: live quotes + signals */}
      <LiveMarketPanel />
    </div>
  );
}
