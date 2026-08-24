"""图片识别和图片知识提取能力。"""

import json
import os
from typing import Any, Dict

from langchain_core.messages import HumanMessage

from app.config import Config
from app.llm import create_chat_model
from app.utils import extract_json


def vision_answer(image_path: str, question: str) -> Dict[str, Any]:
    if not image_path.startswith("file://"):
        image_path = f"file://{os.path.abspath(image_path)}"

    prompt = (
        f"你是识图助手，请根据图片内容回答：{question}\n"
        '请严格输出 JSON：{{"summary":"图片内容概述","entities":["识别出的实体"],'
        '"answer":"针对问题的答案"}}'
    )
    message = HumanMessage(content=[{"text": prompt}, {"image": image_path}])
    response = create_chat_model(Config.VISION_MODEL, temperature=0).invoke([message])
    text = response.content[0]["text"] if isinstance(response.content, list) else response.content

    try:
        obj = json.loads(extract_json(text))
        return {"answer": obj.get("answer", obj.get("summary", "")), "contract": obj}
    except json.JSONDecodeError:
        return {"answer": text, "contract": {"raw": text}}


def extract_image_content(image_path: str) -> Dict[str, Any]:
    """将图片转换为适合知识库检索的、与具体问题无关的文本。"""
    if not image_path.startswith("file://"):
        image_path = f"file://{os.path.abspath(image_path)}"

    prompt = """你是图片资料提取器。请完整提取图片中可用于知识库检索的信息。

要求：
1. ocr_text：按原有阅读顺序提取图片中的文字；没有文字时返回空字符串。
2. description：客观描述图片表达的事实、布局和重要关系，不要推测看不清的内容。
3. entities：列出清晰可见的重要人物、物体、地点、产品或组织名称。
4. 只输出严格 JSON：
{"ocr_text":"图片文字","description":"图片描述","entities":["实体"]}
"""
    message = HumanMessage(content=[{"text": prompt}, {"image": image_path}])
    response = create_chat_model(Config.VISION_MODEL, temperature=0).invoke([message])
    raw = (
        response.content[0]["text"]
        if isinstance(response.content, list)
        else response.content
    )

    try:
        obj = json.loads(extract_json(raw))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("图片内容提取结果不是有效 JSON") from exc
    if not isinstance(obj, dict):
        raise ValueError("图片内容提取结果格式无效")

    ocr_text = str(obj.get("ocr_text") or "").strip()
    description = str(obj.get("description") or "").strip()
    raw_entities = obj.get("entities") or []
    entities = (
        [str(value).strip() for value in raw_entities if str(value).strip()]
        if isinstance(raw_entities, list)
        else []
    )

    parts = []
    if description:
        parts.append(f"图片描述\n{description}")
    if ocr_text:
        parts.append(f"图片文字\n{ocr_text}")
    if entities:
        parts.append(f"图片实体\n{'、'.join(entities)}")
    if not parts:
        raise ValueError("图片中未提取到可检索内容")

    return {
        "text": "\n\n".join(parts),
        "contract": {
            "ocr_text": ocr_text,
            "description": description,
            "entities": entities,
        },
    }

