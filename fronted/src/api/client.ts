import type { Message } from "../types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export async function sendChatMessage(
  content: string,
  history: Message[],
): Promise<string> {
  if (!API_BASE_URL) {
    await new Promise((resolve) => window.setTimeout(resolve, 700));
    return `这是 React 前端的交互预览。你刚才的问题是：“${content}”\n\n配置 VITE_API_BASE_URL 并实现 POST /api/chat 后，就可以接入项目现有的 RAG、数据分析和图片识别能力。`;
  }

  const response = await fetch(`${API_BASE_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: content,
      history: history.map(({ role, content: messageContent }) => ({
        role,
        content: messageContent,
      })),
    }),
  });

  if (!response.ok) {
    throw new Error(`请求失败（${response.status}）`);
  }

  const data = (await response.json()) as { content?: string };
  if (!data.content) {
    throw new Error("接口没有返回回答内容");
  }
  return data.content;
}
