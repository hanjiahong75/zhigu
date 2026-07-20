;
const GLOBAL_MARKETS = ["kr", "jp", "us", "hk"];
function isGlobalMarket(market: string) { return GLOBAL_MARKETS.includes(market); }

const API_BASE = "/api";

export const PERIODS: Record<string, string> = {
  "1": "1分", "5": "5分", "15": "15分", "30": "30分", "60": "60分", "120": "120分",
  "101": "日K", "102": "周K", "103": "月K", "104": "季K", "105": "年K",
};

export async function searchStocks(keyword: string) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 12000);
  try {
    const resp = await fetch(`${API_BASE}/search?keyword=${encodeURIComponent(keyword)}`, {
      signal: controller.signal,
    });
    if (!resp.ok) throw new Error("搜索失败");
    return resp.json();
  } finally {
    clearTimeout(timeout);
  }
}

export async function getMarketIndices() {
  const resp = await fetch(`${API_BASE}/indices`);
  const data = await resp.json();
  return data.indices || [];
}

export async function getStockQuote(code: string, market = "sz") {
  const base = isGlobalMarket(market) ? "/global/quote" : "/quote";
  const resp = await fetch(`${API_BASE}${base}?code=${encodeURIComponent(code)}&market=${market}`);
  if (!resp.ok) throw new Error("Stock not found");
  return resp.json();
}

export async function getKlineData(code: string, market = "sz", days = 10000, klt = "101") {
  const base = isGlobalMarket(market) ? "/global/kline" : "/kline";
  const resp = await fetch(`${API_BASE}${base}?code=${encodeURIComponent(code)}&market=${market}&days=${days}&klt=${klt}`);
  return resp.json();
}

export async function getIndicators(code: string, market = "sz", days = 10000, klt = "101") {
  const base = isGlobalMarket(market) ? "/global/indicators" : "/indicators";
  const resp = await fetch(`${API_BASE}${base}?code=${encodeURIComponent(code)}&market=${market}&days=${days}&klt=${klt}`);
  if (!resp.ok) throw new Error("Indicators not available");
  return resp.json();
}

export async function getIntraday(code: string, date: string, klt = "1") {
  const resp = await fetch(`${API_BASE}/intraday?code=${encodeURIComponent(code)}&date=${date}&klt=${klt}`);
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

export async function getPortfolioDiagnosis() {
  const resp = await fetch(`${API_BASE}/portfolio/diagnosis`);
  if (!resp.ok) return { concentration: null, items: [], summary: "" };
  return resp.json();
}

export async function deletePortfolio() {
  const resp = await fetch(`${API_BASE}/portfolio`, { method: "DELETE" });
  if (!resp.ok) throw new Error("Delete failed");
  return resp.json();
}

export async function getNews(page = 1, limit = 20) {
  const resp = await fetch(`${API_BASE}/news?page=${page}&limit=${limit}&_t=${Date.now()}`);
  if (!resp.ok) return { news: [], total: 0 };
  return resp.json();
}

export async function searchFunds(keyword: string) {
  const resp = await fetch(`${API_BASE}/funds/search?keyword=${encodeURIComponent(keyword)}`);
  if (!resp.ok) return [];
  return resp.json();
}

export async function getFundNav(code: string) {
  const resp = await fetch(`${API_BASE}/funds/nav?code=${encodeURIComponent(code)}`);
  if (!resp.ok) throw new Error("Fund not found");
  return resp.json();
}

export async function getFundRecommendations() {
  const resp = await fetch(`${API_BASE}/funds/recommend`);
  if (!resp.ok) return { hot: [], bond: [], index: [], qdii: [], commodity: [] };
  return resp.json();
}

export async function getFundHoldings(code: string) {
  const resp = await fetch(`${API_BASE}/funds/holdings?code=${encodeURIComponent(code)}`);
  if (!resp.ok) return { stocks: [], industries: [], quarter: "" };
  return resp.json();
}

export async function getGlobalIndices() {
  const resp = await fetch(`${API_BASE}/global-indices`);
  if (!resp.ok) return [];
  return resp.json();
}

// --- User Profile APIs ---

export async function getUserProfile() {
  const resp = await fetch(`${API_BASE}/user/profile`);
  if (!resp.ok) return { investment_style: 'medium_term', risk_preference: 'moderate', focus_industries: '', focus_stocks: '' };
  return resp.json();
}

export async function getAlerts() {
  const resp = await fetch(`${API_BASE}/alerts`);
  if (!resp.ok) return { alerts: [], updated_at: null };
  return resp.json();
}

export async function updateUserProfile(data: {
  investment_style?: string;
  risk_preference?: string;
  focus_industries?: string;
  focus_stocks?: string;
}) {
  const resp = await fetch(`${API_BASE}/user/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error('Update failed');
  return resp.json();
}

// --- Global Market APIs ---

export async function searchGlobalStocks(keyword: string, market = "hk") {
  const resp = await fetch(`${API_BASE}/global/search?keyword=${encodeURIComponent(keyword)}&market=${market}`);
  if (!resp.ok) return { results: [] };
  return resp.json();
}

export async function getGlobalQuote(code: string, market = "hk") {
  const resp = await fetch(`${API_BASE}/global/quote?code=${encodeURIComponent(code)}&market=${market}`);
  if (!resp.ok) throw new Error("Quote not found");
  return resp.json();
}

export async function getGlobalKline(code: string, market = "hk", days = 120) {
  const resp = await fetch(`${API_BASE}/global/kline?code=${encodeURIComponent(code)}&market=${market}&days=${days}`);
  if (!resp.ok) return { kline: [] };
  return resp.json();
}

export async function getGlobalIndicators(code: string, market = "hk") {
  const resp = await fetch(`${API_BASE}/global/indicators?code=${encodeURIComponent(code)}&market=${market}`);
}
