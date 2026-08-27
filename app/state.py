"""Streamlit 会话状态初始化。"""

import tempfile
from pathlib import Path

import streamlit as st

from app.knowledge_base import discard_indexes


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


def remove_uploaded_image_temp_file(uploaded_files=None) -> None:
    """只删除由应用创建在系统临时目录中的图片文件。"""
    files = uploaded_files if uploaded_files is not None else st.session_state.uploaded_files
    image_path = files.get("image_path")
    if not image_path:
        return

    target = Path(image_path).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if target.is_file() and target.is_relative_to(temp_root):
        target.unlink()


def clear_uploaded_files(uploaded_files=None) -> None:
    """清空 Streamlit 或显式传入会话中的全部资料。"""
    files = uploaded_files if uploaded_files is not None else st.session_state.uploaded_files
    remove_uploaded_image_temp_file(files)
    discard_indexes(files)
    files.clear()
    files.update(_empty_uploaded_files())

