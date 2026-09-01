import { useState, useEffect } from "react";
import { Spin, Skeleton, Typography, Tag, Empty } from "antd";
import { LinkOutlined, ClockCircleOutlined, ReloadOutlined } from "@ant-design/icons";
import { getNews } from "../api/client";

const { Text } = Typography;

interface NewsItem {
  title: string;
  url: string;
  intro: string;
  ctime: string;
  source: string;
}

export default function NewsPage() {
  const [news, setNews] = useState<NewsItem[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const refreshNews = async () => {
    setRefreshing(true);
    setPage(1);
    setHasMore(true);
    try {
      const data = await getNews(1, 20);
      setNews(data.news || []);
      if ((data.news || []).length < 20) setHasMore(false);
    } catch {
      // keep existing news on refresh failure
    }
    setRefreshing(false);
  };

  const fetchNews = async (pageNum: number) => {
    try {
      const data = await getNews(pageNum, 20);
      const items = data.news || [];
      if (pageNum === 1) {
        setNews(items);
      } else {
        setNews((prev) => [...prev, ...items]);
      }
      if (items.length < 20) setHasMore(false);
    } catch {
      if (pageNum === 1) setNews([]);
    }
  };

  useEffect(() => {
    fetchNews(1).finally(() => setInitialLoading(false));
  }, []);

  const loadMore = async () => {
    const nextPage = page + 1;
    setLoadingMore(true);
    setPage(nextPage);
    await fetchNews(nextPage);
    setLoadingMore(false);
  };

  const formatTime = (ctime: string) => {
    try {
      const d = new Date(parseInt(ctime) * 1000);
      return d.toLocaleString("zh-CN", {
        month: "2-digit", day: "2-digit",
        hour: "2-digit", minute: "2-digit",
      });
    } catch {
      return ctime;
    }
  };

  if (initialLoading) {
    return (
      <div style={{ flex: 1, padding: 24 }}>
        <Skeleton active paragraph={{ rows: 8 }} />
      </div>
    );
  }

  if (!news.length) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", flex: 1 }}>
        <Empty description="暂无财经新闻" />
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflow: "auto", padding: "0" }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 20px", borderBottom: "1px solid var(--border-color)",
        position: "sticky", top: 0, zIndex: 10,
        background: "var(--bg-primary)",
      }}>
        <Text strong style={{ fontSize: 14, color: "var(--text-primary)" }}>财经新闻</Text>
        <ReloadOutlined
          spin={refreshing}
          style={{ fontSize: 16, color: "var(--text-secondary)", cursor: "pointer" }}
          onClick={refreshNews}
        />
      </div>
      {news.map((item, i) => (
        <a
          key={`${item.ctime}-${i}`}
          href={item.url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ textDecoration: "none", color: "inherit", display: "block" }}
        >
          <div
            style={{
              padding: "12px 20px",
              borderBottom: "1px solid var(--border-color)",
              cursor: "pointer",
              transition: "background 0.15s",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          >
            <div style={{ display: "flex", alignItems: "flex-start", gap: 8, marginBottom: 4 }}>
              <Text
                strong
                style={{
                  flex: 1,
                  fontSize: 14,
                  lineHeight: "22px",
                  color: "var(--text-primary)",
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                }}
              >
                {item.title}
              </Text>
              <LinkOutlined style={{ color: "var(--text-muted)", fontSize: 12, marginTop: 4, flexShrink: 0 }} />
            </div>
            {item.intro && (
              <Text
                style={{
                  fontSize: 12,
                  color: "var(--text-secondary)",
                  lineHeight: "18px",
                  display: "-webkit-box",
                  WebkitLineClamp: 2,
                  WebkitBoxOrient: "vertical",
                  overflow: "hidden",
                  marginBottom: 6,
                }}
              >
                {item.intro}
              </Text>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Tag style={{ fontSize: 10, margin: 0, color: "var(--text-muted)", background: "var(--bg-secondary)", border: "none" }}>
                {item.source || "新浪财经"}
              </Tag>
              <Text style={{ fontSize: 11, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 3 }}>
                <ClockCircleOutlined />
                {formatTime(item.ctime)}
              </Text>
            </div>
          </div>
        </a>
      ))}
      <div style={{ padding: "16px", textAlign: "center" }}>
        {loadingMore ? (
          <Spin size="small" />
        ) : hasMore ? (
          <Text
            style={{ color: "var(--text-muted)", fontSize: 12, cursor: "pointer", userSelect: "none" }}
            onClick={loadMore}
          >
            加载更多
          </Text>
        ) : (
          <Text style={{ color: "var(--text-muted)", fontSize: 12 }}>没有更多了</Text>
        )}
      </div>
    </div>
  );
}
