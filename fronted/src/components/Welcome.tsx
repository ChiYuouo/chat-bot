import { Sparkles } from "lucide-react";

export function Welcome() {
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

    </section>
  );
}
