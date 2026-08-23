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
        "pdf_sources": {},
        "pdf_chunks": [],
        "pdf_store": None,
        "pdf_keyword_index": None,
        "pdf_chat_history": [],
        "image_name": None,
        "image_path": None,
        "image_bytes": None,
    }


def _discard_pdf_indexes(files: Dict[str, Any]) -> None:
    store = files.get("pdf_store")
    if store is not None:
        # 索引可以在异常或热重载后已被释放，清理失败不应阻止资料状态更新。
        try:
            store.delete_collection()
        except Exception:
            pass
    files["pdf_store"] = None
    files["pdf_keyword_index"] = None


def add_pdf_source(
    files: Dict[str, Any],
    source: KnowledgeSource,
    chunks: Iterable[Any],
) -> None:
    files.setdefault("pdf_sources", {})[source.source_id] = source
    files["pdf_chunks"] = [*(files.get("pdf_chunks") or []), *chunks]
    files["pdf_chat_history"] = []
    _discard_pdf_indexes(files)


def remove_pdf_source(files: Dict[str, Any], source_id: str) -> bool:
    sources = files.get("pdf_sources") or {}
    if source_id not in sources:
        return False

    del sources[source_id]
    files["pdf_sources"] = sources
    files["pdf_chunks"] = [
        chunk
        for chunk in files.get("pdf_chunks") or []
        if chunk.metadata.get("source_id") != source_id
    ]
    files["pdf_chat_history"] = []
    _discard_pdf_indexes(files)
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
        if st.session_state.uploaded_files.get("pdf_chunks") is None:
            st.session_state.uploaded_files["pdf_chunks"] = []


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
    _discard_pdf_indexes(st.session_state.uploaded_files)
    st.session_state.uploaded_files = _empty_uploaded_files()

