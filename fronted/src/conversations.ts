import type { Conversation, Message } from "./types";

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
