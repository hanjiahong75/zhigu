import { createContext, useContext, useState, useEffect, useRef, type ReactNode } from "react";
import { App } from "antd";
import {
  sendChatMessage, sendChatMessageStream, getChatThreads, getChatThreadMessages,
  updateChatThread, deleteChatThread,
} from "./client";
import type { ChatStreamStockData } from "./client";

interface ChatMsg {
  id: number;
  role: string;
  content: string;
  stock_code: string;
  stock_name: string;
  stock_data?: ChatStreamStockData | null;
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
  streaming: boolean;
  stopGeneration: () => void;
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
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
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

  // Subscribe to the current thread's realtime event stream (M5):
  // "advice_update" events appear in the conversation as ⚠ 实时更新 messages.
  useEffect(() => {
    if (!threadId) return;
    const auto = localStorage.getItem("zhigu_watch_auto") !== "off";
    if (!auto) return;
    const interval = Number(localStorage.getItem("zhigu_watch_interval") || "10") || 10;
    const es = new EventSource(`/api/chat/threads/${encodeURIComponent(threadId)}/stream?interval=${interval}`);
    es.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === "advice_update") {
          setMessages((prev) => [...prev, {
            id: Date.now(),
            role: "assistant",
            content: msg.content || "",
            stock_code: msg.code || "",
            stock_name: msg.name || "",
            stock_data: {
              stock_code: msg.code,
              stock_name: msg.name,
              source: "realtime",
              signal_update: {
                old_rating: msg.old_rating,
                new_rating: msg.new_rating,
                ts: msg.ts,
              },
            },
            created_at: new Date().toISOString(),
          }]);
          loadThreads();
        }
      } catch {
        // ignore malformed frames
      }
    };
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId]);

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
    const assistantId = tempId + 1;
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "", stock_code: "", stock_name: "", stock_data: null, created_at: new Date().toISOString() }]);

    const controller = new AbortController();
    abortRef.current = controller;
    setStreaming(true);
    let received = false;

    const finalize = (content?: string, info?: { message_id?: number }) => {
      setMessages((prev) => prev.map((m) =>
        m.id === assistantId
          ? { ...m, id: info?.message_id ?? m.id, content: content !== undefined ? content : m.content }
          : m
      ));
    };

    try {
      await sendChatMessageStream(text, threadId, {
        onMeta: (meta) => {
          received = true;
          if (meta.thread_id && !threadId) { setThreadId(meta.thread_id); loadThreads(); }
        },
        onDelta: (content) => {
          received = true;
          setMessages((prev) => prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + content } : m
          ));
        },
        onStockData: (sd) => {
          received = true;
          setMessages((prev) => prev.map((m) =>
            m.id === assistantId
              ? { ...m, stock_data: sd, stock_code: sd?.stock_code || m.stock_code, stock_name: sd?.stock_name || m.stock_name }
              : m
          ));
        },
        onDone: (info) => {
          received = true;
          finalize(info.content, { message_id: info.message_id });
        },
        onError: (message) => {
          received = true;
          setMessages((prev) => prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content || `抱歉，${message}` } : m
          ));
        },
      }, controller.signal);
    } catch (e: any) {
      if (e?.name === "AbortError") {
        finalize();
        setMessages((prev) => prev.map((m) =>
          m.id === assistantId && m.content ? { ...m, content: m.content + "\n\n（已停止生成）" } : m
        ));
      } else if (!received) {
        // Stream failed before any event -> fall back to non-streaming
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
        try {
          const data = await sendChatMessage(text, threadId);
          if (data.thread_id && !threadId) { setThreadId(data.thread_id); loadThreads(); }
          setMessages((prev) => [...prev, {
            id: data.message_id || assistantId, role: "assistant",
            content: data.reply,
            stock_code: data.stock_code || "", stock_name: data.stock_name || "",
            stock_data: data.type === "stock" ? {
              stock_code: data.stock_code, stock_name: data.stock_name,
              market: data.market, quote: data.quote,
              kline: data.kline, indicators: data.indicators,
            } : null,
            created_at: new Date().toISOString(),
          }]);
        } catch (e2: any) {
          setMessages((prev) => [...prev, { id: Date.now(), role: "assistant", content: "抱歉，请求失败：" + (e2.message || "未知错误"), stock_code: "", stock_name: "", created_at: new Date().toISOString() }]);
        }
      }
    } finally { setLoading(false); }
    setStreaming(false);
    abortRef.current = null;
  };

  const stopGeneration = () => {
    abortRef.current?.abort();
  };

  return (
    <ChatContext.Provider value={{
      messages, input, setInput, loading, threadId, setThreadId, threads,
      contextMenu, setContextMenu, renameModal, setRenameModal,
      searchRefresh, setSearchRefresh,
      loadThreads, loadThread, newThread,
      handleContextMenu, handlePin, handleRename, confirmRename, handleDelete,
      handleSend, streaming, stopGeneration, bottomRef, contextMenuRef,
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
