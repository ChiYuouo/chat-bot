"""统一创建 DashScope 聊天模型。"""

from langchain_community.chat_models import ChatTongyi


def create_chat_model(model: str, temperature: float = 0):
    """按原有参数创建一个 ChatTongyi 实例。"""
    return ChatTongyi(model=model, temperature=temperature)

