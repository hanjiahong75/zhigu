import { useState } from "react";
import { Input, Button, Modal, Typography } from "antd";
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

export default function ThreadSidebar() {
  const {
    threads, threadId, contextMenu, setContextMenu, renameModal, setRenameModal,
    loadThread, newThread, handleContextMenu, handlePin, handleRename,
    confirmRename, handleDelete, contextMenuRef,
  } = useChat();
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();

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
      {!collapsed && (
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
      )}
    </div>
  );

  return (
    <>
      {/* Sidebar */}
      <div className="glass-panel" style={{
        width: collapsed ? 44 : 180, borderRight: "1px solid var(--border-color)",
        background: "transparent", display: "flex", flexDirection: "column",
        overflow: "hidden", flexShrink: 0, transition: "width 0.2s ease",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "8px", borderBottom: "1px solid var(--border-color)",
        }}>
          {!collapsed && (
            <Text strong style={{ fontSize: 13, color: "var(--text-primary)" }}>对话记录</Text>
          )}
          <Button
            type="text"
            size="small"
            icon={collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
            onClick={() => setCollapsed(!collapsed)}
          />
        </div>

        {!collapsed && (
          <div style={{ padding: "8px", borderBottom: "1px solid var(--border-color)" }}>
            <Button type="primary" size="small" block icon={<PlusOutlined />} onClick={newThread}>
              新建对话
            </Button>
          </div>
        )}

        {/* Thread list */}
        <div style={{ flex: 1, overflow: "auto", padding: "4px" }}>
          {pinnedThreads.map(renderThread)}
          {pinnedThreads.length > 0 && unpinnedThreads.length > 0 && (
            <div style={{
              borderTop: "1px solid var(--border-color)", margin: "4px 0",
              fontSize: 10, color: "var(--text-muted)", padding: "2px 8px",
            }}>
              {!collapsed && "常规对话"}
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
