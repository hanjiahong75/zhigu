const API_BASE = "/api";

export const PERIODS: Record<string, string> = {
  "1": "1分", "5": "5分", "15": "15分", "30": "30分", "60": "60分", "120": "120分",
  "101": "日K", "102": "周K", "103": "月K", "104": "季K", "105": "年K",
};

export async function searchStocks(keyword: string) {
  const resp = await fetch(`${API_BASE}/search?keyword=${encodeURIComponent(keyword)}`);
  return resp.json();
}

export async function getMarketIndices() {
  const resp = await fetch(`${API_BASE}/indices`);
  return resp.json();
}

export async function getStockQuote(code: string, market = "sz") {
  const resp = await fetch(`${API_BASE}/quote?code=${encodeURIComponent(code)}&market=${market}`);
  if (!resp.ok) throw new Error("Stock not found");
  return resp.json();
}

export async function getKlineData(code: string, market = "sz", days = 10000, klt = "101") {
  const resp = await fetch(`${API_BASE}/kline?code=${encodeURIComponent(code)}&market=${market}&days=${days}&klt=${klt}`);
  return resp.json();
}

export async function getIndicators(code: string, market = "sz", days = 10000, klt = "101") {
  const resp = await fetch(`${API_BASE}/indicators?code=${encodeURIComponent(code)}&market=${market}&days=${days}&klt=${klt}`);
  if (!resp.ok) throw new Error("Indicators not available");
  return resp.json();
}

export async function getIntraday(code: string, date: string) {
  const resp = await fetch(`${API_BASE}/intraday?code=${encodeURIComponent(code)}&date=${date}`);
  if (!resp.ok) throw new Error("No intraday data");
  return resp.json();
}

export async function getAnalysis(code: string, market = "sz", userMessage = "") {
  const params = `code=${encodeURIComponent(code)}&market=${market}&user_message=${encodeURIComponent(userMessage)}`;
  const resp = await fetch(`${API_BASE}/analyze?${params}`);
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || "Analysis failed");
  }
  return resp.json();
}

export async function getWatchlist() {
  const resp = await fetch(`${API_BASE}/watchlist`);
  return resp.json();
}

export async function getWatchlistQuotes(codes: string[]) {
  const params = codes.map(c => `codes=${encodeURIComponent(c)}`).join("&");
  const resp = await fetch(`${API_BASE}/watchlist/quotes?${params}`);
  if (!resp.ok) return [];
  return resp.json();
}

export async function addToWatchlist(code: string, name: string, market = "sz") {
  const resp = await fetch(
    `${API_BASE}/watchlist?code=${encodeURIComponent(code)}&name=${encodeURIComponent(name)}&market=${market}`,
    { method: "POST" }
  );
  return resp.json();
}

export async function removeFromWatchlist(code: string) {
  const resp = await fetch(
    `${API_BASE}/watchlist?code=${encodeURIComponent(code)}`,
    { method: "DELETE" }
  );
  return resp.json();
}

export async function getChatHistory(limit = 50) {
  const resp = await fetch(`${API_BASE}/conversations?limit=${limit}`);
  return resp.json();
}

// --- Chat Panel APIs ---

export async function sendChatMessage(message: string, threadId = "") {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
  });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || "Chat failed");
  }
  return resp.json();
}

export async function getChatThreads() {
  const resp = await fetch(`${API_BASE}/chat/threads`);
  if (!resp.ok) return [];
  return resp.json();
}

export async function getChatThreadMessages(threadId: string) {
  const resp = await fetch(`${API_BASE}/chat/threads/${threadId}`);
  if (!resp.ok) return [];
  return resp.json();
}

export async function updateChatThread(threadId: string, data: { title?: string; pinned?: boolean }) {
  const params = new URLSearchParams();
  if (data.title !== undefined) params.set("title", data.title);
  if (data.pinned !== undefined) params.set("pinned", String(data.pinned));
  const resp = await fetch(`${API_BASE}/chat/threads/${threadId}?${params.toString()}`, { method: "PATCH" });
  if (!resp.ok) throw new Error("Update failed");
  return resp.json();
}

export async function deleteChatThread(threadId: string) {
  const resp = await fetch(`${API_BASE}/chat/threads/${threadId}`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Delete failed");
  return resp.json();
}

// --- Portfolio APIs ---

export async function getPortfolio() {
  const resp = await fetch(`${API_BASE}/portfolio`);
  return resp.json();
}

export async function uploadPortfolioImage(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await fetch(`${API_BASE}/portfolio/upload`, {
    method: "POST",
    body: formData,
  });
  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(err.detail || "Upload failed");
  }
  return resp.json();
}

export async function updatePortfolioItems(items: Array<{
  stock_code: string;
  stock_name: string;
  asset_type?: string;
  quantity: number;
  cost_price: number;
  current_price?: number;
}>) {
  const resp = await fetch(`${API_BASE}/portfolio/items`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!resp.ok) throw new Error("Update failed");
  return resp.json();
}


export async function getPortfolioRisk() {
  const resp = await fetch(`${API_BASE}/portfolio/risk`);
  if (!resp.ok) return { sharpe_ratio: null, max_drawdown: null };
  return resp.json();
}
export async function deletePortfolio() {
  const resp = await fetch(`${API_BASE}/portfolio`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Delete failed");
  return resp.json();
}