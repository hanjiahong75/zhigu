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
  holding_amount?: number;
  cost_amount?: number;
  holding_return?: number;
  daily_return?: number;
  daily_return_pct?: number;
  sector?: string;
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

export interface DiagnosisItem {
  stock_code: string;
  stock_name: string;
  asset_type: string;
  weight_pct: number;
  profit_pct: number;
  change_today: number | null;
  signal: "green" | "yellow" | "red" | "grey";
  reason: string;
}

export interface DiagnosisData {
  concentration: {
    top3_pct: number;
    top1_pct: number;
    top1_name: string;
    warning: string | null;
  } | null;
  items: DiagnosisItem[];
  summary: string;
}

export interface UserProfile {
  investment_style: 'short_term' | 'medium_term' | 'long_term';
  risk_preference: 'conservative' | 'moderate' | 'aggressive';
  focus_industries: string;
  focus_stocks: string;
}

export interface GlobalQuote {
  code: string;
  market: string;
  name: string;
  price: number;
  change_pct: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  amount?: number;
  pe?: number;
  source: string;
}

export interface GlobalIndicators {
  code: string;
  market: string;
  price: number;
  rsi: number;
  rsi_signal: string;
  macd: { macd: number; signal: number; histogram: number };
  ma: { ma5: number; ma10: number; ma20: number; ma50: number };
  boll: { upper: number; mid: number; lower: number };
  recommendation: string;
  buy_count: number;
  sell_count: number;
  neutral_count: number;
  source: string;
}