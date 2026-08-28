import { Badge, Empty, Popconfirm, Tag, Tooltip } from "antd";
import {
  AudioLines,
  FileImage,
  FileSpreadsheet,
  FileText,
  Globe,
  Loader2,
  PanelRightClose,
  Trash2,
} from "lucide-react";
import React from "react";
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

const kindLabels: Record<SourceKind, { label: string; color: string }> = {
  pdf: { label: "PDF", color: "red" },
  text: { label: "文本", color: "blue" },
  url: { label: "网页", color: "cyan" },
  csv: { label: "CSV", color: "green" },
  image: { label: "图片", color: "purple" },
  audio: { label: "音频", color: "orange" },
  vision: { label: "识图", color: "magenta" },
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
          <button
            className="icon-btn-apple"
            onClick={onCollapse}
            aria-label="收起面板"
            title="收起面板"
            type="button"
          >
            <PanelRightClose size={16} />
          </button>
        )}
      </div>

      <div className="source-list">
        {sources.map((source) => {
          const Icon = sourceIcons[source.kind] ?? FileText;
          const kindInfo = kindLabels[source.kind] ?? {
            label: "文档",
            color: "default",
          };
          const isProcessing = source.status === "processing";
          const isError = source.status === "error";

          return (
            <div
              className={`source-item is-${source.status}`}
              key={source.id}
            >
              <div className="source-icon-wrap">
                {isProcessing ? (
                  <Loader2 size={15} className="spin-icon" />
                ) : (
                  <Icon size={15} />
                )}
              </div>

              <div className="source-item-info">
                <div className="source-name-row">
                  <Tooltip title={source.name} placement="topLeft">
                    <span className="source-name">{source.name}</span>
                  </Tooltip>
                  <Tag color={kindInfo.color} className="source-kind-tag">
                    {kindInfo.label}
                  </Tag>
                </div>

                <div className="source-meta-row">
                  {isProcessing && (
                    <Badge status="processing" text="正在解析索引..." />
                  )}
                  {isError && (
                    <Badge
                      status="error"
                      text={source.meta || "导入失败"}
                    />
                  )}
                  {!isProcessing && !isError && (
                    <span className="source-meta">{source.meta}</span>
                  )}
                </div>
              </div>

              <Popconfirm
                title="移除知识资料"
                description={`确定移除「${source.name}」吗？`}
                onConfirm={() => onRemove(source.id)}
                okText="移除"
                cancelText="取消"
                okButtonProps={{ danger: true, size: "small" }}
                cancelButtonProps={{ size: "small" }}
                disabled={isProcessing}
              >
                <button
                  className="source-delete-btn"
                  disabled={isProcessing}
                  aria-label={`移除 ${source.name}`}
                  title="移除资料"
                  type="button"
                >
                  <Trash2 size={13} />
                </button>
              </Popconfirm>
            </div>
          );
        })}

        {sources.length === 0 && (
          <div className="source-empty-wrap">
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <div className="source-empty-text">
                  <p>暂无关联资料</p>
                  <span>点击输入框旁的「+」添加文档或网页</span>
                </div>
              }
            />
          </div>
        )}
      </div>
    </aside>
  );
}
