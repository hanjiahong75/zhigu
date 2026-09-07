import { useState } from "react";
import { Input, Button, Modal, Typography } from "antd";
import { useEffect, useRef } from "react";
import {
  PlusOutlined, PushpinOutlined, PushpinFilled,
  EditOutlined, DeleteOutlined, MenuFoldOutlined, MenuUnfoldOutlined,
} from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useChat, type Thread } from "../api/ChatContext";

const { Text } = Typography;

const menuItemStyle: React.CSSProperties = {
  padding: "6px 12px", cursor: "pointer", fontSize: 12, display: "flex",
  alignItems: "center", color: "var(--text-primary)",
};

// Liquid-glass morph helpers (panel outline in objectBoundingBox space: 0..1)
const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);
const lp = (a: number, b: number, t: number) => a + (b - a) * t;
function morphPath(p: number): string {
  const A: [number, number] = [0.9, 0.13];
  const TLs: [number, number] = [0.02, 0.02];
  const TRs: [number, number] = [0.98, 0.02];
  const BRs: [number, number] = [0.98, 0.98];
  const BLs: [number, number] = [0.02, 0.98];
  const lag = p * p;
  const TL: [number, number] = [lp(TLs[0], A[0], p), lp(TLs[1], A[1], p)];
  const TR: [number, number] = [lp(TRs[0], A[0], p), lp(TRs[1], A[1], p)];
  const BR: [number, number] = [lp(BRs[0], A[0], p), lp(BRs[1], A[1], p)];
  const BL: [number, number] = [lp(BLs[0], A[0], lag), lp(BLs[1], A[1], lag)];
  const c1: [number, number] = [lp(lp(BRs[0], BLs[0], 0.34), A[0], p * 0.9), lp(lp(BRs[1], BLs[1], 0.34), A[1], p * 0.9)];
  const c2: [number, number] = [lp(lp(BRs[0], BLs[0], 0.66), A[0], p * 0.9), lp(lp(BRs[1], BLs[1], 0.66), A[1], p * 0.9)];
  return `M ${TL[0]} ${TL[1]} L ${TR[0]} ${TR[1]} L ${BR[0]} ${BR[1]} C ${c1[0]} ${c1[1]}, ${c2[0]} ${c2[1]}, ${BL[0]} ${BL[1]} L ${TL[0]} ${TL[1]} Z`;
}

