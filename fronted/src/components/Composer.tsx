import { Sender } from "@ant-design/x";
import { type MenuProps, Dropdown } from "antd";
import {
  AudioLines,
  Eye,
  FileImage,
  FileSpreadsheet,
  FileText,
  Globe,
  Plus,
  X,
} from "lucide-react";
import React, { useRef, useState } from "react";
import type { SourceKind } from "../types";

const accepts: Record<Exclude<SourceKind, "url">, string> = {
  pdf: ".pdf",
  text: ".txt,.md,.markdown",
  image: ".png,.jpg,.jpeg",
  audio: ".mp3,.wav,.m4a",
  csv: ".csv",
  vision: ".png,.jpg,.jpeg",
};

function inferKindFromFile(file: File): Exclude<SourceKind, "url"> {
  const name = file.name.toLowerCase();
  const type = file.type.toLowerCase();

  if (name.endsWith(".pdf") || type === "application/pdf") return "pdf";
  if (name.endsWith(".csv") || type === "text/csv") return "csv";
  if (
    name.endsWith(".png") ||
    name.endsWith(".jpg") ||
    name.endsWith(".jpeg") ||
    type.startsWith("image/")
  ) {
    return "image";
  }
  if (
    name.endsWith(".mp3") ||
    name.endsWith(".wav") ||
    name.endsWith(".m4a") ||
    type.startsWith("audio/")
  ) {
    return "audio";
  }
  return "text";
}

interface ComposerProps {
  value: string;
  disabled?: boolean;
  isThinking?: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onCancel?: () => void;
  onUploadFile: (file: File, kind: Exclude<SourceKind, "url">) => void;
  onAddUrl: (url: string) => void;
}

export function Composer({
  value,
  disabled,
  isThinking = false,
  onChange,
  onSend,
  onCancel,
  onUploadFile,
  onAddUrl,
}: ComposerProps) {
  const [urlMode, setUrlMode] = useState(false);
  const [urlValue, setUrlValue] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pendingKind = useRef<Exclude<SourceKind, "url">>("pdf");

  const chooseFile = (kind: Exclude<SourceKind, "url">) => {
    pendingKind.current = kind;
    if (fileInputRef.current) {
      fileInputRef.current.accept = accepts[kind];
      fileInputRef.current.click();
    }
  };

  const handleFile = (file?: File) => {
    if (!file) return;
    onUploadFile(file, pendingKind.current);
  };

  const handlePasteFiles = (files: FileList) => {
    if (!files || files.length === 0) return;
    const file = files[0];
    const kind = inferKindFromFile(file);
    onUploadFile(file, kind);
  };

  const addUrl = () => {
    const normalized = urlValue.trim();
    if (!normalized) return;
    onAddUrl(normalized);
    setUrlValue("");
    setUrlMode(false);
  };

  const menuItems: MenuProps["items"] = [
    {
      key: "pdf",
      label: "PDF 文档",
      icon: <FileText size={15} className="menu-icon-pdf" />,
      onClick: () => chooseFile("pdf"),
    },
    {
      key: "text",
      label: "文本文档",
      icon: <FileText size={15} className="menu-icon-text" />,
      onClick: () => chooseFile("text"),
    },
    {
      key: "csv",
      label: "CSV 表格（数据分析）",
      icon: <FileSpreadsheet size={15} className="menu-icon-csv" />,
      onClick: () => chooseFile("csv"),
    },
    {
      key: "image",
      label: "图片资料",
      icon: <FileImage size={15} className="menu-icon-img" />,
      onClick: () => chooseFile("image"),
    },
    {
      key: "audio",
      label: "音频资料（语音转写）",
      icon: <AudioLines size={15} className="menu-icon-audio" />,
      onClick: () => chooseFile("audio"),
    },
    {
      type: "divider",
    },
    {
      key: "url",
      label: "网页链接导入",
      icon: <Globe size={15} className="menu-icon-web" />,
      onClick: () => setUrlMode(true),
    },
    {
      key: "vision",
      label: "临时识图 QA",
      icon: <Eye size={15} className="menu-icon-img" />,
      onClick: () => chooseFile("vision"),
    },
  ];

  return (
    <div className="composer-wrap">
      <input
        ref={fileInputRef}
        className="visually-hidden"
        type="file"
        onChange={(event) => {
          handleFile(event.target.files?.[0]);
          event.target.value = "";
        }}
      />

      <div className="ant-sender-container">
        <Sender
          value={value}
          loading={isThinking}
          disabled={disabled && !isThinking}
          placeholder="向 Copilot 提问、分析数据或总结资料... (Enter 发送, Shift+Enter 换行)"
          onChange={(val) => onChange(val)}
          onSubmit={() => {
            if (!value.trim() || isThinking) return;
            onSend();
          }}
          onCancel={onCancel}
          onPasteFile={handlePasteFiles}
          autoSize={{ minRows: 1, maxRows: 6 }}
          header={
            urlMode ? (
              <Sender.Header
                title={
                  <div className="sender-url-bar">
                    <Globe size={14} className="url-icon" />
                    <input
                      autoFocus
                      className="sender-url-input"
                      value={urlValue}
                      placeholder="输入或粘贴网页链接..."
                      onChange={(e) => setUrlValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          addUrl();
                        }
                      }}
                    />
                    <button
                      className="url-submit-btn"
                      onClick={addUrl}
                      type="button"
                    >
                      添加
                    </button>
                    <button
                      className="url-cancel-btn"
                      onClick={() => setUrlMode(false)}
                      type="button"
                    >
                      <X size={14} />
                    </button>
                  </div>
                }
                open={urlMode}
                onOpenChange={(open) => setUrlMode(open)}
              />
            ) : undefined
          }
          prefix={
            <Dropdown
              menu={{ items: menuItems }}
              trigger={["click"]}
              placement="topLeft"
              disabled={disabled}
            >
              <button
                className="attach-button ant-sender-attach-btn"
                aria-label="添加资料"
                type="button"
                title="添加资料或网页"
              >
                <Plus size={18} />
              </button>
            </Dropdown>
          }
        />
      </div>

      <div className="composer-footnote">
        Enterprise AI Copilot · 支持直接粘贴文件或多模态附件
      </div>
    </div>
  );
}
