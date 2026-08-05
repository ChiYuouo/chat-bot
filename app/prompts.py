"""意图识别 Prompt。"""

from langchain_core.prompts import ChatPromptTemplate


INTENT_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        "你是企业智能助手的意图识别器。必须只输出严格 JSON，不要 Markdown 或解释。\n"
        "支持多意图，intent 只能取 rag_qa、data_agent、vision_extract、general。\n"
        "slots 至少包含 query、file_path、image_path，没有时填 '?'；confidence 是 0~1 的小数。\n"
        "提到数据分析、统计、图表、CSV、表格时使用 data_agent；提到图片、发票、截图、识别时使用 vision_extract；"
        "提到文档、PDF、手册、制度、知识库、文档查询时使用 rag_qa；其他情况使用 general。",
    ),
    (
        "human",
        "用户输入：用条形图展示各类别的数量分布\n只输出 JSON："
        '{{"intent":["data_agent"],"slots":{{"query":"用条形图展示各类别的数量分布",'
        '"file_path":"?","image_path":"?"}},"confidence":0.86}}',
    ),
    (
        "human",
        "用户输入：这张发票截图里金额是多少？\n只输出 JSON："
        '{{"intent":["vision_extract"],"slots":{{"query":"金额是多少",'
        '"file_path":"?","image_path":"?"}},"confidence":0.82}}',
    ),
    (
        "human",
        "用户输入：员工手册里病假最多几天？\n只输出 JSON："
        '{{"intent":["rag_qa"],"slots":{{"query":"病假最多几天",'
        '"file_path":"?","image_path":"?"}},"confidence":0.88}}',
    ),
    ("human", "用户输入：{input}\n只输出 JSON："),
])

