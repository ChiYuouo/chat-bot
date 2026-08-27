import { AudioLines, FileImage, FileSpreadsheet, FileText, Globe, PanelRightClose, Trash2 } from "lucide-react";
import type { KnowledgeSource, SourceKind } from "../types";

const sourceIcons: Record<SourceKind, typeof FileText> = {
  pdf: FileText,
  text: FileText,
  url: Globe,
  image: FileImage,
  audio: AudioLines,
  csv: FileSpreadsheet,
  vision: FileImage,
};

interface SourcePanelProps {
  sources: KnowledgeSource[];
  onRemove: (id: string) => void;
  onCollapse?: () => void;
}

export function SourcePanel({ sources, onRemove, onCollapse }: SourcePanelProps) {
  return (
    <aside className="source-panel">
      <div className="source-header">
        <div className="source-title-wrap">
          <h2>知识来源</h2>
          <span className="source-count-pill">{sources.length}</span>
        </div>
        {onCollapse && (
          <button className="icon-btn-apple" onClick={onCollapse} aria-label="收起面板" title="收起面板">
            <PanelRightClose size={16} />
          </button>
        )}
      </div>

      <div className="source-list">
        {sources.map((source) => {
          const Icon = sourceIcons[source.kind] ?? FileText;
          return (
            <div className="source-item" key={source.id}>
              <div className="source-icon-wrap">
                <Icon size={14} />
              </div>
              <div className="source-item-info">
                <span className="source-name" title={source.name}>{source.name}</span>
                <span className="source-meta">{source.meta}</span>
              </div>
              <button
                className="source-delete-btn"
                onClick={() => onRemove(source.id)}
                aria-label={`移除 ${source.name}`}
                title="移除"
              >
                <Trash2 size={12} />
              </button>
            </div>
          );
        })}

        {sources.length === 0 && (
          <div className="source-empty">
            <p>暂无关联文件</p>
            <span>点击输入框旁的「+」添加</span>
          </div>
        )}
      </div>
    </aside>
  );
}
