import { Database, PanelLeftClose, PanelLeftOpen, SquarePen } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  addUrlSource,
  clearSources,
  deleteConversation as deletePersistedConversation,
  deleteSource,
  listConversations,
  listSources,
  renameConversation as renamePersistedConversation,
  streamChatMessage,
  uploadSource,
} from "./api/client";
import { Composer } from "./components/Composer";
import { MessageList } from "./components/MessageList";
import { SettingsModal } from "./components/SettingsModal";
import { Sidebar } from "./components/Sidebar";
import { SourcePanel } from "./components/SourcePanel";
import { Welcome } from "./components/Welcome";
import {
  createConversation,
  titleFromMessages,
} from "./conversations";
import type { ChatResult, Conversation, KnowledgeSource, Message, SourceKind } from "./types";

function makeMessage(
  role: Message["role"],
  content: string,
  result?: Pick<ChatResult, "chartUrl" | "ragDebug">,
): Message {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    role,
    content,
    createdAt: new Date().toISOString(),
    chartUrl: result?.chartUrl,
    ragDebug: result?.ragDebug,
  };
}

function getFileSize(file: File): string {
  return file.size > 1024 * 1024
    ? `${(file.size / 1024 / 1024).toFixed(1)} MB`
    : `${Math.max(1, Math.round(file.size / 1024))} KB`;
}

