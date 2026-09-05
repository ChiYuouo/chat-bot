import type {
  ChatResult,
  Conversation,
  KnowledgeSource,
  Message,
  SourceKind,
} from "../types";

const DEFAULT_TIMEOUT_MS = 120_000;
const DEFAULT_API_BASE_URL = "http://localhost:8000";
const SUPPORTED_MODELS = new Set(["qwen-plus", "qwen-max"]);

interface ApiErrorBody {
  detail?: string | { message?: string };
  message?: string;
}

interface BackendSource {
  source_id?: string;
  id?: string;
  name: string;
  modality?: SourceKind;
  kind?: SourceKind;
  chunk_count?: number;
  duration_seconds?: number | null;
  meta?: string;
  status?: KnowledgeSource["status"];
}

interface BackendChatResponse {
  content?: string;
  chart_url?: string | null;
  rag_debug?: unknown;
}

interface BackendChatStreamEvent extends BackendChatResponse {
  type?: "status" | "delta" | "done" | "error";
  message?: string;
}

interface BackendConversation {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
  messages: Array<{
    role: Message["role"];
    content: string;
    created_at: number;
  }>;
}

export interface CurrentUser {
  id: string;
  email: string;
}

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function getApiBaseUrl(): string {
  const configured = localStorage.getItem("custom-api-base-url")?.trim();
  const fromEnvironment = import.meta.env.VITE_API_BASE_URL?.trim();
  return (configured || fromEnvironment || DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

function getRequestHeaders(): Headers {
  const headers = new Headers({ Accept: "application/json" });
  const apiKey = localStorage.getItem("dashscope-api-key")?.trim();
  const model = localStorage.getItem("selected-model")?.trim();

  if (apiKey) headers.set("X-DashScope-Api-Key", apiKey);
  if (model && SUPPORTED_MODELS.has(model)) {
    headers.set("X-Model", model);
  } else if (model) {
    localStorage.removeItem("selected-model");
  }
  return headers;
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (typeof body.detail === "string") return body.detail;
    if (body.detail && typeof body.detail === "object" && body.detail.message) {
      return body.detail.message;
    }
    if (body.message) return body.message;
  } catch {
    // 非 JSON 错误响应使用统一状态提示。
  }
  return `请求失败（${response.status}）`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  const headers = getRequestHeaders();
  new Headers(init.headers).forEach((value, key) => headers.set(key, value));

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
    if (!response.ok) throw new ApiError(await readError(response), response.status);
    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求超时，请稍后重试");
    }
    throw new ApiError(error instanceof Error ? error.message : "无法连接到后端服务");
  } finally {
    window.clearTimeout(timeoutId);
  }
}

function formatDuration(totalSeconds: number): string {
  const seconds = Math.max(0, Math.round(totalSeconds));
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function normalizeSource(source: BackendSource): KnowledgeSource {
  const kind = source.modality ?? source.kind ?? "text";
  const details = [
    typeof source.duration_seconds === "number"
      ? formatDuration(source.duration_seconds)
      : null,
    typeof source.chunk_count === "number" ? `${source.chunk_count} 个片段` : null,
  ].filter(Boolean);

  return {
    id: source.source_id ?? source.id ?? crypto.randomUUID(),
    name: source.name,
    kind,
    meta: source.meta ?? (details.join(" · ") || "已就绪"),
    status: source.status ?? "ready",
  };
}

function isoTime(timestamp: number): string {
  return new Date(timestamp * 1000).toISOString();
}

function normalizeConversation(conversation: BackendConversation): Conversation {
  return {
    id: conversation.id,
    title: conversation.title,
    createdAt: isoTime(conversation.created_at),
    updatedAt: isoTime(conversation.updated_at),
    messages: conversation.messages.map((message, index) => ({
      id: `${conversation.id}-${index}-${message.created_at}`,
      role: message.role,
      content: message.content,
      createdAt: isoTime(message.created_at),
    })),
  };
}

export async function sendChatMessage(
  content: string,
  conversationId: string,
): Promise<ChatResult> {
  const response = await request<BackendChatResponse>("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: content,
      conversation_id: conversationId,
    }),
  });

  if (!response.content) throw new ApiError("接口没有返回回答内容");
  return {
    content: response.content,
    chartUrl: response.chart_url ?? undefined,
    ragDebug: response.rag_debug ?? undefined,
  };
}

