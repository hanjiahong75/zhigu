import { useEffect, useState } from "react";
import type { StockQuote } from "../types";

const API_BASE = "/api";

interface QuoteStreamMessage {
  type: "quotes";
  ts: number;
  quotes: StockQuote[];
}

/**
 * Subscribe to the backend realtime quote SSE stream (M2).
 * EventSource auto-reconnects on network errors. Returns quotes keyed by code.
 */
export function useQuoteStream(codes: string[], interval = 10, enabled = true) {
  const [quotes, setQuotes] = useState<Record<string, StockQuote>>({});
  const codesKey = codes.join(",");

  useEffect(() => {
    if (!enabled || codesKey.length === 0) {
      setQuotes({});
      return;
    }
    const es = new EventSource(
      `${API_BASE}/quotes/stream?codes=${encodeURIComponent(codesKey)}&interval=${interval}`
    );
    es.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as QuoteStreamMessage;
        if (msg.type === "quotes" && Array.isArray(msg.quotes)) {
          setQuotes((prev) => {
            const next: Record<string, StockQuote> = { ...prev };
            for (const q of msg.quotes) next[q.code] = q;
            return next;
          });
        }
      } catch {
        // ignore malformed frames
      }
    };
    // EventSource reconnects automatically on error; nothing else to do here.
    return () => es.close();
  }, [codesKey, interval, enabled]);

  return quotes;
}
