"""普通多轮对话能力。"""

from typing import Dict, List

from langchain_core.messages import AIMessage, HumanMessage

from app.config import Config
from app.llm import create_chat_model


def general_answer(question: str, chat_history: List[Dict]) -> str:
    llm = create_chat_model(Config.LLM_MODEL, temperature=0.7)
    messages = []
    for message in chat_history[-10:]:
        if message["role"] == "user":
            messages.append(HumanMessage(content=message["content"]))
        else:
            messages.append(AIMessage(content=message["content"]))
    messages.append(HumanMessage(content=question))

    response = llm.invoke(messages)
    return response.content if isinstance(response.content, str) else response.content[0].get("text", "")

