"""图片识别能力。"""

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

