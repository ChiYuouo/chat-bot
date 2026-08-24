"""知识库资料块的检索文本与来源信息辅助函数。"""

from typing import Any, Dict, Iterable, List

from langchain_core.documents import Document


_MODALITY_NAMES = {"pdf": "PDF", "text": "文本", "url": "网页"}
_RETRIEVAL_PREFIX_CHARS = "retrieval_prefix_chars"


def display_page(metadata: Dict[str, Any]) -> Any:
    if "display_page" in metadata:
        return metadata["display_page"]
    if "page" in metadata:
        page = metadata["page"]
        return page + 1 if isinstance(page, int) else page
    return metadata.get("page_number", "未知")


def source_location(metadata: Dict[str, Any]) -> str:
    source_name = metadata.get("source", "未知资料")
    modality = metadata.get("modality", "pdf")
    if modality == "pdf":
        return f"{source_name}，第 {display_page(metadata)} 页"
    if modality == "url":
        return f"{source_name}，网页资料"
    return f"{source_name}，文本资料"


def build_retrieval_documents(chunks: Iterable[Any]) -> List[Document]:
    documents = []
    for chunk in chunks:
        metadata = dict(chunk.metadata)
        source_name = metadata.get("source", "未知资料")
        modality_name = _MODALITY_NAMES.get(metadata.get("modality"), "资料")
        prefix = f"资料名称：{source_name}\n资料类型：{modality_name}\n"
        # 召回时加入来源信息；生成答案和引用时按长度移除前缀，保留原始正文。
        metadata[_RETRIEVAL_PREFIX_CHARS] = len(prefix)
        documents.append(
            Document(
                page_content=f"{prefix}{chunk.page_content}",
                metadata=metadata,
            )
        )
    return documents


def document_content(document: Any) -> str:
    prefix_chars = int(document.metadata.get(_RETRIEVAL_PREFIX_CHARS, 0))
    return document.page_content[prefix_chars:]
