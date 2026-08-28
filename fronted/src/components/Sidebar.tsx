import { Conversations, type ConversationItemType } from "@ant-design/x";
import { Input, Modal } from "antd";
import {
  Edit3,
  MessageSquare,
  Plus,
  Settings,
  SquarePen,
  Trash2,
  X,
} from "lucide-react";
import React, { useState } from "react";
import type { Conversation } from "../types";
import { BrandMark } from "./BrandMark";

function getConversationGroup(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    const now = new Date();
    const today = new Date(
      now.getFullYear(),
      now.getMonth(),
      now.getDate(),
    ).getTime();
    const yesterday = today - 86400000;
    const sevenDaysAgo = today - 7 * 86400000;

    const targetTime = date.getTime();
    if (targetTime >= today) return "今天";
    if (targetTime >= yesterday) return "昨天";
    if (targetTime >= sevenDaysAgo) return "最近 7 天";
    return "更早";
  } catch {
    return "历史对话";
  }
}

interface SidebarProps {
  sourceCount: number;
  conversations: Conversation[];
  activeConversationId: string;
  isOpen: boolean;
  disabled?: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onSelectConversation: (conversationId: string) => void;
  onDeleteConversation: (conversationId: string) => void;
  onRenameConversation: (conversationId: string, newTitle: string) => void;
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
  onDeleteConversation,
  onRenameConversation,
  onClearSources,
  onOpenSettings,
}: SidebarProps) {
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameTitle, setRenameTitle] = useState("");

  const handleStartRename = (conversation: Conversation) => {
    setRenamingId(conversation.id);
    setRenameTitle(conversation.title);
  };

  const handleConfirmRename = () => {
    if (renamingId && renameTitle.trim()) {
      onRenameConversation(renamingId, renameTitle.trim());
    }
    setRenamingId(null);
  };

  const handleDeleteWithConfirm = (conversation: Conversation) => {
    if (conversation.messages.length > 0) {
      Modal.confirm({
        title: "删除对话",
        content: `确定要删除「${conversation.title}」吗？删除后不可恢复。`,
        okText: "确认删除",
        cancelText: "取消",
        okButtonProps: { danger: true },
        onOk: () => onDeleteConversation(conversation.id),
      });
    } else {
      onDeleteConversation(conversation.id);
    }
  };

  const conversationItems: ConversationItemType[] = conversations.map(
    (conversation) => ({
      key: conversation.id,
      label: conversation.title,
      group: getConversationGroup(conversation.updatedAt || conversation.createdAt),
      icon: <MessageSquare size={13} />,
      disabled,
    }),
  );

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
            type="button"
          >
            <SquarePen size={16} />
          </button>
          <button
            className="icon-btn-apple sidebar-close-btn"
            onClick={onClose}
            aria-label="关闭侧边栏"
            type="button"
          >
            <X size={16} />
          </button>
        </div>
      </div>

      {/* New chat quick pill */}
      <div className="sidebar-new-chat-wrap">
        <button
          className="sidebar-new-chat-btn"
          onClick={onNewChat}
          disabled={disabled}
          type="button"
        >
          <Plus size={14} />
          <span>开启新对话</span>
        </button>
      </div>

      {/* Sessions list */}
      <div className="sidebar-section">
        <div className="conversations-wrapper">
          <Conversations
            items={conversationItems}
            activeKey={activeConversationId}
            onActiveChange={(key) => onSelectConversation(String(key))}
            groupable
            menu={(item) => {
              const target = conversations.find((c) => c.id === item.key);
              if (!target) return {};
              return {
                items: [
                  {
                    key: "rename",
                    label: "重命名",
                    icon: <Edit3 size={13} />,
                  },
                  {
                    type: "divider",
                  },
                  {
                    key: "delete",
                    label: "删除对话",
                    icon: <Trash2 size={13} />,
                    danger: true,
                  },
                ],
                onClick: ({ key, domEvent }) => {
                  domEvent.stopPropagation();
                  if (key === "rename") {
                    handleStartRename(target);
                  } else if (key === "delete") {
                    handleDeleteWithConfirm(target);
                  }
                },
              };
            }}
          />
        </div>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <button
          className="sidebar-footer-row"
          onClick={onOpenSettings}
          type="button"
        >
          <Settings size={14} />
          <span>系统设置</span>
        </button>
        {sourceCount > 0 && (
          <button
            className="sidebar-footer-row text-danger"
            onClick={onClearSources}
            type="button"
          >
            <Trash2 size={14} />
            <span>清空已绑资料 ({sourceCount})</span>
          </button>
        )}
      </div>

      {/* Rename Dialog */}
      <Modal
        title="重命名对话"
        open={Boolean(renamingId)}
        onOk={handleConfirmRename}
        onCancel={() => setRenamingId(null)}
        okText="保存"
        cancelText="取消"
        destroyOnClose
      >
        <div style={{ marginTop: 12 }}>
          <Input
            autoFocus
            value={renameTitle}
            maxLength={50}
            showCount
            placeholder="输入对话名称..."
            onChange={(e) => setRenameTitle(e.target.value)}
            onPressEnter={handleConfirmRename}
          />
        </div>
      </Modal>
    </aside>
  );
}