export default function App() {
  const [initialConversation] = useState(createConversation);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sourcePanelOpen, setSourcePanelOpen] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sources, setSources] = useState<KnowledgeSource[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>(
    [initialConversation],
  );
  const [activeConversationId, setActiveConversationId] = useState(
    initialConversation.id,
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState("正在思考...");
  const scrollAnchor = useRef<HTMLDivElement>(null);
  const streamAbortController = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollAnchor.current?.scrollIntoView({ behavior: isThinking ? "auto" : "smooth" });
  }, [messages, isThinking]);

  useEffect(() => {
    setConversations((items) => {
      const active = items.find((conversation) => conversation.id === activeConversationId);
      if (!active) return items;
      const title = active.title === "新对话"
        ? titleFromMessages(messages)
        : active.title;
      if (active.messages === messages && active.title === title) return items;
      const updated: Conversation = {
        ...active,
        title,
        messages,
        updatedAt: new Date().toISOString(),
      };
      return [updated, ...items.filter((conversation) => conversation.id !== activeConversationId)];
    });
  }, [activeConversationId, messages]);

  const refreshSources = () => {
    void listSources()
      .then(setSources)
      .catch((error) => {
        const reason = error instanceof Error ? error.message : "未知错误";
        setMessages((items) => [
          ...items,
          makeMessage("assistant", `读取知识来源失败：${reason}`),
        ]);
      });
  };

  useEffect(() => {
    refreshSources();
  }, []);

  useEffect(() => {
    let disposed = false;
    void listConversations()
      .then((remoteConversations) => {
        if (disposed || remoteConversations.length === 0) return;
        const active = remoteConversations[0];
        setConversations(remoteConversations.slice(0, 50));
        setActiveConversationId(active.id);
        setMessages(active.messages);
      })
      .catch(() => undefined);
    return () => {
      disposed = true;
    };
  }, []);

  const newChat = () => {
    if (isThinking) return;
    const active = conversations.find(
      (conversation) => conversation.id === activeConversationId,
    );
    if (active?.messages.length) {
      const conversation = createConversation();
      setConversations((items) => [conversation, ...items].slice(0, 50));
      setActiveConversationId(conversation.id);
      setMessages(conversation.messages);
    }
    setDraft("");
    setSidebarOpen(false);
  };

  const selectConversation = (conversationId: string) => {
    if (isThinking || conversationId === activeConversationId) return;
    const conversation = conversations.find((item) => item.id === conversationId);
    if (!conversation) return;
    setActiveConversationId(conversation.id);
    setMessages(conversation.messages);
    setDraft("");
    setSidebarOpen(false);
  };

  const deleteConversation = async (conversationId: string) => {
    if (isThinking) return;
    try {
      await deletePersistedConversation(conversationId);
    } catch (error) {
      const status = error instanceof Error && "status" in error
        ? (error as { status?: number }).status
        : undefined;
      // 新建但从未发送消息的本地对话尚未写入 SQLite。
      if (status !== 404) return;
    }
    setConversations((items) => {
      const remaining = items.filter((c) => c.id !== conversationId);
      if (remaining.length === 0) {
        const fresh = createConversation();
        setActiveConversationId(fresh.id);
        setMessages(fresh.messages);
        return [fresh];
      }
      if (activeConversationId === conversationId) {
        setActiveConversationId(remaining[0].id);
        setMessages(remaining[0].messages);
      }
      return remaining;
    });
  };

  const renameConversation = (conversationId: string, newTitle: string) => {
    setConversations((items) =>
      items.map((c) => (c.id === conversationId ? { ...c, title: newTitle } : c)),
    );
    void renamePersistedConversation(conversationId, newTitle).catch(() => {
      // 未发送消息的新对话尚未写入 SQLite，首次发送后会自动创建。
    });
  };

  const streamAnswer = async (
    prompt: string,
    conversationId: string,
    pendingMessage: Message,
    signal?: AbortSignal,
  ) => {
    const result = await streamChatMessage(
      prompt,
      conversationId,
      (delta) => {
        setMessages((items) => {
          const existing = items.find((item) => item.id === pendingMessage.id);
          if (!existing) {
            return [...items, { ...pendingMessage, content: delta }];
          }
          return items.map((item) =>
            item.id === pendingMessage.id
              ? { ...item, content: item.content + delta }
              : item,
          );
        });
      },
      setThinkingStatus,
      signal,
    );

    const finalMessage = makeMessage("assistant", result.content, result);
    finalMessage.id = pendingMessage.id;
    finalMessage.createdAt = pendingMessage.createdAt;
    setMessages((items) =>
      items.some((item) => item.id === pendingMessage.id)
        ? items.map((item) => (item.id === pendingMessage.id ? finalMessage : item))
        : [...items, finalMessage],
    );
  };

  const showStreamError = (pendingMessage: Message, text: string) => {
    setMessages((items) => {
      const existing = items.find((item) => item.id === pendingMessage.id);
      if (!existing) return [...items, { ...pendingMessage, content: text }];
      return items.map((item) =>
        item.id === pendingMessage.id
          ? { ...item, content: `${item.content}\n\n> ⚠️ ${text}` }
          : item,
      );
    });
  };

  const cancelStreaming = () => {
    if (streamAbortController.current) {
      streamAbortController.current.abort();
    }
  };

  const send = async (suggestedPrompt?: string) => {
    const content = (suggestedPrompt ?? draft).trim();
    if (!content || isThinking) return;

    const userMessage = makeMessage("user", content);
    const conversationId = activeConversationId;
    const pendingMessage = makeMessage("assistant", "");
    setMessages((items) => [...items, userMessage]);
    setDraft("");
    setThinkingStatus("正在识别问题类型...");
    setIsThinking(true);

    const controller = new AbortController();
    streamAbortController.current = controller;

    try {
      await streamAnswer(content, conversationId, pendingMessage, controller.signal);
    } catch (error) {
      if (controller.signal.aborted) {
        showStreamError(pendingMessage, "已停止生成。");
        return;
      }
      const reason = error instanceof Error ? error.message : "未知错误";
      showStreamError(
        pendingMessage,
        `暂时无法连接到后端：${reason}。请检查服务配置。`,
      );
    } finally {
      setIsThinking(false);
      streamAbortController.current = null;
    }
  };

  const regenerateLastMessage = () => {
    if (isThinking || messages.length === 0) return;
    let lastUserIndex = -1;
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "user") {
        lastUserIndex = i;
        break;
      }
    }
    if (lastUserIndex === -1) return;
    const lastPrompt = messages[lastUserIndex].content;
    const conversationId = activeConversationId;
    setMessages((prev) => prev.slice(0, lastUserIndex + 1));
    setThinkingStatus("正在识别问题类型...");
    setIsThinking(true);
    const pendingMessage = makeMessage("assistant", "");

    const controller = new AbortController();
    streamAbortController.current = controller;

    streamAnswer(lastPrompt, conversationId, pendingMessage, controller.signal)
      .catch((error) => {
        if (controller.signal.aborted) {
          showStreamError(pendingMessage, "已停止生成。");
          return;
        }
        const reason = error instanceof Error ? error.message : "未知错误";
        showStreamError(pendingMessage, `重新生成失败：${reason}`);
      })
      .finally(() => {
        setIsThinking(false);
        streamAbortController.current = null;
      });
  };

  const handleUploadFile = async (
    file: File,
    kind: Exclude<SourceKind, "url">,
  ) => {
    const pendingId = `pending-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const pendingSource: KnowledgeSource = {
      id: pendingId,
      name: file.name,
      kind,
      meta: getFileSize(file),
      status: "processing",
    };
    setSources((items) => [pendingSource, ...items]);

    try {
      const source = await uploadSource(file, kind);
      setSources((items) => items.map((item) => (item.id === pendingId ? source : item)));
    } catch (error) {
      const reason = error instanceof Error ? error.message : "上传失败";
      setSources((items) =>
        items.map((item) =>
          item.id === pendingId ? { ...item, status: "error", meta: reason } : item,
        ),
      );
    }
  };

  const handleAddUrl = async (url: string) => {
    const pendingId = `pending-url-${Date.now()}`;
    const pendingSource: KnowledgeSource = {
      id: pendingId,
      name: url.replace(/^https?:\/\//, ""),
      kind: "url",
      meta: "网页",
      status: "processing",
    };
    setSources((items) => [pendingSource, ...items]);

    try {
      const source = await addUrlSource(url);
      setSources((items) => items.map((item) => (item.id === pendingId ? source : item)));
    } catch (error) {
      const reason = error instanceof Error ? error.message : "网页导入失败";
      setSources((items) =>
        items.map((item) =>
          item.id === pendingId ? { ...item, status: "error", meta: reason } : item,
        ),
      );
    }
  };

  const handleRemoveSource = async (sourceId: string) => {
    const source = sources.find((item) => item.id === sourceId);
    if (!source) return;
    if (source.status === "error") {
      setSources((items) => items.filter((item) => item.id !== sourceId));
      return;
    }

    setSources((items) => items.filter((item) => item.id !== sourceId));
    try {
      await deleteSource(sourceId);
    } catch (error) {
      const reason = error instanceof Error ? error.message : "删除失败";
      setSources((items) => [{ ...source, status: "error", meta: reason }, ...items]);
    }
  };

  const handleClearSources = async () => {
    const previousSources = sources;
    setSources([]);
    try {
      await clearSources();
    } catch (error) {
      setSources(previousSources);
      const reason = error instanceof Error ? error.message : "清空失败";
      setMessages((items) => [
        ...items,
        makeMessage("assistant", `清空资料失败：${reason}`),
      ]);
    }
  };

  const toggleLeftPanel = () => {
    if (window.matchMedia("(max-width: 760px)").matches) {
      setSidebarOpen((prev) => !prev);
    } else {
      setLeftCollapsed((prev) => !prev);
    }
  };

  const toggleRightPanel = () => {
    if (window.matchMedia("(max-width: 1120px)").matches) {
      setSourcePanelOpen((prev) => !prev);
    } else {
      setRightCollapsed((prev) => !prev);
    }
  };

  return (
    <div className={`app-root ${sidebarOpen ? "is-mobile-sidebar-open" : ""}`}>
      {/* Mobile Scrim */}
      <button
        className={`sidebar-scrim ${sidebarOpen ? "is-visible" : ""}`}
        aria-label="关闭侧边栏"
        onClick={() => setSidebarOpen(false)}
      />

      {/* 3-Column Grid Shell */}
      <div
        className={`app-shell ${leftCollapsed ? "is-left-collapsed" : ""} ${
          rightCollapsed ? "is-right-collapsed" : ""
        }`}
      >
        <Sidebar
          sourceCount={sources.length}
          conversations={conversations}
          activeConversationId={activeConversationId}
          isOpen={sidebarOpen}
          disabled={isThinking}
          onClose={() => setSidebarOpen(false)}
          onNewChat={newChat}
          onSelectConversation={selectConversation}
          onDeleteConversation={deleteConversation}
          onRenameConversation={renameConversation}
          onClearSources={() => void handleClearSources()}
          onOpenSettings={() => setSettingsOpen(true)}
        />

        <main className="main-panel">
          {/* Minimal macOS Topbar */}
          <header className="topbar">
            <div className="topbar-left">
              <button
                className="icon-btn-apple"
                onClick={toggleLeftPanel}
                aria-label={leftCollapsed ? "展开侧边栏" : "收起侧边栏"}
                title={leftCollapsed ? "展开侧边栏" : "收起侧边栏"}
              >
                {leftCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
              </button>
              <span className="topbar-title">Enterprise Copilot</span>
            </div>

            <div className="topbar-right">
              {messages.length > 0 && (
                <button
                  className="icon-btn-apple"
                  onClick={newChat}
                  disabled={isThinking}
                  title="新建对话"
                  aria-label="新建对话"
                >
                  <SquarePen size={16} />
                </button>
              )}
              <button
                className={`topbar-pill-btn ${!rightCollapsed ? "is-active" : ""}`}
                onClick={toggleRightPanel}
                title="知识来源"
                aria-label="知识来源"
              >
                <Database size={13} />
                <span>{sources.length}</span>
              </button>
            </div>
          </header>

          {/* Chat Surface */}
          <section className="chat-surface">
            <div className={`chat-content ${messages.length ? "has-messages" : "is-empty"}`}>
              <div className={`welcome-state ${messages.length ? "is-hidden" : ""}`}>
                <Welcome />
              </div>
              <div className={`conversation-state ${messages.length ? "" : "is-hidden"}`}>
                <MessageList
                  messages={messages}
                  isThinking={isThinking}
                  thinkingStatus={thinkingStatus}
                  onRegenerate={regenerateLastMessage}
                />
                <div ref={scrollAnchor} />
              </div>
            </div>

            <Composer
              value={draft}
              disabled={isThinking}
              isThinking={isThinking}
              onChange={setDraft}
              onSend={() => void send()}
              onCancel={cancelStreaming}
              onUploadFile={(file, kind) => void handleUploadFile(file, kind)}
              onAddUrl={(url) => void handleAddUrl(url)}
            />
          </section>
        </main>

        <div className="desktop-source-panel">
          <SourcePanel
            sources={sources}
            onRemove={(id) => void handleRemoveSource(id)}
            onCollapse={() => setRightCollapsed(true)}
          />
        </div>
      </div>

      {/* Mobile Drawer */}
      <div className={`source-drawer ${sourcePanelOpen ? "is-open" : ""}`}>
        <button
          className="source-drawer-scrim"
          aria-label="关闭知识来源"
          onClick={() => setSourcePanelOpen(false)}
        />
        <div className="source-drawer-content">
          <SourcePanel
            sources={sources}
            onRemove={(id) => void handleRemoveSource(id)}
            onCollapse={() => setSourcePanelOpen(false)}
          />
        </div>
      </div>

      <SettingsModal
        isOpen={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={refreshSources}
      />
    </div>
  );
}
