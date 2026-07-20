import { Typography, Spin, Input } from "antd";
import { SendOutlined, RobotOutlined, UserOutlined } from "@ant-design/icons";
import PortfolioOverviewCard from "../components/PortfolioOverviewCard";
import ThreadSidebar from "../components/ThreadSidebar";
import ChatStockCard from "../components/ChatStockCard";
import { useChat, renderMarkdown } from "../api/ChatContext";

const { Text } = Typography;

export default function HomePage() {
  const {
    messages, input, setInput, loading, handleSend, bottomRef,
  } = useChat();

  return (
    <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
      {/* Left: Thread sidebar */}
      <ThreadSidebar />

      {/* Right: Portfolio card + Chat */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0, overflow: "hidden" }}>
        {/* Portfolio overview card */}
        <PortfolioOverviewCard />

        {/* Divider */}
        <div style={{
          borderTop: "1px solid var(--border-color)", margin: "0 16px",
          fontSize: 11, color: "var(--text-muted)", textAlign: "center", padding: "4px 0",
        }}>
          AI 投研对话
        </div>

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
          {loading && (
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
          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <div style={{
          padding: "10px 24px", borderTop: "1px solid var(--border-color)",
          background: "var(--bg-secondary)", flexShrink: 0,
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
        </div>
      </div>
    </div>
  );
}