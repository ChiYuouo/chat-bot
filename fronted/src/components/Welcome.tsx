import { ArrowUpRight, Sparkles } from "lucide-react";

interface WelcomeProps {
  onSelectPrompt?: (prompt: string) => void;
}

const suggestions = [
  "分析 Q2 销售报表并总结核心增长趋势",
  "检索最新的员工差旅与住宿报销标准",
  "提炼周会录音中的关键决议与后续待办",
];

export function Welcome({ onSelectPrompt }: WelcomeProps) {
  return (
    <section className="welcome">
      <div className="welcome-hero">
        <div className="apple-ai-icon" aria-hidden="true">
          <Sparkles size={26} strokeWidth={2} />
        </div>
        <h1>今天能为你做些什么？</h1>
        <p className="welcome-subtitle">
          连接企业私有文档与业务数据，为你提供精准检索与智能分析。
        </p>
      </div>

      <div className="suggestion-pills">
        {suggestions.map((prompt) => (
          <button
            key={prompt}
            className="suggestion-pill"
            onClick={() => onSelectPrompt?.(prompt)}
          >
            <span>{prompt}</span>
            <ArrowUpRight size={14} className="pill-arrow" />
          </button>
        ))}
      </div>
    </section>
  );
}
