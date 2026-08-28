import { Bubble, ThoughtChain, type ThoughtChainItemType } from "@ant-design/x";
import {
  Brain,
  Check,
  Copy,
  Database,
  FileSearch,
  RotateCcw,
  Sparkles,
  User,
} from "lucide-react";
import React, { useState } from "react";
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

interface RagDebugData {
  rewritten_query?: string;
  rewrite?: Record<string, unknown>;
  retrieval?: Record<string, unknown>;
  rerank?: Record<string, unknown>;
  final_chunk_ids?: string[];
  timings_ms?: {
    total_ms?: number;
    retrieve_ms?: number;
    rerank_ms?: number;
    rewrite_ms?: number;
  };
  adaptive_rag_error?: string;
  [key: string]: unknown;
}

function parseThoughtChainItems(
  ragDebug: unknown,
  isStreaming: boolean,
  thinkingStatus: string,
): ThoughtChainItemType[] {
  const items: ThoughtChainItemType[] = [];

  if (isStreaming) {
    items.push({
      key: "streaming-thought",
      icon: <Brain size={14} className="text-primary" />,
      title: thinkingStatus || "正在思考与处理...",
      status: "loading",
      blink: true,
    });
    return items;
  }

  if (!ragDebug || typeof ragDebug !== "object") {
    return items;
  }

  const debug = ragDebug as RagDebugData;

  if (debug.adaptive_rag_error) {
    items.push({
      key: "rag-fallback",
      icon: <Database size={14} />,
      title: "自适应检索降级",
      status: "error",
      description: String(debug.adaptive_rag_error),
    });
    return items;
  }

  if (debug.rewritten_query) {
    items.push({
      key: "rag-rewrite",
      icon: <FileSearch size={14} />,
      title: "意图理解与检索改写",
      status: "success",
      description: `已将问题对齐为：“${debug.rewritten_query}”`,
    });
  }

  const chunkCount = Array.isArray(debug.final_chunk_ids)
    ? debug.final_chunk_ids.length
    : undefined;
  const timingText =
    debug.timings_ms?.total_ms !== undefined
      ? `（耗时 ${(debug.timings_ms.total_ms / 1000).toFixed(2)}s）`
      : "";

  items.push({
    key: "rag-retrieval",
    icon: <Database size={14} />,
    title: "知识库混合检索与精排",
    status: "success",
    description:
      chunkCount !== undefined
        ? `命中 ${chunkCount} 个相关资料切片 ${timingText}`
        : `知识检索完成 ${timingText}`,
    collapsible: true,
    content: (
      <div className="thought-chain-debug-box">
        <pre>{JSON.stringify(ragDebug, null, 2)}</pre>
      </div>
    ),
  });

  return items;
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

  const bubbleItems = messages.map((message, index) => {
    const isUser = message.role === "user";
    const isLast = index === messages.length - 1;
    const isStreamingMessage = isReceivingAnswer && isLast;
    const isCopied = copiedId === message.id;

    const thoughtChainItems = !isUser
      ? parseThoughtChainItems(
          message.ragDebug,
          isStreamingMessage && !message.content,
          thinkingStatus,
        )
      : [];

    return {
      key: message.id,
      role: isUser ? "user" : "assistant",
      avatar: isUser ? (
        <div className="user-avatar-badge" title="用户">
          <User size={15} />
        </div>
      ) : (
        <div className="assistant-avatar-badge" title="Enterprise Copilot">
          <Sparkles size={15} />
        </div>
      ),
      content: (
        <div className="bubble-message-content">
          {thoughtChainItems.length > 0 && (
            <div className="thought-chain-wrapper">
              <ThoughtChain items={thoughtChainItems} defaultExpandedKeys={[]} />
            </div>
          )}

          {isUser ? (
            <div className="plain-message-text">{message.content}</div>
          ) : message.content ? (
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
          ) : null}

          {message.chartUrl && (
            <div className="message-chart-wrap">
              <img
                className="message-chart"
                src={message.chartUrl}
                alt="数据分析图表"
              />
            </div>
          )}
        </div>
      ),
      footer:
        !isUser && !isStreamingMessage && message.content ? (
          <div className="bubble-footer-actions">
            <button
              className="bubble-action-btn"
              onClick={() => handleCopy(message.id, message.content)}
              title={isCopied ? "已复制" : "复制"}
              type="button"
            >
              {isCopied ? <Check size={13} /> : <Copy size={13} />}
              <span>{isCopied ? "已复制" : "复制"}</span>
            </button>

            {isLast && onRegenerate && (
              <button
                className="bubble-action-btn"
                onClick={onRegenerate}
                title="重新生成"
                type="button"
              >
                <RotateCcw size={13} />
                <span>重试</span>
              </button>
            )}
          </div>
        ) : undefined,
    };
  });

  return (
    <div className="ant-bubble-list-wrapper" aria-live="polite">
      <Bubble.List
        items={bubbleItems}
        role={{
          user: {
            placement: "end",
            variant: "filled",
            shape: "round",
          },
          assistant: {
            placement: "start",
            variant: "borderless",
            shape: "default",
          },
        }}
      />

      {isThinking && !isReceivingAnswer && (
        <div className="thinking-bubble-row">
          <div className="assistant-avatar-badge">
            <Sparkles size={15} />
          </div>
          <div className="thinking-thought-chain">
            <ThoughtChain
              items={[
                {
                  key: "pending-thought",
                  icon: <Brain size={14} />,
                  title: thinkingStatus,
                  status: "loading",
                  blink: true,
                },
              ]}
            />
          </div>
        </div>
      )}
    </div>
  );
}
