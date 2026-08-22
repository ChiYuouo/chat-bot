# Enterprise AI Copilot

一个基于 **Streamlit、LangChain 与通义千问** 的企业智能助手示例。系统会识别用户意图，并自动调用文档问答、数据分析、图片识别或通用对话能力。

## 功能特性

- **智能意图路由**：识别单个或多个任务，并分发到对应能力模块
- **RAG 2.0 问答**：问题改写、向量与 BM25 混合召回、RRF 混排、LLM 精排，并标注引用页码
- **CSV 数据分析**：根据自然语言生成 Pandas 代码、统计结果与图表
- **图片内容识别**：理解图片并返回结构化信息
- **多轮通用对话**：保留最近的会话上下文，支持连续提问

## 项目架构

```mermaid
flowchart LR
    U[用户] --> UI[Streamlit 对话界面]
    UI --> I[意图识别<br/>Qwen Turbo]
    I --> R{能力路由}
    R --> G[通用对话<br/>Qwen Max]
    R --> D[PDF RAG 2.0<br/>Rewrite + Hybrid Search + Rerank]
    R --> A[CSV 数据分析<br/>Pandas + Matplotlib]
    R --> V[图片识别<br/>Qwen VL Max]
    G & D & A & V --> UI
```

## 快速开始

准备 Python 3.10+ 和 [DashScope API Key](https://help.aliyun.com/zh/model-studio/get-api-key)。

```bash
git clone https://github.com/ChiYuouo/chat-bot.git
cd chat-bot

python -m venv .venv
```

激活虚拟环境并安装依赖：

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

python -m pip install -r requirements.txt
```

启动应用：

```bash
streamlit run chatbot.py
```

浏览器打开 `http://localhost:8501`，在左侧边栏填写 API Key，即可开始对话或上传 PDF、CSV、图片文件。

## 使用示例

| 场景 | 示例问题 |
| --- | --- |
| 文档问答 | `员工手册中规定的年假有多少天？` |
| 数据分析 | `统计各类别数量，并生成条形图。` |
| 图片识别 | `提取这张发票中的金额和日期。` |
| 普通对话 | `帮我写一封简短的会议邀请邮件。` |

## 目录结构

```text
chatbot.py              # 应用入口
app/
├── capabilities/       # RAG、数据分析、视觉与通用对话能力
├── ui/                 # Streamlit 页面与侧边栏
├── intent.py           # 意图识别
├── router.py           # 能力路由
├── config.py           # 模型与检索配置
└── state.py            # 会话状态管理
```

## 技术栈

`Python` · `Streamlit` · `LangChain` · `DashScope` · `ChromaDB` · `Pandas` · `Matplotlib`

## RAG 2.0 检索链路

```text
用户问题
  → 结合历史对话 Rewrite
  → 向量 Top 15 + 中文 BM25 Top 15
  → RRF 混排 Top 10
  → Qwen Listwise 精排
  → Top 4 生成答案并标注页码
```

聊天界面的“查看 RAG 检索过程”会展示改写结果、两路召回、混排、精排和各阶段耗时。Rewrite、精排失败时都会自动降级，不会中断问答。

### RRF 混排

[`app/rag/retrieval.py`](app/rag/retrieval.py) 中的 `reciprocal_rank_fusion` 会累加同一个 chunk 在多路召回中的倒数排名分数：

实现公式：

```text
score(document) = Σ 1 / (rrf_k + rank_i)
```

对应单元测试位于 [`tests/test_rag_retrieval.py`](tests/test_rag_retrieval.py)。

> [!WARNING]
> CSV 分析模块会在受限子进程中执行大模型生成的 Python 代码，并进行语法检查与超时控制；这仍不能替代生产环境的容器沙箱、网络隔离与操作系统级资源限制。

## 运行测试

项目测试不依赖真实 API Key：

```bash
python -m unittest discover -s tests -v
```
