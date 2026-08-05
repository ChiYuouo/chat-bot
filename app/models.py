"""跨模块使用的数据模型。"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


IntentName = Literal["rag_qa", "data_agent", "vision_extract", "general"]


class IntentSlots(BaseModel):
    query: Optional[str] = None
    file_path: Optional[str] = None
    image_path: Optional[str] = None


class IntentResult(BaseModel):
    intent: List[IntentName] = Field(default_factory=list)
    slots: IntentSlots = Field(default_factory=IntentSlots)
    confidence: float = Field(ge=0.0, le=1.0)

