import pathlib

# ============================================================
# 1. types/index.ts
# ============================================================
types = r'''export interface StockQuote {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  change_amount: number;
  volume: number;
  amount: number;
  high: number;
  low: number;
  open: number;
  pre_close: number;
  turnover: number;
}

export interface KlineItem {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  amount: number;
}

export interface StockSearchResult {
  code: string;
  name: string;
}

export interface MarketIndex {
  name: string;
  code: string;
  price: number;
  change_pct: number;
}

export interface AnalysisResult {
  quote: StockQuote;
  kline: KlineItem[];
  analysis: string;
  memory_context: string;
  summary: string;
}

export interface WatchlistItem {
  id: number;
  code: string;
  name: string;
  market: string;
}

export interface IndicatorsData {
  ma: { ma5: (number | null)[]; ma10: (number | null)[]; ma20: (number | null)[]; ma60: (number | null)[] };
  macd: { dif: (number | null)[]; dea: (number | null)[]; macd: (number | null)[] };
  rsi: { rsi6: (number | null)[]; rsi14: (number | null)[]; rsi24: (number | null)[] };
  bollinger: { upper: (number | null)[]; mid: (number | null)[]; lower: (number | null)[] };
}

export interface IndicatorsResponse {
  kline: KlineItem[];
  indicators: IndicatorsData;
}

export interface WatchlistQuote extends StockQuote {
  alert?: "up" | "down" | null;
}

export interface ChatHistoryItem {
  id: number;
  stock_code: string;
  stock_name: string;
  user_message: string;
  content: string;
  created_at: string;
}
'''
pathlib.Path("frontend/src/types/index.ts").write_text(types, encoding="utf-8")
print("1. types/index.ts updated")

# ============================================================
# 2. api/client.ts
# ============================================================
client = r'''const API_BASE = "/api";

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
'''
pathlib.Path("frontend/src/api/client.ts").write_text(client, encoding="utf-8")
print("2. api/client.ts updated")