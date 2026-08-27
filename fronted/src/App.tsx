import { Database, PanelLeftClose, PanelLeftOpen, SquarePen } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { sendChatMessage } from "./api/client";
import { Composer } from "./components/Composer";
import { MessageList } from "./components/MessageList";
import { SettingsModal } from "./components/SettingsModal";
import { Sidebar } from "./components/Sidebar";
import { SourcePanel } from "./components/SourcePanel";
import { Welcome } from "./components/Welcome";
import { starterSources } from "./data";
import type { KnowledgeSource, Message } from "./types";

function makeMessage(role: Message["role"], content: string): Message {
  return {
    id: `${role}-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    role,
    content,
    createdAt: new Date().toISOString(),
  };
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sourcePanelOpen, setSourcePanelOpen] = useState(false);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sources, setSources] = useState(starterSources);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const scrollAnchor = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollAnchor.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  const newChat = () => {
    setMessages([]);
    setDraft("");
    setSidebarOpen(false);
  };

  const send = async (suggestedPrompt?: string) => {
    const content = (suggestedPrompt ?? draft).trim();
    if (!content || isThinking) return;

    const userMessage = makeMessage("user", content);
    const previousMessages = messages;
    setMessages((items) => [...items, userMessage]);
    setDraft("");
    setIsThinking(true);

    try {
      const answer = await sendChatMessage(content, previousMessages);
      setMessages((items) => [...items, makeMessage("assistant", answer)]);
    } catch (error) {
      const reason = error instanceof Error ? error.message : "未知错误";
      setMessages((items) => [
        ...items,
        makeMessage(
          "assistant",
          `暂时无法连接到后端：${reason}。请检查服务配置。`,
        ),
      ]);
    } finally {
      setIsThinking(false);
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
    setMessages((prev) => prev.slice(0, lastUserIndex + 1));
    setIsThinking(true);
    const previousMessages = messages.slice(0, lastUserIndex);

    sendChatMessage(lastPrompt, previousMessages)
      .then((answer) => {
        setMessages((items) => [...items, makeMessage("assistant", answer)]);
      })
      .catch((error) => {
        const reason = error instanceof Error ? error.message : "未知错误";
        setMessages((items) => [
          ...items,
          makeMessage("assistant", `重新生成失败：${reason}`),
        ]);
      })
      .finally(() => {
        setIsThinking(false);
      });
  };

  const addSource = (source: KnowledgeSource) => {
    setSources((items) => [source, ...items]);
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
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          onNewChat={newChat}
          onClearSources={() => setSources([])}
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
                <Welcome onSelectPrompt={(prompt) => void send(prompt)} />
              </div>
              <div className={`conversation-state ${messages.length ? "" : "is-hidden"}`}>
                <MessageList
                  messages={messages}
                  isThinking={isThinking}
                  onRegenerate={regenerateLastMessage}
                />
                <div ref={scrollAnchor} />
              </div>
            </div>

            <Composer
              value={draft}
              disabled={isThinking}
              onChange={setDraft}
              onSend={() => void send()}
              onAddSource={addSource}
            />
          </section>
        </main>

        <div className="desktop-source-panel">
          <SourcePanel
            sources={sources}
            onRemove={(id) => setSources((items) => items.filter((item) => item.id !== id))}
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
            onRemove={(id) => setSources((items) => items.filter((item) => item.id !== id))}
            onCollapse={() => setSourcePanelOpen(false)}
          />
        </div>
      </div>

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