export async function streamChatMessage(
  content: string,
  conversationId: string,
  onDelta: (content: string) => void,
  onStatus?: (content: string) => void,
  signal?: AbortSignal,
): Promise<ChatResult> {
  const controller = new AbortController();
  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", () => controller.abort(), { once: true });
    }
  }
  let timeoutId = 0;
  const resetTimeout = () => {
    window.clearTimeout(timeoutId);
    timeoutId = window.setTimeout(() => controller.abort(), DEFAULT_TIMEOUT_MS);
  };
  resetTimeout();

  const headers = getRequestHeaders();
  headers.set("Accept", "application/x-ndjson");
  headers.set("Content-Type", "application/json");

  try {
    const response = await fetch(`${getApiBaseUrl()}/api/chat/stream`, {
      method: "POST",
      headers,
      credentials: "include",
      signal: controller.signal,
      body: JSON.stringify({
        message: content,
        conversation_id: conversationId,
      }),
    });

    if (!response.ok) throw new ApiError(await readError(response), response.status);
    if (!response.body) throw new ApiError("当前浏览器不支持流式响应");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let result: ChatResult | undefined;

    const consumeLine = (line: string) => {
      if (!line.trim()) return;
      let event: BackendChatStreamEvent;
      try {
        event = JSON.parse(line) as BackendChatStreamEvent;
      } catch {
        throw new ApiError("流式响应格式无效");
      }

      if (event.type === "delta" && event.content) {
        onDelta(event.content);
      } else if (event.type === "status" && event.content) {
        onStatus?.(event.content);
      } else if (event.type === "done") {
        if (!event.content) throw new ApiError("接口没有返回回答内容");
        result = {
          content: event.content,
          chartUrl: event.chart_url ?? undefined,
          ragDebug: event.rag_debug ?? undefined,
        };
      } else if (event.type === "error") {
        throw new ApiError(event.message || "生成回答失败");
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      resetTimeout();
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      lines.forEach(consumeLine);
    }

    buffer += decoder.decode();
    consumeLine(buffer);
    if (!result) throw new ApiError("流式响应意外结束");
    return result;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError("请求超时，请稍后重试");
    }
    throw new ApiError(error instanceof Error ? error.message : "无法连接到后端服务");
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function listSources(): Promise<KnowledgeSource[]> {
  const response = await request<BackendSource[] | { sources: BackendSource[] }>(
    "/api/sources",
  );
  const sources = Array.isArray(response) ? response : response.sources;
  return sources.map(normalizeSource);
}

export async function uploadSource(
  file: File,
  kind: Exclude<SourceKind, "url">,
): Promise<KnowledgeSource> {
  const body = new FormData();
  body.append("file", file);
  body.append("kind", kind);
  const response = await request<BackendSource | { source: BackendSource }>(
    "/api/sources",
    { method: "POST", body },
  );
  return normalizeSource("source" in response ? response.source : response);
}

export async function addUrlSource(url: string, title?: string): Promise<KnowledgeSource> {
  const response = await request<BackendSource | { source: BackendSource }>(
    "/api/sources/url",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title: title?.trim() || undefined }),
    },
  );
  return normalizeSource("source" in response ? response.source : response);
}

export async function deleteSource(sourceId: string): Promise<void> {
  await request<void>(`/api/sources/${encodeURIComponent(sourceId)}`, {
    method: "DELETE",
  });
}

export async function clearSources(): Promise<void> {
  await request<void>("/api/sources", { method: "DELETE" });
}

export async function listConversations(): Promise<Conversation[]> {
  const response = await request<{ conversations: BackendConversation[] }>(
    "/api/conversations",
  );
  return response.conversations.map(normalizeConversation);
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await request<void>(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
  });
}

export async function renameConversation(conversationId: string, title: string): Promise<void> {
  await request<void>(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const response = await request<{ user: CurrentUser | null }>("/api/auth/me");
  return response.user;
}

async function authenticate(
  path: "/api/auth/login" | "/api/auth/register",
  email: string,
  password: string,
): Promise<CurrentUser> {
  return request<CurrentUser>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function register(email: string, password: string): Promise<CurrentUser> {
  return authenticate("/api/auth/register", email, password);
}

export function login(email: string, password: string): Promise<CurrentUser> {
  return authenticate("/api/auth/login", email, password);
}

export async function logout(): Promise<void> {
  await request<void>("/api/auth/logout", { method: "POST" });
}
