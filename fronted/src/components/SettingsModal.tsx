import { Check, Cpu, Eye, EyeOff, KeyRound, Server, X } from "lucide-react";
import { useEffect, useState } from "react";

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

const models = [
  { id: "", name: "跟随后端配置", desc: "不覆盖后端模型，使用环境变量或服务端默认值" },
  { id: "qwen-plus", name: "Qwen-Plus", desc: "通用均衡 · 推荐用于企业常规知识检索与对话" },
  { id: "qwen-max", name: "Qwen-Max", desc: "旗舰推理 · 复杂逻辑梳理、代码生成与长文本洞察" },
];

export function SettingsModal({ isOpen, onClose, onSaved }: SettingsModalProps) {
  const [key, setKey] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [apiBaseUrl, setApiBaseUrl] = useState("");
  const [visible, setVisible] = useState(false);
  const [saved, setSaved] = useState(false);

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

  if (!isOpen) return null;

  const save = () => {
    const normalizedKey = key.trim();
    const normalizedUrl = apiBaseUrl.trim();
    if (normalizedKey) localStorage.setItem("dashscope-api-key", normalizedKey);
    else localStorage.removeItem("dashscope-api-key");
    if (selectedModel) localStorage.setItem("selected-model", selectedModel);
    else localStorage.removeItem("selected-model");
    if (normalizedUrl) localStorage.setItem("custom-api-base-url", normalizedUrl);
    else localStorage.removeItem("custom-api-base-url");
    onSaved?.();
    setSaved(true);
    window.setTimeout(() => {
      setSaved(false);
      onClose();
    }, 600);
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="settings-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="modal-heading">
          <div className="heading-left">
            <span className="eyebrow">系统偏好</span>
            <h2 id="settings-title">模型与环境配置</h2>
          </div>
          <button className="icon-button modal-close-btn" onClick={onClose} aria-label="关闭设置">
            <X size={18} />
          </button>
        </div>

        <div className="modal-body">
          {/* Model Selection */}
          <div className="setting-section">
            <label className="field-label">
              <Cpu size={14} /> 默认推理模型
            </label>
            <div className="model-choice-grid">
              {models.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className={`model-card ${selectedModel === m.id ? "is-selected" : ""}`}
                  onClick={() => setSelectedModel(m.id)}
                >
                  <div className="model-card-top">
                    <strong>{m.name}</strong>
                    {selectedModel === m.id && <span className="model-active-badge">使用中</span>}
                  </div>
                  <p>{m.desc}</p>
                </button>
              ))}
            </div>
          </div>

          {/* API Key Field */}
          <div className="setting-section">
            <label className="field-label" htmlFor="api-key">
              <KeyRound size={14} /> DashScope API Key
            </label>
            <div className="password-field">
              <input
                id="api-key"
                type={visible ? "text" : "password"}
                value={key}
                placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
                onChange={(event) => setKey(event.target.value)}
              />
              <button
                type="button"
                className="eye-toggle-btn"
                onClick={() => setVisible((current) => !current)}
                aria-label={visible ? "隐藏密钥" : "显示密钥"}
              >
                {visible ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            <p className="field-help">留空时不发送密钥，由后端读取 <code>DASHSCOPE_API_KEY</code>。</p>
          </div>

          {/* API Base URL Field */}
          <div className="setting-section">
            <label className="field-label" htmlFor="api-url">
              <Server size={14} /> 后端服务地址 (可选)
            </label>
            <input
              id="api-url"
              className="text-input"
              type="text"
              value={apiBaseUrl}
              placeholder="http://localhost:8000"
              onChange={(event) => setApiBaseUrl(event.target.value)}
            />
            <p className="field-help">留空则读取 <code>VITE_API_BASE_URL</code>，未配置时使用 http://localhost:8000。</p>
          </div>
        </div>

        <div className="modal-actions">
          <button className="button-secondary" onClick={onClose}>
            取消
          </button>
          <button className={`button-primary ${saved ? "is-saved" : ""}`} onClick={save}>
            {saved ? (
              <>
                <Check size={16} /> 已保存生效
              </>
            ) : (
              "保存配置"
            )}
          </button>
        </div>
      </section>
    </div>
  );
}
