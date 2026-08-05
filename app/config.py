"""应用配置。"""


class Config:
    """集中管理模型和检索参数，保持原有默认值。"""

    LLM_MODEL = "qwen-max"
    INTENT_MODEL = "qwen-turbo"
    VISION_MODEL = "qwen-vl-max"
    EMBEDDING_MODEL = "text-embedding-v2"

    CONFIDENCE_THRESHOLD = 0.65
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 120
    RETRIEVAL_K = 4

