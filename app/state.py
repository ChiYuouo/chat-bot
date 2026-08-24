"""Streamlit 会话状态初始化。"""

import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable

import streamlit as st

from app.models import KnowledgeSource


def _empty_uploaded_files():
    return {
        "csv_name": None,
        "csv_df": None,
        "knowledge_sources": {},
        "knowledge_chunks": [],
        "knowledge_store": None,
        "knowledge_keyword_index": None,
        "image_name": None,
        "image_path": None,
        "image_bytes": None,
    }


def _discard_knowledge_indexes(files: Dict[str, Any]) -> None:
    store = files.get("knowledge_store")
    if store is not None:
        # 索引可以在异常或热重载后已被释放，清理失败不应阻止资料状态更新。
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
    _discard_knowledge_indexes(files)


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
    _discard_knowledge_indexes(files)
    return True


def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "last_intents" not in st.session_state:
        st.session_state.last_intents = []
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = _empty_uploaded_files()
    else:
        for key, value in _empty_uploaded_files().items():
            st.session_state.uploaded_files.setdefault(key, value)
        if st.session_state.uploaded_files.get("knowledge_chunks") is None:
            st.session_state.uploaded_files["knowledge_chunks"] = []


def remove_uploaded_image_temp_file() -> None:
    """只删除由应用创建在系统临时目录中的图片文件。"""
    image_path = st.session_state.uploaded_files.get("image_path")
    if not image_path:
        return

    target = Path(image_path).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if target.is_file() and target.is_relative_to(temp_root):
        target.unlink()


def clear_uploaded_files() -> None:
    remove_uploaded_image_temp_file()
    _discard_knowledge_indexes(st.session_state.uploaded_files)
    st.session_state.uploaded_files = _empty_uploaded_files()

