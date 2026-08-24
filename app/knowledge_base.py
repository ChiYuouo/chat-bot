"""会话知识库的资料与索引生命周期。"""

import uuid
from typing import Any, Dict, Iterable

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma

from app.config import Config
from app.models import KnowledgeSource
from app.rag import BM25Index
from app.source_utils import build_retrieval_documents


def _build_vector_store(chunks: list[Any]) -> Chroma:
    embeddings = DashScopeEmbeddings(model=Config.EMBEDDING_MODEL)
    return Chroma.from_documents(
        chunks,
        embeddings,
        ids=[chunk.metadata["chunk_id"] for chunk in chunks],
        collection_name=f"knowledge-{uuid.uuid4().hex}",
    )


def _build_keyword_index(chunks: list[Any]) -> BM25Index:
    return BM25Index(chunks)


def discard_indexes(files: Dict[str, Any]) -> None:
    store = files.get("knowledge_store")
    if store is not None:
        # 热重载或异常后 collection 可能已经释放，不能影响资料状态更新。
        try:
            store.delete_collection()
        except Exception:
            pass
    files["knowledge_store"] = None
    files["knowledge_keyword_index"] = None


def add_source(
    files: Dict[str, Any],
    source: KnowledgeSource,
    chunks: Iterable[Any],
) -> None:
    files.setdefault("knowledge_sources", {})[source.source_id] = source
    files["knowledge_chunks"] = [*(files.get("knowledge_chunks") or []), *chunks]
    discard_indexes(files)


def remove_source(files: Dict[str, Any], source_id: str) -> bool:
    sources = files.get("knowledge_sources") or {}
    if source_id not in sources:
        return False

    del sources[source_id]
    files["knowledge_sources"] = sources
    files["knowledge_chunks"] = [
        chunk
        for chunk in files.get("knowledge_chunks") or []
        if chunk.metadata.get("source_id") != source_id
    ]
    discard_indexes(files)
    return True


def ensure_indexes(files: Dict[str, Any]) -> tuple[Any, Any]:
    chunks = files.get("knowledge_chunks") or []
    if not chunks:
        raise ValueError("知识库中没有可检索资料")

    index_documents = None
    if files.get("knowledge_store") is None:
        index_documents = build_retrieval_documents(chunks)
        files["knowledge_store"] = _build_vector_store(index_documents)
    if files.get("knowledge_keyword_index") is None:
        index_documents = index_documents or build_retrieval_documents(chunks)
        files["knowledge_keyword_index"] = _build_keyword_index(index_documents)
    return files["knowledge_store"], files["knowledge_keyword_index"]
