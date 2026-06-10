export interface StockQuote {
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

export interface PortfolioItem {
  id: number;
  stock_code: string;
  stock_name: string;
  asset_type: 'stock' | 'fund' | 'etf';
  quantity: number;
  cost_price: number;
  current_price: number;
  value?: number;
  profit_loss?: number;
  profit_pct?: number;
}

export interface Portfolio {
  id: number | null;
  name: string;
  items: PortfolioItem[];
  total_value: number;
  total_cost: number;
  total_profit: number;
  total_profit_pct: number;
}

export interface RecognizedItem {
  stock_code: string;
  stock_name: string;
  quantity: number;
  cost_price: number;
  current_price?: number;
}