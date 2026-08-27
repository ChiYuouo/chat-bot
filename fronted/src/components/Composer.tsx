import { ArrowUp, AudioLines, Eye, FileImage, FileSpreadsheet, FileText, Globe, Plus, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { SourceKind } from "../types";

const accepts: Record<Exclude<SourceKind, "url">, string> = {
  pdf: ".pdf",
  text: ".txt,.md,.markdown",
  image: ".png,.jpg,.jpeg",
  audio: ".mp3,.wav,.m4a",
  csv: ".csv",
  vision: ".png,.jpg,.jpeg",
};

interface ComposerProps {
  value: string;
  disabled?: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onUploadFile: (file: File, kind: Exclude<SourceKind, "url">) => void;
  onAddUrl: (url: string) => void;
}

export function Composer({
  value,
  disabled,
  onChange,
  onSend,
  onUploadFile,
  onAddUrl,
}: ComposerProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [urlMode, setUrlMode] = useState(false);
  const [urlValue, setUrlValue] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const pendingKind = useRef<Exclude<SourceKind, "url">>("pdf");

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    if (menuOpen) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [menuOpen]);

  const chooseFile = (kind: Exclude<SourceKind, "url">) => {
    pendingKind.current = kind;
    if (fileInputRef.current) {
      fileInputRef.current.accept = accepts[kind];
      fileInputRef.current.click();
    }
    setMenuOpen(false);
  };

  const handleFile = (file?: File) => {
    if (!file) return;
    onUploadFile(file, pendingKind.current);
  };

  const addUrl = () => {
    const normalized = urlValue.trim();
    if (!normalized) return;
    onAddUrl(normalized);
    setUrlValue("");
    setUrlMode(false);
  };

  const hasContent = Boolean(value.trim());

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

      {urlMode && (
        <div className="url-entry-bar">
          <Globe size={15} className="url-icon" />
          <input
            autoFocus
            value={urlValue}
            placeholder="输入或粘贴网页链接..."
            onChange={(event) => setUrlValue(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && addUrl()}
          />
          <button className="url-submit-btn" onClick={addUrl}>添加</button>
          <button className="url-cancel-btn" onClick={() => setUrlMode(false)}>
            <X size={14} />
          </button>
        </div>
      )}

      <div className="composer">
        <div className="composer-leading" ref={menuRef}>
          <button
            className={`attach-button ${menuOpen ? "is-active" : ""}`}
            onClick={() => setMenuOpen((v) => !v)}
            aria-label="添加资料"
            type="button"
            title="添加资料"
          >
            <Plus size={18} />
          </button>

          {menuOpen && (
            <div className="apple-menu">
              <button onClick={() => chooseFile("pdf")}>
                <FileText size={15} className="menu-icon-pdf" />
                <span>PDF 文档</span>
              </button>
              <button onClick={() => chooseFile("text")}>
                <FileText size={15} className="menu-icon-text" />
                <span>文本文档</span>
              </button>
              <button onClick={() => chooseFile("csv")}>
                <FileSpreadsheet size={15} className="menu-icon-csv" />
                <span>CSV 表格</span>
              </button>
              <button onClick={() => chooseFile("image")}>
                <FileImage size={15} className="menu-icon-img" />
                <span>图片资料</span>
              </button>
              <button onClick={() => chooseFile("audio")}>
                <AudioLines size={15} className="menu-icon-audio" />
                <span>音频资料</span>
              </button>
              <div className="apple-menu-divider" />
              <button onClick={() => { setUrlMode(true); setMenuOpen(false); }}>
                <Globe size={15} className="menu-icon-web" />
                <span>网页链接</span>
              </button>
              <button onClick={() => chooseFile("vision")}>
                <Eye size={15} className="menu-icon-img" />
                <span>临时识图</span>
              </button>
            </div>
          )}
        </div>

        <textarea
          ref={textareaRef}
          value={value}
          rows={1}
          placeholder="向 Copilot 提问或总结资料..."
          aria-label="输入消息"
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              onSend();
            }
          }}
        />

        <button
          className={`send-circle-btn ${hasContent && !disabled ? "is-active" : ""}`}
          onClick={onSend}
          disabled={!hasContent || disabled}
          aria-label="发送消息"
        >
          <ArrowUp size={16} strokeWidth={2.5} />
        </button>
      </div>

      <div className="composer-footnote">AI 生成内容仅供参考</div>
    </div>
  );
}
