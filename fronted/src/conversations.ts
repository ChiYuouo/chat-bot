import type { Conversation, Message } from "./types";

const STORAGE_KEY = "copilot-conversations-v1";
const MAX_CONVERSATIONS = 50;

interface ConversationState {
  conversations: Conversation[];
  activeConversationId: string;
}

function isMessage(value: unknown): value is Message {
  if (!value || typeof value !== "object") return false;
  const message = value as Partial<Message>;
  return (
    typeof message.id === "string" &&
    (message.role === "user" || message.role === "assistant") &&
    typeof message.content === "string" &&
    typeof message.createdAt === "string"
  );
}

function isConversation(value: unknown): value is Conversation {
  if (!value || typeof value !== "object") return false;
  const conversation = value as Partial<Conversation>;
  return (
    typeof conversation.id === "string" &&
    typeof conversation.title === "string" &&
    typeof conversation.createdAt === "string" &&
    typeof conversation.updatedAt === "string" &&
    Array.isArray(conversation.messages) &&
    conversation.messages.every(isMessage)
  );
}

export function createConversation(): Conversation {
  const now = new Date().toISOString();
  return {
    id: crypto.randomUUID(),
    title: "新对话",
    messages: [],
    createdAt: now,
    updatedAt: now,
  };
}

export function titleFromMessages(messages: Message[]): string {
  const firstQuestion = messages.find((message) => message.role === "user")?.content;
  if (!firstQuestion) return "新对话";
  const title = firstQuestion.replace(/\s+/g, " ").trim();
  return title.length > 24 ? `${title.slice(0, 24)}…` : title;
}

export function loadConversationState(): ConversationState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<ConversationState>;
      const conversations = Array.isArray(parsed.conversations)
        ? parsed.conversations.filter(isConversation).slice(0, MAX_CONVERSATIONS)
        : [];
      if (conversations.length > 0) {
        const activeConversationId = conversations.some(
          (conversation) => conversation.id === parsed.activeConversationId,
        )
          ? parsed.activeConversationId!
          : conversations[0].id;
        return { conversations, activeConversationId };
      }
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
  }

  const conversation = createConversation();
  return {
    conversations: [conversation],
    activeConversationId: conversation.id,
  };
}

export function saveConversationState(
  conversations: Conversation[],
  activeConversationId: string,
): void {
  try {
    const serializable = conversations.slice(0, MAX_CONVERSATIONS).map((conversation) => ({
      ...conversation,
      messages: conversation.messages.slice(-100).map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
        createdAt: message.createdAt,
      })),
    }));
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ conversations: serializable, activeConversationId }),
    );
  } catch {
    // LocalStorage 不可用或容量不足时，对话仍可在当前页面继续使用。
  }
}
