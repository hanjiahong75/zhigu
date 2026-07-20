import { createContext, useContext, useState, useEffect, useRef, type ReactNode } from "react";
import { App } from "antd";
import {
  sendChatMessage, getChatThreads, getChatThreadMessages,
  updateChatThread, deleteChatThread,
} from "./client";
import type { StockQuote, KlineItem } from "../types";

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

export interface Thread {
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

interface ChatContextType {
  messages: ChatMsg[];
  input: string;
  setInput: (v: string) => void;
  loading: boolean;
  threadId: string;
  setThreadId: (v: string) => void;
  threads: Thread[];
  contextMenu: ContextMenuState;
  setContextMenu: (v: ContextMenuState) => void;
  renameModal: { visible: boolean; threadId: string; title: string };
  setRenameModal: (v: { visible: boolean; threadId: string; title: string }) => void;
  searchRefresh: number;
  setSearchRefresh: (v: number | ((n: number) => number)) => void;
  loadThreads: () => Promise<void>;
  loadThread: (tid: string) => Promise<void>;
  newThread: () => void;
  handleContextMenu: (e: React.MouseEvent, tid: string) => void;
  handlePin: () => Promise<void>;
  handleRename: () => void;
  confirmRename: () => Promise<void>;
  handleDelete: () => Promise<void>;
  handleSend: (value?: string) => Promise<void>;
  bottomRef: React.RefObject<HTMLDivElement | null>;
  contextMenuRef: React.RefObject<HTMLDivElement | null>;
}

const ChatContext = createContext<ChatContextType>(null!);

export function ChatProvider({ children }: { children: ReactNode }) {
  const { modal, message: msg } = App.useApp();
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState("");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ visible: false, x: 0, y: 0, threadId: "" });
  const [renameModal, setRenameModal] = useState<{ visible: boolean; threadId: string; title: string }>({ visible: false, threadId: "", title: "" });
  const [searchRefresh, setSearchRefresh] = useState(0);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const contextMenuRef = useRef<HTMLDivElement | null>(null);

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
    try { const data = await getChatThreads(); setThreads(data); } catch { /* silent */ }
  };

  const loadThread = async (tid: string) => {
    setThreadId(tid);
    setMessages([]);
    try { const msgs = await getChatThreadMessages(tid); setMessages(msgs); } catch { /* silent */ }
  };

  const newThread = () => {
    setThreadId("");
    setMessages([]);
  };

  const handleContextMenu = (e: React.MouseEvent, tid: string) => {
    e.preventDefault();
    setContextMenu({ visible: true, x: e.clientX, y: e.clientY, threadId: tid });
  };

  const handlePin = async () => {
    const t = threads.find((th) => th.id === contextMenu.threadId);
    if (!t) return;
    try { await updateChatThread(contextMenu.threadId, { pinned: !t.pinned }); loadThreads(); } catch { msg.error("操作失败"); }
    setContextMenu((p) => ({ ...p, visible: false }));
  };

  const handleRename = () => {
    const t = threads.find((th) => th.id === contextMenu.threadId);
    setRenameModal({ visible: true, threadId: contextMenu.threadId, title: t?.title || "" });
    setContextMenu((p) => ({ ...p, visible: false }));
  };

  const confirmRename = async () => {
    try { await updateChatThread(renameModal.threadId, { title: renameModal.title }); loadThreads(); } catch { msg.error("重命名失败"); }
    setRenameModal({ visible: false, threadId: "", title: "" });
  };

  const handleDelete = async () => {
    modal.confirm({
      title: "删除对话", content: "删除后无法恢复，确定删除？",
      okText: "删除", okType: "danger", cancelText: "取消",
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

  const handleSend = async (value?: string) => {
    const text = (value || input).trim();
    if (!text || loading) return;
    setInput("");
    setLoading(true);
    const tempId = Date.now();
    setMessages((prev) => [...prev, { id: tempId, role: "user", content: text, stock_code: "", stock_name: "", created_at: new Date().toISOString() }]);
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
      setMessages((prev) => [...prev, { id: tempId + 1, role: "assistant", content: "抱歉，请求失败：" + (e.message || "未知错误"), stock_code: "", stock_name: "", created_at: new Date().toISOString() }]);
    } finally { setLoading(false); }
  };

  return (
    <ChatContext.Provider value={{
      messages, input, setInput, loading, threadId, setThreadId, threads,
      contextMenu, setContextMenu, renameModal, setRenameModal,
      searchRefresh, setSearchRefresh,
      loadThreads, loadThread, newThread,
      handleContextMenu, handlePin, handleRename, confirmRename, handleDelete,
      handleSend, bottomRef, contextMenuRef,
    }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  return useContext(ChatContext);
}

export function renderMarkdown(text: string): string {
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
