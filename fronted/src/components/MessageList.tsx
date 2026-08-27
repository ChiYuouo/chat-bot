import { Check, Copy, RotateCcw } from "lucide-react";
import { useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import type { Message } from "../types";

interface MessageListProps {
  messages: Message[];
  isThinking: boolean;
  thinkingStatus: string;
  onRegenerate?: () => void;
}

export function MessageList({
  messages,
  isThinking,
  thinkingStatus,
  onRegenerate,
}: MessageListProps) {
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const lastMessage = messages[messages.length - 1];
  const isReceivingAnswer = isThinking && lastMessage?.role === "assistant";

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
        const isStreamingMessage = isReceivingAnswer && message.id === lastMessage.id;

        return (
          <article className={`message-row message-${message.role}`} key={message.id}>
            <div className="message-bubble-wrap">
              <div className="message-bubble">
                {isUser ? (
                  <p className="plain-message">{message.content}</p>
                ) : (
                  <div className="markdown-content">
                    <ReactMarkdown
                      remarkPlugins={[remarkGfm]}
                      rehypePlugins={[rehypeSanitize]}
                      components={{
                        a: ({ ...props }) => (
                          <a {...props} target="_blank" rel="noreferrer noopener" />
                        ),
                      }}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                )}
                {message.chartUrl && (
                  <img className="message-chart" src={message.chartUrl} alt="数据分析图表" />
                )}
                {message.ragDebug !== undefined && (
                  <details className="rag-debug">
                    <summary>查看 RAG 检索过程</summary>
                    <pre>{JSON.stringify(message.ragDebug, null, 2)}</pre>
                  </details>
                )}
              </div>

              {!isUser && !isStreamingMessage && (
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

      {isThinking && !isReceivingAnswer && (
        <article className="message-row message-assistant">
          <div className="thinking-bubble-apple">
            <span className="thinking-status">{thinkingStatus}</span>
            <span className="thinking-dots" aria-hidden="true">
              <span className="dot" />
              <span className="dot" />
              <span className="dot" />
            </span>
          </div>
        </article>
      )}
    </div>
  );
}
