"""把依赖上下文的追问改写成可独立检索的问题。"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Tuple

from app.config import Config
from app.llm import create_chat_model
from app.utils import extract_json


def rewrite_query(
    question: str,
    chat_history: List[Dict[str, Any]],
) -> Tuple[str, Dict[str, Any]]:
    """有历史时执行一次改写；任何异常都安全退回原问题。"""
    if not Config.ENABLE_QUERY_REWRITE or not chat_history:
        return question, {"applied": False, "reason": "没有历史对话或功能未开启"}

    history_lines = []
    # 只取最近几轮并限制单条长度，避免完整回答反复进入 Rewrite Prompt。
    for message in chat_history[-Config.REWRITE_HISTORY_MESSAGES:]:
        role = "用户" if message.get("role") == "user" else "助手"
        content = str(message.get("content", ""))[:600]
        history_lines.append(f"{role}：{content}")

    prompt = f"""你是检索问题改写器。结合对话历史，将当前问题改写为不依赖上下文、可以独立检索的问题。

对话历史：
{chr(10).join(history_lines)}

当前问题：{question}

要求：
1. 不增加对话中不存在的事实。
2. 如果当前问题已经独立完整，保持原意，不要扩写。
3. 只输出严格 JSON：{{"standalone_query":"改写后的问题"}}
"""
    try:
        response = create_chat_model(Config.REWRITE_MODEL, temperature=0).invoke(prompt)
        raw = response.content if isinstance(response.content, str) else response.content[0]["text"]
        standalone_query = str(json.loads(extract_json(raw))["standalone_query"]).strip()
        if not standalone_query:
            raise ValueError("改写结果为空")
        return standalone_query, {
            "applied": standalone_query != question,
            "reason": None,
        }
    except Exception as exc:
        return question, {
            "applied": False,
            "reason": f"Rewrite 失败，已使用原问题：{exc}",
        }
