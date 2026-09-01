import { create } from "zustand";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface AppState {
  // Auth
  isLoggedIn: boolean;
  setLoggedIn: (v: boolean) => void;

  // Chat
  messages: ChatMessage[];
  input: string;
  loading: boolean;
  threadId: string | null;
  setInput: (v: string) => void;
  setLoading: (v: boolean) => void;
  addMessage: (msg: ChatMessage) => void;
  updateLastAssistant: (content: string) => void;
  setThreadId: (id: string | null) => void;
  clearMessages: () => void;

  // Market
  currentStock: { code: string; name: string; market: string } | null;
  setCurrentStock: (s: any) => void;
}

export const useStore = create<AppState>((set, get) => ({
  isLoggedIn: false,
  setLoggedIn: (v) => set({ isLoggedIn: v }),

  messages: [],
  input: "",
  loading: false,
  threadId: null,
  setInput: (v) => set({ input: v }),
  setLoading: (v) => set({ loading: v }),
  addMessage: (msg) => set({ messages: [...get().messages, msg] }),
  updateLastAssistant: (content) => {
    const msgs = [...get().messages];
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].role === "assistant") {
        msgs[i] = { ...msgs[i], content };
        break;
      }
    }
    set({ messages: msgs });
  },
  setThreadId: (id) => set({ threadId: id }),
  clearMessages: () => set({ messages: [], threadId: null }),

  currentStock: null,
  setCurrentStock: (s) => set({ currentStock: s }),
}));