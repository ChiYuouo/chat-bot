"""跨模块使用的数据模型。"""

import time
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


IntentName = Literal["rag_qa", "data_agent", "vision_extract", "general"]
SourceModality = Literal["pdf", "text", "url", "image"]


class KnowledgeSource(BaseModel):
    source_id: str
    name: str
    modality: SourceModality
    chunk_count: int = Field(ge=1)
    url: Optional[str] = None
    content_hash: Optional[str] = None
    created_at: float = Field(default_factory=time.time)


class IntentSlots(BaseModel):
    query: Optional[str] = None
    file_path: Optional[str] = None
    image_path: Optional[str] = None


class IntentResult(BaseModel):
    intent: List[IntentName] = Field(default_factory=list)
    slots: IntentSlots = Field(default_factory=IntentSlots)
    confidence: float = Field(ge=0.0, le=1.0)

