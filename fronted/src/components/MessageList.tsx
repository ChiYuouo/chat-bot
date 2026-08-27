import { Check, Copy, RotateCcw } from "lucide-react";
import { useState } from "react";
import type { Message } from "../types";

interface MessageListProps {
  messages: Message[];
  isThinking: boolean;
  onRegenerate?: () => void;
}

export function MessageList({ messages, isThinking, onRegenerate }: MessageListProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleCopy = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1800);
    } catch {
      // Fallback
    }
  };

  return (
    <div className="message-list" aria-live="polite">
      {messages.map((message) => {
        const isUser = message.role === "user";
        const isCopied = copiedId === message.id;

        return (
          <article className={`message-row message-${message.role}`} key={message.id}>
            <div className="message-bubble-wrap">
              <div className="message-bubble">
                {message.content.split("\n").map((line, index) => (
                  <p key={`${message.id}-${index}`}>{line || <br />}</p>
                ))}
              </div>

              {!isUser && (
                <div className="message-actions-apple">
                  <button
                    className="action-pill"
                    onClick={() => handleCopy(message.id, message.content)}
                    title={isCopied ? "已复制" : "复制"}
                  >
                    {isCopied ? <Check size={12} /> : <Copy size={12} />}
                    <span>{isCopied ? "已复制" : "复制"}</span>
                  </button>

                  {onRegenerate && (
                    <button className="action-pill" onClick={onRegenerate} title="重新生成">
                      <RotateCcw size={12} />
                      <span>重试</span>
                    </button>
                  )}
                </div>
              )}
            </div>
          </article>
        );
      })}

      {isThinking && (
        <article className="message-row message-assistant">
          <div className="thinking-bubble-apple">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        </article>
      )}
    </div>
  );
}
