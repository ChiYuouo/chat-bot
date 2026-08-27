import { MessageSquare, Settings, SquarePen, Trash2, X } from "lucide-react";
import { BrandMark } from "./BrandMark";

interface SidebarProps {
  sourceCount: number;
  isOpen: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onClearSources: () => void;
  onOpenSettings: () => void;
}

const mockSessions = [
  { id: "1", title: "当前对话", isActive: true },
  { id: "2", title: "Q2 销售数据分析", isActive: false },
  { id: "3", title: "差旅与住宿报销标准", isActive: false },
  { id: "4", title: "周会录音要点提炼", isActive: false },
];

export function Sidebar({
  sourceCount,
  isOpen,
  onClose,
  onNewChat,
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
          {mockSessions.map((session) => (
            <button
              key={session.id}
              className={`session-row ${session.isActive ? "is-active" : ""}`}
              onClick={session.isActive ? undefined : onNewChat}
            >
              <MessageSquare size={13} className="session-row-icon" />
              <span className="session-row-text">{session.title}</span>
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
