import Taro from "@tarojs/taro";

var API_BASE = "http://localhost:8000";

var authToken = "";
var userId = "";

export function setToken(token: string) { authToken = token; Taro.setStorageSync("token", token); }
export function getToken(): string { return authToken || Taro.getStorageSync("token") || ""; }

async function request<T>(path: string, options: Record<string, any>): Promise<T> {
  if (!options) options = {};
  var token = getToken();
  var headers: Record<string, string> = { "Content-Type": "application/json" };
  if (options.headers) { var h = options.headers as Record<string, string>; for (var k in h) { headers[k] = h[k]; } }
  if (token) headers["Authorization"] = "Bearer " + token;

  var res = await Taro.request({
    url: API_BASE + path,
    method: (options.method || "GET") as any,
    header: headers,
    data: options.body ? JSON.parse(options.body as string) : undefined,
  });
  if (res.statusCode >= 400) {
    var detail = (res.data as any)?.detail || ("Request failed: " + res.statusCode);
    throw new Error(String(detail));
  }
  return res.data as T;
}

export async function chatSimple(message: string, threadId: string | null) {
  return request<{ reply: string; thread_id: string }>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message: message, thread_id: threadId }),
  });
}

export async function searchStock(keyword: string) {
  return request<{ results: any[] }>("/api/search?keyword=" + encodeURIComponent(keyword));
}

export async function getQuote(code: string, market: string) {
  return request<any>("/api/quote?code=" + code + "&market=" + market);
}

export async function getKline(code: string, market: string, period: string) {
  return request<any>("/api/kline?code=" + code + "&market=" + market + "&period=" + period);
}

export async function getIndices() {
  return request<{ indices: any[] }>("/api/indices");
}

export async function getGlobalIndices() {
  return request<{ indices: any[] }>("/api/global-indices");
}

export async function getStockNews(page: number) {
  return request<{ articles: any[] }>("/api/news?page=" + page);
}

export async function getWatchlist() {
  return request<{ items: any[] }>("/api/watchlist");
}

export async function getWatchlistQuotes(codes: string[]) {
  var params = codes.map(function(c) { return "codes=" + c; }).join("&");
  return request<any[]>("/api/watchlist/quotes?" + params);
}

export async function removeFromWatchlist(code: string) {
  return request("/api/watchlist/" + code, { method: "DELETE" });
}

export async function getPortfolio() {
  return request<{ items: any[] }>("/api/portfolio");
}

export async function uploadPortfolio(filePath: string) {
  var token = getToken();
  return new Promise(function(resolve, reject) {
    Taro.uploadFile({
      url: API_BASE + "/api/portfolio/upload",
      filePath: filePath,
      name: "file",
      header: { Authorization: "Bearer " + token },
      success: function(res: any) { resolve(JSON.parse(res.data)); },
      fail: reject,
    });
  });
}