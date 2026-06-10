import { useState, useRef, useEffect } from "react";
import { Input, List, Tag, message } from "antd";
import { SearchOutlined, PlusOutlined } from "@ant-design/icons";
import { searchStocks, addToWatchlist } from "../api/client";
import type { StockSearchResult } from "../types";

interface Props {
  onSelect: (code: string, name: string, market: string) => void;
  onWatchlistChange: () => void;
}

export default function StockSearch({ onSelect, onWatchlistChange }: Props) {
  const [keyword, setKeyword] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setShowResults(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const doSearch = async (value: string) => {
    if (!value.trim()) {
      setResults([]);
      setShowResults(false);
      return;
    }
    setSearching(true);
    try {
      const data = await searchStocks(value);
      setResults(data.results || []);
      setShowResults(true);
    } catch {
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const handleChange = (value: string) => {
    setKeyword(value);
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => doSearch(value), 300);
  };

  const handleSelect = (item: StockSearchResult) => {
    const market = item.code.startsWith("6") ? "sh" : "sz";
    onSelect(item.code, item.name, market);
    setKeyword(item.name);
    setShowResults(false);
  };

  const handleAddWatchlist = async (item: StockSearchResult) => {
    const market = item.code.startsWith("6") ? "sh" : "sz";
    try {
      await addToWatchlist(item.code, item.name, market);
      message.success(`已添加 ${item.name} 到自选`);
      onWatchlistChange();
    } catch {
      message.error("添加失败");
    }
  };

  return (
    <div ref={containerRef} style={{ position: "relative", marginBottom: 16 }}>
      <Input
        size="large"
        prefix={<SearchOutlined />}
        placeholder="输入股票代码或名称，如：贵州茅台、000001..."
        value={keyword}
        onChange={(e) => handleChange(e.target.value)}
        onFocus={() => results.length > 0 && setShowResults(true)}
        allowClear
        style={{ borderRadius: 8 }}
      />
      {showResults && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            zIndex: 1000,
            background: "#fff",
            border: "1px solid #e8e8e8",
            borderRadius: 8,
            boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
            maxHeight: 320,
            overflow: "auto",
          }}
        >
          {searching ? (
            <div style={{ padding: 16, textAlign: "center", color: "#888" }}>
              搜索中...
            </div>
          ) : results.length === 0 ? (
            <div style={{ padding: 16, textAlign: "center", color: "#888" }}>
              无匹配结果
            </div>
          ) : (
            <List
              dataSource={results}
              renderItem={(item) => (
                <List.Item
                  style={{
                    padding: "10px 16px",
                    cursor: "pointer",
                  }}
                  onMouseEnter={(e) =>
                    (e.currentTarget.style.background = "#f5f5f5")
                  }
                  onMouseLeave={(e) =>
                    (e.currentTarget.style.background = "transparent")
                  }
                  onClick={() => handleSelect(item)}
                  actions={[
                    <PlusOutlined
                      key="add"
                      style={{ color: "#1677ff" }}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAddWatchlist(item);
                      }}
                    />,
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <span>
                        <Tag color="blue" style={{ marginRight: 8 }}>
                          {item.code}
                        </Tag>
                        {item.name}
                      </span>
                    }
                  />
                </List.Item>
              )}
            />
          )}
        </div>
      )}
    </div>
  );
}
