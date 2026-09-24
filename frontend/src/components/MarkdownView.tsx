import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

interface Props {
  content: string;
  variant?: "chat" | "analysis";
  className?: string;
}

/**
 * 安全的 Markdown 渲染组件（react-markdown + rehype-sanitize）。
 * 视觉样式通过 components 回调以 JSX style 注入，不依赖原始 HTML 属性，
 * 因此不会被 sanitize 剥离；同时 LLM 输出中的脚本/原始 HTML 会被移除。
 */
export default function MarkdownView({ content, variant = "chat", className }: Props) {
  const isAnalysis = variant === "analysis";
  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          h1: (p) => <h1 style={{ fontSize: isAnalysis ? 20 : 16, margin: "12px 0 6px" }} {...p} />,
          h2: (p) => <h2 style={{ fontSize: isAnalysis ? 18 : 15, margin: isAnalysis ? "20px 0 10px" : "12px 0 6px" }} {...p} />,
          h3: (p) => (
            <h3
              style={{
                color: "#1677ff",
                fontSize: isAnalysis ? 16 : 14,
                margin: isAnalysis ? "16px 0 8px" : "10px 0 4px",
                borderBottom: "1px solid #e8f4ff",
                paddingBottom: isAnalysis ? 6 : 4,
              }}
              {...p}
            />
          ),
          p: (p) => <p style={{ margin: "6px 0" }} {...p} />,
          table: (p) => (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                margin: isAnalysis ? "12px 0" : "6px 0",
                fontSize: isAnalysis ? 13 : 12,
              }}
              {...p}
            />
          ),
          th: (p) => (
            <th
              style={{ border: "1px solid #e8f4ff", padding: 4, background: "#f5faff", textAlign: "left" }}
              {...p}
            />
          ),
          td: (p) => <td style={{ border: "1px solid #eee", padding: 4 }} {...p} />,
          strong: (p) => <strong style={{ color: "#333" }} {...p} />,
          ul: (p) => <ul style={{ margin: "6px 0", paddingLeft: 20 }} {...p} />,
          ol: (p) => <ol style={{ margin: "6px 0", paddingLeft: 20 }} {...p} />,
          li: (p) => <li style={{ margin: "2px 0" }} {...p} />,
          code: (p) => (
            <code
              style={{ background: "#f5f5f5", borderRadius: 4, padding: "1px 5px", fontSize: "0.92em" }}
              {...p}
            />
          ),
          pre: (p) => (
            <pre
              style={{ background: "#f5f5f5", borderRadius: 8, padding: 12, overflowX: "auto", fontSize: 12 }}
              {...p}
            />
          ),
          blockquote: (p) => (
            <blockquote
              style={{ margin: "6px 0", paddingLeft: 12, borderLeft: "3px solid #e8f4ff", color: "#666" }}
              {...p}
            />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
