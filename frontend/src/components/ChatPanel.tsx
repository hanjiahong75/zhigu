import { useState, useEffect, useRef } from "react";
import { Input, Button, Spin, Typography, Modal, App, message } from "antd";
import {
  SendOutlined, RobotOutlined, UserOutlined, PlusOutlined,
  PushpinOutlined, PushpinFilled, EditOutlined, DeleteOutlined,
  StockOutlined, WalletOutlined,
} from "@ant-design/icons";
import ChatStockCard from "./ChatStockCard";
import StockSearch from "./StockSearch";
import PortfolioPanel from "./PortfolioPanel";
import {
  sendChatMessage, getChatThreads, getChatThreadMessages,
  updateChatThread, deleteChatThread,
} from "../api/client";
import type { StockQuote, KlineItem } from "../types";

const { Text } = Typography;

type SidebarTab = "threads" | "portfolio";

interface ChatMsg {
  id: number;
  role: string;
  content: string;
  stock_code: string;
  stock_name: string;
  stock_data?: {
    stock_code?: string;
    stock_name?: string;
    market?: string;
    quote?: StockQuote;
    kline?: KlineItem[];
    indicators?: any;
  } | null;
  created_at: string;
}

interface Thread {
  id: string;
  title: string;
  pinned?: boolean;
  updated_at: string;
  last_message: string;
}

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  threadId: string;
}

