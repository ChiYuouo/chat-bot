"""应用配置。"""


class Config:
    """集中管理模型和检索参数，保持原有默认值。"""

    LLM_MODEL = "qwen-max"
    INTENT_MODEL = "qwen-turbo"
    VISION_MODEL = "qwen-vl-max"
    EMBEDDING_MODEL = "text-embedding-v2"
    REWRITE_MODEL = "qwen-turbo"
    RERANK_MODEL = "qwen-max"

    CONFIDENCE_THRESHOLD = 0.65
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 120
    RETRIEVAL_K = 15
    FUSION_K = 10
    FINAL_CONTEXT_K = 4

    ENABLE_QUERY_REWRITE = True
    ENABLE_LLM_RERANK = True
    REWRITE_HISTORY_MESSAGES = 4
    RERANK_CHUNK_MAX_CHARS = 1_200
    RERANK_RELEVANCE_THRESHOLD = 0.55