export default function ThreadSidebar() {
  const {
    threads, threadId, contextMenu, setContextMenu, renameModal, setRenameModal,
    loadThread, newThread, handleContextMenu, handlePin, handleRename,
    confirmRename, handleDelete, contextMenuRef,
  } = useChat();
  const [collapsed, setCollapsed] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const lidRef = useRef<SVGPathElement | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    const pathEl = lidRef.current;
    const panel = panelRef.current;
    if (!pathEl || !panel) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      pathEl.setAttribute("d", morphPath(collapsed ? 1 : 0));
      panel.style.filter = "";
      return;
    }
    const dur = 620;
    const start = performance.now();
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min((now - start) / dur, 1);
      const p = collapsed ? easeOutCubic(t) : easeOutCubic(1 - t);
      pathEl.setAttribute("d", morphPath(p));
      panel.style.filter = `blur(${Math.round(p * 10)}px)`;
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [collapsed]);

  const pinnedThreads = threads.filter((t: Thread) => t.pinned);
  const unpinnedThreads = threads.filter((t: Thread) => !t.pinned);

  const renderThread = (t: Thread) => (
    <div
      key={t.id}
      onClick={() => { loadThread(t.id); navigate("/home"); }}
      onContextMenu={(e) => handleContextMenu(e, t.id)}
      className="thread-item"
      style={{
        background: t.id === threadId ? "var(--thread-active-bg)" : "transparent",
        borderLeft: t.id === threadId ? "3px solid #1677ff" : "3px solid transparent",
        border: "1px solid transparent",
        display: "flex", alignItems: "center", gap: 4,
      }}
    >
      {t.pinned && <PushpinFilled style={{ color: "var(--bubble-user-text)", fontSize: 10, flexShrink: 0 }} />}
      <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: 12, fontWeight: t.id === threadId ? 600 : 400,
            color: "var(--text-primary)",
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {t.title || "新对话"}
          </div>
          <div style={{
            fontSize: 10, color: "var(--text-muted)", marginTop: 2,
            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
          }}>
            {t.last_message?.slice(0, 30)}
          </div>
        </div>
    </div>
  );

  return (
    <>
      {/* Sidebar */}
      <button
        className={"thread-toggle" + (collapsed ? "" : " hide")}
        onClick={() => setCollapsed(false)}
        title="展开对话记录"
      >
        <MenuUnfoldOutlined />
      </button>
      <svg width="0" height="0" style={{ position: "absolute" }} aria-hidden="true">
        <defs>
          <clipPath id="threadLiquidClip" clipPathUnits="objectBoundingBox">
            <path
              id="threadLiquidPath"
              ref={lidRef}
              d="M 0.02 0.02 L 0.98 0.02 L 0.98 0.98 C 0.66 0.98, 0.34 0.98, 0.02 0.98 L 0.02 0.02 Z"
            />
          </clipPath>
        </defs>
      </svg>
      <div
        ref={panelRef}
        className="glass-panel thread-sidebar"
        style={{
        width: collapsed ? 0 : 180, borderRight: "1px solid var(--border-color)",
        display: "flex", flexDirection: "column",
        overflow: "hidden", flexShrink: 0,
        clipPath: "url(#threadLiquidClip)",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "8px", borderBottom: "1px solid var(--border-color)",
        }}>
          <Text strong style={{ fontSize: 13, color: "var(--text-primary)" }}>对话记录</Text>
          <Button
            type="text"
            size="small"
            icon={<MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
        </div>

        <div style={{ padding: "8px", borderBottom: "1px solid var(--border-color)" }}>
          <Button type="primary" size="small" block icon={<PlusOutlined />} onClick={newThread}>
            新建对话
          </Button>
        </div>

        {/* Thread list — hidden entirely when collapsed */}
        <div style={{ flex: 1, overflow: "auto", padding: "4px" }}>
          {pinnedThreads.map(renderThread)}
          {pinnedThreads.length > 0 && unpinnedThreads.length > 0 && (
            <div style={{
              borderTop: "1px solid var(--border-color)", margin: "4px 0",
              fontSize: 10, color: "var(--text-muted)", padding: "2px 8px",
            }}>
              常规对话
            </div>
          )}
          {unpinnedThreads.map(renderThread)}
        </div>
      </div>

      {/* Context menu */}
      {contextMenu.visible && (
        <div ref={contextMenuRef} style={{
          position: "fixed", left: contextMenu.x, top: contextMenu.y,
          background: "var(--bg-secondary)", border: "1px solid var(--border-color)",
          borderRadius: 8, boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
          zIndex: 1000, minWidth: 140, padding: "4px 0",
        }}>
          {(() => {
            const t = threads.find((th: Thread) => th.id === contextMenu.threadId);
            return (
              <div onClick={handlePin} style={menuItemStyle}>
                {t?.pinned ? <PushpinFilled style={{ color: "var(--bubble-user-text)" }} /> : <PushpinOutlined />}
                <span style={{ marginLeft: 8 }}>{t?.pinned ? "取消置顶" : "置顶"}</span>
              </div>
            );
          })()}
          <div onClick={handleRename} style={menuItemStyle}>
            <EditOutlined />
            <span style={{ marginLeft: 8 }}>重命名</span>
          </div>
          <div style={{ borderTop: "1px solid var(--border-color)", margin: "4px 0" }} />
          <div onClick={handleDelete} style={{ ...menuItemStyle, color: "#ef4444" }}>
            <DeleteOutlined />
            <span style={{ marginLeft: 8 }}>删除</span>
          </div>
        </div>
      )}

      {/* Rename modal */}
      <Modal
        title="重命名对话"
        open={renameModal.visible}
        onOk={confirmRename}
        onCancel={() => setRenameModal({ visible: false, threadId: "", title: "" })}
        okText="确定"
        cancelText="取消"
      >
        <Input
          value={renameModal.title}
          onChange={(e) => setRenameModal({ ...renameModal, title: e.target.value })}
          placeholder="输入新名称"
        />
      </Modal>
    </>
  );
}
