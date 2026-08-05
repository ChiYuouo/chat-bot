"""用户意图识别。"""

import json

from app.llm import create_chat_model
from app.models import IntentResult
from app.prompts import INTENT_PROMPT
from app.utils import extract_json
from app.config import Config


def recognize_intent(user_input: str) -> IntentResult:
    llm = create_chat_model(Config.INTENT_MODEL, temperature=0)
    response = (INTENT_PROMPT | llm).invoke({"input": user_input})
    raw = json.loads(extract_json(response.content))
    return IntentResult.model_validate(raw)

