# Enterprise AI Copilot React 前端

这是现有 Streamlit 页面的 React 版本。前端 API 层已按 Python 后端现有的数据模型设计，不改变意图路由、RAG、数据分析、识图或资料解析逻辑。

## 启动

```powershell
cd fronted
pnpm install
pnpm dev
```

浏览器访问 `http://localhost:5173`。

复制 `.env.example` 为 `.env.local`，配置后端地址：

```text
VITE_API_BASE_URL=http://localhost:8000
```

“系统设置”中填写的后端地址会覆盖环境变量。请求默认携带 Cookie，以便后端按浏览器会话隔离知识库与临时文件。

系统设置中的 API Key、模型和后端地址都可以留空：API Key 与模型由后端配置决定，后端地址依次回退到 `VITE_API_BASE_URL` 和 `http://localhost:8000`。

最近对话保存在浏览器 LocalStorage 中。新建或切换对话时，前端会向聊天接口发送对应的 `conversation_id` 和消息历史，后端会分别保存每个对话的上一轮意图；知识来源仍在当前浏览器会话中共享。

## API 契约

### 1. 发送消息

`POST /api/chat`

```json
{
  "message": "用户问题",
  "conversation_id": "前端对话 ID",
  "history": [
    { "role": "user", "content": "历史消息" },
    { "role": "assistant", "content": "历史回答" }
  ]
}
```

响应字段与 `app.router.process_user_message` 的结果保持一致；图表由 HTTP 适配层转换成浏览器可访问的 URL：

```json
{
  "content": "助手回答",
  "chart_url": "/api/assets/chart-id",
  "rag_debug": {}
}
```

`chart_url` 和 `rag_debug` 可以省略。

### 2. 查询当前会话资料

`GET /api/sources`

响应可以是数组，也可以使用 `{ "sources": [] }` 包装。知识库资料沿用后端 `KnowledgeSource` 字段：

```json
{
  "source_id": "source-id",
  "name": "员工手册.pdf",
  "modality": "pdf",
  "chunk_count": 42,
  "duration_seconds": null
}
```

### 3. 上传文件

`POST /api/sources`，请求类型为 `multipart/form-data`：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `file` | File | 原始文件 |
| `kind` | string | `pdf`、`text`、`image`、`audio`、`csv` 或 `vision` |

响应为上面的资料对象，也可以使用 `{ "source": {} }` 包装。`csv` 表示当前会话的数据分析文件；`vision` 表示当前会话的临时识图文件。

### 4. 添加网页

`POST /api/sources/url`

```json
{
  "url": "https://example.com/article",
  "title": "可选标题"
}
```

### 5. 删除资料

- `DELETE /api/sources/{source_id}`：删除单个资料。
- `DELETE /api/sources`：清空当前会话的全部资料。

删除成功返回 `204 No Content`。

### 通用约定

- 设置页中的 DashScope Key 通过 `X-DashScope-Api-Key` 请求头发送，模型通过 `X-Model` 发送；两者均为可选。
- 非 2xx 响应使用 `{ "detail": "错误信息" }` 或 `{ "message": "错误信息" }`。
- 前端请求超时时间为 120 秒，以覆盖图片解析、音频转写和 RAG 精排。
- 前端会展示上传中的处理状态；失败时保留失败项和后端错误信息，删除失败时恢复原资料。

## 启动后端 API

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --reload --host 127.0.0.1 --port 8000
```

启动后可以访问 `http://127.0.0.1:8000/docs` 查看接口文档，或访问 `GET /api/health` 检查服务状态。

API 使用进程内会话存储，适合本地单进程演示：服务重启后会话会清空，不要配置多个 Uvicorn Worker。跨域来源默认允许 `localhost:5173` 和 `127.0.0.1:5173`，可以通过逗号分隔的 `COPILOT_CORS_ORIGINS` 环境变量覆盖。
