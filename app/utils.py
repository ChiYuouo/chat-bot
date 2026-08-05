"""通用文本处理工具。"""

import re


def extract_json(text: str) -> str:
    """从模型返回内容中提取第一个 JSON 对象。"""
    value = (text or "").strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    match = re.search(r"\{.*\}", value, flags=re.S)
    return match.group(0) if match else value

