import { Sparkles } from "lucide-react";

export function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand" aria-label="Enterprise AI Copilot">
      <span className="brand-mark" aria-hidden="true">
        <Sparkles size={17} strokeWidth={2.2} />
      </span>
      {!compact && (
        <span className="brand-copy">
          <strong>Enterprise AI</strong>
          <small>Copilot</small>
        </span>
      )}
    </div>
  );
}
