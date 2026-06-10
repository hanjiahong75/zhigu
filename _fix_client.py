path = r"D:\知股app - 前后端分离版本\frontend\src\api\client.ts"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

# Remove DEFAULT_DAYS and getDaysForKlt, simplify
c = """const API_BASE = "/api";

export const PERIODS: Record<string, string> = {
  "1": "\u4e00\u5206", "5": "\u4e94\u5206", "15": "\u5341\u4e94\u5206", "30": "\u4e09\u5341\u5206", "60": "\u516d\u5341\u5206", "120": "\u767e\u4e8c\u5341\u5206",
  "101": "\u65e5K", "102": "\u5468K", "103": "\u6708K", "104": "\u5b63K", "105": "\u5e74K",
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

export async function getAnalysis(code: string, market = "sz") {
  const resp = await fetch(`${API_BASE}/analyze?code=${encodeURIComponent(code)}&market=${market}`);
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
"""
with open(path, "w", encoding="utf-8") as f:
    f.write(c)
print("client.ts rewritten")
