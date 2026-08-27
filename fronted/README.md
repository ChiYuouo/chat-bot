# Enterprise AI Copilot React 前端

这是现有 Streamlit 页面的 React 版本，当前包含完整界面交互和本地预览数据。

## 启动

```powershell
cd fronted
pnpm install
pnpm dev
```

浏览器访问 `http://localhost:5173`。

## 接入后端

复制 `.env.example` 为 `.env.local`，设置：

```text
VITE_API_BASE_URL=http://localhost:8000
```

前端会调用 `POST /api/chat`：

```json
{
  "message": "用户问题",
  "history": [{ "role": "user", "content": "历史消息" }]
}
```

后端返回：

```json
{ "content": "助手回答" }
```

未设置 `VITE_API_BASE_URL` 时，页面自动使用本地演示回答。
