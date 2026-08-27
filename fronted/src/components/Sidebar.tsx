import { MessageSquare, Settings, SquarePen, Trash2, X } from "lucide-react";
import type { Conversation } from "../types";
import { BrandMark } from "./BrandMark";

interface SidebarProps {
  sourceCount: number;
  conversations: Conversation[];
  activeConversationId: string;
  isOpen: boolean;
  disabled?: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelectConversation: (conversationId: string) => void;
  onClearSources: () => void;
  onOpenSettings: () => void;
}

export function Sidebar({
  sourceCount,
  conversations,
  activeConversationId,
  isOpen,
  disabled,
  onClose,
  onNewChat,
  onSelectConversation,
  onClearSources,
  onOpenSettings,
}: SidebarProps) {
  return (
    <aside className={`sidebar ${isOpen ? "is-open" : ""}`}>
      {/* Header */}
      <div className="sidebar-top">
        <BrandMark />
        <div className="sidebar-top-actions">
          <button
            className="icon-btn-apple"
            onClick={onNewChat}
            disabled={disabled}
            title="新建对话"
            aria-label="新建对话"
          >
            <SquarePen size={16} />
          </button>
          <button
            className="icon-btn-apple sidebar-close-btn"
            onClick={onClose}
            aria-label="关闭侧边栏"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* Sessions list */}
      <div className="sidebar-section">
        <span className="sidebar-section-title">最近对话</span>
        <div className="session-list">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              className={`session-row ${conversation.id === activeConversationId ? "is-active" : ""}`}
              onClick={() => onSelectConversation(conversation.id)}
              disabled={disabled || conversation.id === activeConversationId}
            >
              <MessageSquare size={13} className="session-row-icon" />
              <span className="session-row-text">{conversation.title}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <button className="sidebar-footer-row" onClick={onOpenSettings}>
          <Settings size={14} />
          <span>系统设置</span>
        </button>
        {sourceCount > 0 && (
          <button className="sidebar-footer-row text-danger" onClick={onClearSources}>
            <Trash2 size={14} />
            <span>清空已绑资料 ({sourceCount})</span>
          </button>
        )}
      </div>
    </aside>
  );
}
