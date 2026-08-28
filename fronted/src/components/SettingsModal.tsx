import { Button, Input, Modal, message } from "antd";
import {
  Check,
  Cpu,
  KeyRound,
  Server,
  Sparkles,
} from "lucide-react";
import React, { useEffect, useState } from "react";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

const models = [
  {
    id: "",
    name: "跟随后端配置",
    tag: "默认",
    desc: "不覆盖后端模型，使用环境变量或服务端默认设置",
  },
  {
    id: "qwen-plus",
    name: "Qwen-Plus",
    tag: "均衡",
    desc: "通用高效 · 推荐用于常规企业知识问答与文档总结",
  },
  {
    id: "qwen-max",
    name: "Qwen-Max",
    tag: "旗舰",
    desc: "旗舰推理 · 适用于复杂逻辑梳理、代码生成与多轮深度分析",
  },
];

export function SettingsModal({ isOpen, onClose, onSaved }: SettingsModalProps) {
  const [key, setKey] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setKey(localStorage.getItem("dashscope-api-key") ?? "");
      const storedModel = localStorage.getItem("selected-model");
      const nextModel = models.some((model) => model.id === storedModel)
        ? storedModel!
        : "";
      setSelectedModel(nextModel);
      setApiBaseUrl(localStorage.getItem("custom-api-base-url") ?? "");
    }
  }, [isOpen]);

  const handleSave = () => {
    setSaving(true);
    const normalizedKey = key.trim();
    const normalizedUrl = apiBaseUrl.trim();

    if (normalizedKey) {
      localStorage.setItem("dashscope-api-key", normalizedKey);
    } else {
      localStorage.removeItem("dashscope-api-key");
    }

    if (selectedModel) {
      localStorage.setItem("selected-model", selectedModel);
    } else {
      localStorage.removeItem("selected-model");
    }

    if (normalizedUrl) {
      localStorage.setItem("custom-api-base-url", normalizedUrl);
    } else {
      localStorage.removeItem("custom-api-base-url");
    }

    onSaved?.();
    message.success("系统设置已保存生效");

    window.setTimeout(() => {
      setSaving(false);
      onClose();
    }, 300);
  };

  return (
    <Modal
      open={isOpen}
      onCancel={onClose}
      footer={[
        <Button key="cancel" onClick={onClose}>
          取消
        </Button>,
        <Button
          key="submit"
          type="primary"
          loading={saving}
          onClick={handleSave}
          icon={<Check size={14} />}
        >
          保存生效
        </Button>,
      ]}
      title={
        <div className="settings-modal-header">
          <Sparkles size={18} className="settings-title-icon" />
          <span>系统偏好与模型设置</span>
        </div>
      }
      destroyOnClose
      width={560}
      className="ant-settings-modal"
    >
      <div className="settings-modal-body">
        {/* Model Selection */}
        <div className="setting-block">
          <label className="setting-label">
            <Cpu size={14} /> 默认推理模型
          </label>
          <div className="model-grid-cards">
            {models.map((m) => {
              const isSelected = selectedModel === m.id;
              return (
                <div
                  key={m.id}
                  className={`model-option-card ${isSelected ? "is-active" : ""}`}
                  onClick={() => setSelectedModel(m.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && setSelectedModel(m.id)}
                >
                  <div className="model-option-top">
                    <span className="model-option-name">{m.name}</span>
                    <span className="model-tag">{m.tag}</span>
                  </div>
                  <p className="model-option-desc">{m.desc}</p>
                </div>
              );
            })}
          </div>
        </div>

        {/* API Key */}
        <div className="setting-block">
          <label className="setting-label" htmlFor="dashscope-key">
            <KeyRound size={14} /> DashScope API Key
          </label>
          <Input.Password
            id="dashscope-key"
            value={key}
            placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
            onChange={(e) => setKey(e.target.value)}
            allowClear
          />
          <span className="setting-helper-text">
            留空时不发送请求头，由后端读取环境变量 <code>DASHSCOPE_API_KEY</code>。
          </span>
        </div>

        {/* API Base URL */}
        <div className="setting-block">
          <label className="setting-label" htmlFor="backend-url">
            <Server size={14} /> 后端服务地址（可选）
          </label>
          <Input
            id="backend-url"
            value={apiBaseUrl}
            placeholder="http://localhost:8000"
            onChange={(e) => setApiBaseUrl(e.target.value)}
            allowClear
          />
          <span className="setting-helper-text">
            留空则读取 <code>VITE_API_BASE_URL</code>，未配置时回退到 <code>http://localhost:8000</code>。
          </span>
        </div>
      </div>
    </Modal>
  );
}