function renderMarkdown(text: string): string {
  let html = text
    .replace(/^### (.+)$/gm, '<h3 style="color:#1677ff;font-size:14px;margin:10px 0 4px;border-bottom:1px solid #e8f4ff;padding-bottom:4px;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size:15px;margin:12px 0 6px;">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br/>");

  html = html.replace(
    /\|(.+)\|/g,
    (match) => {
      if (match.includes("---")) return "";
      const cells = match.split("|").filter((c) => c.trim());
      const isHeader = cells.length > 0 && cells.every((c) => /^[\s\u4e00-\u9fff]+$/.test(c.trim()));
      const tag = isHeader ? "th" : "td";
      const row = cells.map((c) => `<${tag}>${c.trim()}</${tag}>`).join("");
      return `<tr>${row}</tr>`;
    }
  );

  html = `<p>${html}</p>`;
  html = html.replace(
    /(<tr>.*?<\/tr>)/gs,
    (table) => `<table style="width:100%;border-collapse:collapse;margin:6px 0;font-size:12px;"><tbody>${table}</tbody></table>`
  );
  return html;
}


export default function ChatPanel() {
  const { modal, message: msg } = App.useApp();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState("");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ visible: false, x: 0, y: 0, threadId: "" });
  const [renameModal, setRenameModal] = useState<{ visible: boolean; threadId: string; title: string }>({ visible: false, threadId: "", title: "" });
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("threads");
  const [searchRefresh, setSearchRefresh] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const contextMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => { loadThreads(); }, []);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (contextMenuRef.current && !contextMenuRef.current.contains(e.target as Node)) {
        setContextMenu((p) => ({ ...p, visible: false }));
      }
    };
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, []);
  const loadThreads = async () => {
    try {
      const data = await getChatThreads();
      setThreads(data);
    } catch { /* silent */ }
  };

  const loadThread = async (tid: string) => {
    setThreadId(tid);
    setMessages([]);
    try {
      const msgs = await getChatThreadMessages(tid);
      setMessages(msgs);
    } catch { /* silent */ }
  };

  const newThread = () => {
    setThreadId("");
    setMessages([]);
    setSidebarTab("threads");
  };

  const handleContextMenu = (e: React.MouseEvent, tid: string) => {
    e.preventDefault();
    setContextMenu({ visible: true, x: e.clientX, y: e.clientY, threadId: tid });
  };

  const handlePin = async () => {
    const t = threads.find((th) => th.id === contextMenu.threadId);
    if (!t) return;
    try {
      await updateChatThread(contextMenu.threadId, { pinned: !t.pinned });
      loadThreads();
    } catch { msg.error("操作失败"); }
    setContextMenu((p) => ({ ...p, visible: false }));
  };

  const handleRename = () => {
    const t = threads.find((th) => th.id === contextMenu.threadId);
    setRenameModal({ visible: true, threadId: contextMenu.threadId, title: t?.title || "" });
    setContextMenu((p) => ({ ...p, visible: false }));
  };

  const confirmRename = async () => {
    try {
      await updateChatThread(renameModal.threadId, { title: renameModal.title });
      loadThreads();
    } catch { msg.error("重命名失败"); }
    setRenameModal({ visible: false, threadId: "", title: "" });
  };

  const handleDelete = async () => {
    modal.confirm({
      title: "删除对话",
      content: "删除后无法恢复，确定删除？",
      okText: "删除",
      okType: "danger",
      cancelText: "取消",
      onOk: async () => {
        try {
          await deleteChatThread(contextMenu.threadId);
          if (threadId === contextMenu.threadId) newThread();
          loadThreads();
        } catch { msg.error("删除失败"); }
      },
    });
    setContextMenu((p) => ({ ...p, visible: false }));
  };

  const handleSend = async (value: string) => {
    const text = value?.trim() || input.trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);

    const tempId = Date.now();
    setMessages((prev) => [...prev, {
      id: tempId, role: "user", content: text,
      stock_code: "", stock_name: "", created_at: new Date().toISOString(),
    }]);

    try {
      const data = await sendChatMessage(text, threadId);
      if (data.thread_id && !threadId) { setThreadId(data.thread_id); loadThreads(); }

      setMessages((prev) => [...prev, {
        id: data.message_id || tempId + 1, role: "assistant",
        content: data.reply,
        stock_code: data.stock_code || "", stock_name: data.stock_name || "",
        stock_data: data.type === "stock" ? {
          stock_code: data.stock_code, stock_name: data.stock_name,
          market: data.market, quote: data.quote,
          kline: data.kline, indicators: data.indicators,
        } : null,
        created_at: new Date().toISOString(),
      }]);
    } catch (e: any) {
      setMessages((prev) => [...prev, {
        id: tempId + 1, role: "assistant",
        content: "抱歉，请求失败：" + (e.message || "未知错误"),
        stock_code: "", stock_name: "", created_at: new Date().toISOString(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      {/* Context menu */}
      {contextMenu.visible && (
        <div ref={contextMenuRef} style={{
          position: "fixed", left: contextMenu.x, top: contextMenu.y,
          background: "var(--bg-secondary)", border: "1px solid #e8e8e8", borderRadius: 8,
          boxShadow: "0 4px 12px rgba(0,0,0,0.12)", zIndex: 1000,
          minWidth: 140, padding: "4px 0",
        }}>
          {(() => {
            const t = threads.find((th) => th.id === contextMenu.threadId);
            return (
              <div
                onClick={handlePin}
                style={menuItemStyle}>
                {t?.pinned ? <PushpinFilled style={{ color: "var(--bubble-user-text)" }} /> : <PushpinOutlined />}
                <span style={{ marginLeft: 8 }}>{t?.pinned ? "取消置顶" : "置顶"}</span>
              </div>
            );
          })()}
          <div onClick={handleRename} style={menuItemStyle}>
            <EditOutlined />
            <span style={{ marginLeft: 8 }}>重命名</span>
          </div>
          <div style={{ borderTop: "1px solid #f0f0f0", margin: "4px 0" }} />
          <div onClick={handleDelete} style={{ ...menuItemStyle, color: "#ef4444" }}>
            <DeleteOutlined />
            <span style={{ marginLeft: 8 }}>删除</span>
          </div>
        </div>
      )}

      {/* Rename modal */}
      <Modal
        title="重命名对话"
        open={renameModal.visible}
        onOk={confirmRename}
        onCancel={() => setRenameModal({ visible: false, threadId: "", title: "" })}
        okText="确定"
        cancelText="取消"
      >
        <Input
          value={renameModal.title}
          onChange={(e) => setRenameModal((p) => ({ ...p, title: e.target.value }))}
          placeholder="输入新名称"
          onPressEnter={confirmRename}
        />
      </Modal>

      {/* Thread sidebar */}
      <div style={{
        width: 240, borderRight: "1px solid var(--border-color)", background: "var(--bg-sidebar)",
        display: "flex", flexDirection: "column", overflow: "hidden", flexShrink: 0,
      }}>
        {/* Search bar */}
        <div style={{ padding: "8px" }}>
          <StockSearch
            onSelect={(code, name, market) => {
              /* Auto-create new thread and chat about this stock */
              setThreadId("");
              setMessages([]);
              setInput(name + "(" + code + ") 怎么样？");
              setSidebarTab("threads");
            }}
            onWatchlistChange={() => setSearchRefresh((n) => n + 1)}
            compact
          />
        </div>
        <div style={{ display: "flex", borderBottom: "1px solid var(--border-color)" }}>
          <button
            className="btn-pulse" onClick={() => setSidebarTab("threads")}
            style={{
              flex: 1, padding: "8px 0", border: "none", background: sidebarTab === "threads" ? "var(--thread-active-bg)" : "transparent",
              cursor: "pointer", fontSize: 12, fontWeight: sidebarTab === "threads" ? 600 : 400,
              color: sidebarTab === "threads" ? "#1677ff" : "#666",
              borderBottom: sidebarTab === "threads" ? "2px solid #1677ff" : "2px solid transparent",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
            }}
          >
            <StockOutlined /> 对话
          </button>
          <button
            className="btn-pulse" onClick={() => setSidebarTab("portfolio")}
            style={{
              flex: 1, padding: "8px 0", border: "none", background: sidebarTab === "portfolio" ? "var(--thread-active-bg)" : "transparent",
              cursor: "pointer", fontSize: 12, fontWeight: sidebarTab === "portfolio" ? 600 : 400,
              color: sidebarTab === "portfolio" ? "#1677ff" : "#666",
              borderBottom: sidebarTab === "portfolio" ? "2px solid #1677ff" : "2px solid transparent",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
            }}
          >
            <WalletOutlined /> 持仓
          </button>
        </div>

        {sidebarTab === "threads" && (
          <>
            <div style={{ padding: "8px", borderBottom: "1px solid var(--border-color)" }}>
              <Button type="primary" size="small" block icon={<PlusOutlined />} onClick={newThread}>
                新建对话
              </Button>
            </div>
            <div style={{ flex: 1, overflow: "auto", padding: "4px" }}>
               {(() => {
                 const pinnedThreads = threads.filter(t => t.pinned);
                 const unpinnedThreads = threads.filter(t => !t.pinned);
                 const renderThread = (t: Thread) => (
                   <div
                     key={t.id}
                     onClick={() => loadThread(t.id)}
                     onContextMenu={(e) => handleContextMenu(e, t.id)}
                     style={{
                       padding: "8px", cursor: "pointer", borderRadius: 6, marginBottom: 2,
                       background: t.id === threadId ? "var(--thread-active-bg)" : "transparent",
                       borderLeft: t.id === threadId ? "3px solid #1677ff" : "3px solid transparent", border: "1px solid transparent",
                       display: "flex", alignItems: "center", gap: 4,
                     }}
                   >
                     {t.pinned && <PushpinFilled style={{ color: "var(--bubble-user-text)", fontSize: 10, flexShrink: 0 }} />}
                     <div style={{ flex: 1, minWidth: 0 }}>
                       <div style={{ fontSize: 12, fontWeight: t.id === threadId ? 600 : 400, color: "var(--text-primary)",
                         overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                         {t.title || "新对话"}
                       </div>
                       <div style={{ fontSize: 10, color: "var(--text-muted)", marginTop: 2,
                         overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                         {t.last_message?.slice(0, 30)}
                       </div>
                     </div>
                   </div>
                 );
                 return (
                   <>
                     {pinnedThreads.map(renderThread)}
                     {pinnedThreads.length > 0 && unpinnedThreads.length > 0 && (
                       <div style={{
                         borderTop: "1px solid var(--border-color)", margin: "4px 0",
                         fontSize: 10, color: "var(--text-muted)", padding: "2px 8px",
                       }}>常规对话</div>
                     )}
                     {unpinnedThreads.map(renderThread)}
                   </>
                 );
               })()}
            </div>
          </>
        )}

        {sidebarTab === "portfolio" && (
          <div style={{ flex: 1, overflow: "auto" }}>
            <PortfolioPanel />
          </div>
        )}
      </div>

      {/* Chat area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div style={{ flex: 1, overflow: "auto", padding: "16px 24px", display: "flex", flexDirection: "column", gap: 12 }}>
          {messages.length === 0 && !loading && (
            <div style={{ textAlign: "center", color: "var(--text-muted)", fontSize: 13, marginTop: 60, padding: "0 24px", lineHeight: "22px" }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🤖</div>
              <div>我是知股，你的AI投研助手</div>
              <div style={{ marginTop: 8, fontSize: 11, color: "var(--text-muted)" }}>
                试着问我："茅台现在怎么样？" "新能源板块怎么看？" "今天大盘如何？"
              </div>
            </div>
          )}
          {messages.map((msg) => (
            <div key={msg.id} className={msg.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"} style={{ display: "flex", gap: 10, flexDirection: msg.role === "user" ? "row-reverse" : "row" }}>
              <div style={{ width: 30, height: 30, borderRadius: "50%", flexShrink: 0, background: msg.role === "user" ? "#1677ff" : "#52c41a", display: "flex", alignItems: "center", justifyContent: "center" }}>
                {msg.role === "user" ? <UserOutlined style={{ color: "#fff", fontSize: 14 }} /> : <RobotOutlined style={{ color: "#fff", fontSize: 14 }} />}
              </div>
              <div style={{ maxWidth: "95%", minWidth: 0 }}>
                <div style={{ padding: "10px 16px", borderRadius: 12, background: msg.role === "user" ? "var(--bubble-user-bg)" : "var(--bubble-ai-bg)", border: msg.role === "user" ? "1px solid var(--bubble-user-border)" : "1px solid var(--bubble-ai-border)", fontSize: 13, lineHeight: "20px", color: "var(--bubble-ai-text)", display: "inline-block", maxWidth: "100%" }}>
                  {msg.role === "assistant" ? <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} /> : <Text style={{ color: "var(--bubble-user-text)" }}>{msg.content}</Text>}
                </div>
                {msg.role === "assistant" && msg.stock_data?.kline && msg.stock_data?.quote && (
                  <ChatStockCard stockCode={msg.stock_data.stock_code || msg.stock_code} stockName={msg.stock_data.stock_name || msg.stock_name} market={msg.stock_data.market || "sz"} quote={msg.stock_data.quote} initialKline={msg.stock_data.kline} initialIndicators={msg.stock_data.indicators || null} />
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div style={{ display: "flex", gap: 10 }}>
              <div style={{ width: 30, height: 30, borderRadius: "50%", background: "#52c41a", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <RobotOutlined style={{ color: "#fff", fontSize: 14 }} />
              </div>
              <div style={{ padding: "10px 20px", borderRadius: 12, background: "var(--bubble-ai-bg)", border: "1px solid var(--bubble-ai-border)", fontSize: 13 }}>
                <Spin size="small" /> 思考中...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <div style={{ padding: "12px 24px", borderTop: "1px solid var(--border-color)", background: "var(--bg-secondary)" }}>
          <Input.Search value={input} onChange={(e) => setInput(e.target.value)} onSearch={handleSend} placeholder="输入你的问题，如：茅台现在怎么样？" enterButton={<SendOutlined />} loading={loading} size="large" />
        </div>
      </div>
    </div>
  );
}

const menuItemStyle: React.CSSProperties = {
  padding: "6px 12px", cursor: "pointer", fontSize: 12, display: "flex",
  alignItems: "center", color: "var(--text-primary)",
};



