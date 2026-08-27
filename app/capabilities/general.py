"""普通多轮对话能力。"""

from collections.abc import Callable
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage

from app.config import Config
from app.llm import create_chat_model


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            item if isinstance(item, str) else str(item.get("text", ""))
            for item in content
            if isinstance(item, (str, dict))
        )
    return str(content or "")


def general_answer(
    question: str,
    chat_history: List[Dict],
    stream_callback: Callable[[str], None] | None = None,
) -> str:
    llm = create_chat_model(Config.LLM_MODEL, temperature=0.7)
    messages = []
    for message in chat_history[-10:]:
        if message["role"] == "user":
            messages.append(HumanMessage(content=message["content"]))
        else:
            messages.append(AIMessage(content=message["content"]))
    messages.append(HumanMessage(content=question))

    if stream_callback is None:
        return _content_to_text(llm.invoke(messages).content)

    answer_parts: list[str] = []
    for chunk in llm.stream(messages):
        text = _content_to_text(chunk.content)
        if not text:
            continue
        answer_parts.append(text)
        stream_callback(text)
    return "".join(answer_parts)

