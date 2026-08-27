export type MessageRole = "user" | "assistant";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  chartUrl?: string;
  ragDebug?: unknown;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export type SourceKind = "pdf" | "text" | "url" | "image" | "audio" | "csv" | "vision";

export interface KnowledgeSource {
  id: string;
  name: string;
  kind: SourceKind;
  meta: string;
  status: "ready" | "processing" | "error";
}

export interface ChatResult {
  content: string;
  chartUrl?: string;
  ragDebug?: unknown;
}
