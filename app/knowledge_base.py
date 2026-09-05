"""会话知识库的资料、持久化与索引生命周期。"""

import hashlib
import uuid
from typing import Any, Dict, Iterable

from langchain_community.embeddings import DashScopeEmbeddings
from langchain_community.vectorstores import Chroma

from app.config import Config
from app.models import KnowledgeSource
from app.rag import BM25Index
from app.repositories.knowledge import SQLiteKnowledgeRepository
from app.source_utils import build_retrieval_documents


_repository = SQLiteKnowledgeRepository()


def _scope_id(files: Dict[str, Any]) -> str | None:
    scope_id = files.get("knowledge_scope_id")
    return scope_id if isinstance(scope_id, str) and scope_id else None


def _collection_name(files: Dict[str, Any]) -> str:
    scope_id = _scope_id(files)
    if scope_id is None:
        return f"knowledge-{uuid.uuid4().hex}"
    return _collection_name_for_scope(scope_id)


def _collection_name_for_scope(scope_id: str) -> str:
    digest = hashlib.sha256(scope_id.encode("utf-8")).hexdigest()[:24]
    return f"knowledge-{digest}"


def _build_vector_store(chunks: list[Any], collection_name: str | None = None) -> Chroma:
    embeddings = DashScopeEmbeddings(model=Config.EMBEDDING_MODEL)
    store = Chroma(
        collection_name=collection_name or f"knowledge-{uuid.uuid4().hex}",
        embedding_function=embeddings,
        persist_directory=Config.CHROMA_PERSIST_DIRECTORY,
    )
    chunk_ids = [str(chunk.metadata["chunk_id"]) for chunk in chunks]
    existing_ids = set(store.get(ids=chunk_ids, include=[]).get("ids", []))
    pending = [
        chunk for chunk in chunks
        if str(chunk.metadata["chunk_id"]) not in existing_ids
    ]
    if pending:
        store.add_documents(
            pending,
            ids=[str(chunk.metadata["chunk_id"]) for chunk in pending],
        )
    return store


def _build_keyword_index(chunks: list[Any]) -> BM25Index:
    return BM25Index(chunks)


def discard_indexes(files: Dict[str, Any]) -> None:
    store = files.get("knowledge_store")
    if store is not None and _scope_id(files) is None:
        # 热重载或异常后 collection 可能已经释放，不能影响资料状态更新。
        try:
            store.delete_collection()
        except Exception:
            pass
    files["knowledge_store"] = None
    files["knowledge_keyword_index"] = None


def restore_persisted_knowledge(files: Dict[str, Any], scope_id: str) -> None:
    """从 SQLite 恢复资料和 Chunk；向量索引在首次检索时按需打开。"""
    files["knowledge_scope_id"] = scope_id
    files["knowledge_sources"] = _repository.load_sources(scope_id)
    files["knowledge_chunks"] = _repository.load_chunks(scope_id)
    files["knowledge_store"] = None
    files["knowledge_keyword_index"] = None


def discard_persisted_vector_index(scope_id: str) -> None:
    """删除旧 scope 的索引；SQLite 中的 Chunk 会在下次检索时重建索引。"""
    try:
        Chroma(
            collection_name=_collection_name_for_scope(scope_id),
            persist_directory=Config.CHROMA_PERSIST_DIRECTORY,
        ).delete_collection()
    except Exception:
        # 索引还未创建或已被清理时，不影响账号绑定流程。
        pass


def _delete_vector_chunks(files: Dict[str, Any], chunk_ids: list[str]) -> None:
    if not chunk_ids or _scope_id(files) is None:
        return
    store = files.get("knowledge_store")
    if store is None:
        store = Chroma(
            collection_name=_collection_name(files),
            persist_directory=Config.CHROMA_PERSIST_DIRECTORY,
        )
    store.delete(ids=chunk_ids)


def clear_knowledge(files: Dict[str, Any]) -> None:
    """清除当前 scope 的 SQLite 数据及其持久化向量索引。"""
    scope_id = _scope_id(files)
    if scope_id is not None:
        store = files.get("knowledge_store")
        if store is None:
            store = Chroma(
                collection_name=_collection_name(files),
                persist_directory=Config.CHROMA_PERSIST_DIRECTORY,
            )
        try:
            store.delete_collection()
        except Exception:
            # Collection 尚未创建时无需阻止 SQLite 数据清理。
            pass
        _repository.clear_scope(scope_id)
    discard_indexes(files)
    files["knowledge_sources"] = {}
    files["knowledge_chunks"] = []


def add_source(
    files: Dict[str, Any],
    source: KnowledgeSource,
    chunks: Iterable[Any],
) -> None:
    documents = list(chunks)
    scope_id = _scope_id(files)
    if scope_id is not None:
        documents = _repository.save_source(scope_id, source, documents)
    files.setdefault("knowledge_sources", {})[source.source_id] = source
    files["knowledge_chunks"] = [*(files.get("knowledge_chunks") or []), *documents]
    discard_indexes(files)


def remove_source(files: Dict[str, Any], source_id: str) -> bool:
    sources = files.get("knowledge_sources") or {}
    if source_id not in sources:
        return False

    removed_chunk_ids = [
        str(chunk.metadata["chunk_id"])
        for chunk in files.get("knowledge_chunks") or []
        if chunk.metadata.get("source_id") == source_id
    ]
    _delete_vector_chunks(files, removed_chunk_ids)
    scope_id = _scope_id(files)
    if scope_id is not None:
        if not _repository.delete_source(scope_id, source_id):
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
        files["knowledge_store"] = _build_vector_store(
            index_documents, _collection_name(files)
        )
    if files.get("knowledge_keyword_index") is None:
        index_documents = index_documents or build_retrieval_documents(chunks)
        files["knowledge_keyword_index"] = _build_keyword_index(index_documents)
    return files["knowledge_store"], files["knowledge_keyword_index"]
