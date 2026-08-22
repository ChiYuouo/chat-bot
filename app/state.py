"""Streamlit 会话状态初始化。"""

import tempfile
from pathlib import Path

import streamlit as st


def _empty_uploaded_files():
    return {
        "csv_name": None,
        "csv_df": None,
        "pdf_name": None,
        "pdf_chunks": None,
        "pdf_store": None,
        "pdf_keyword_index": None,
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
    st.session_state.uploaded_files = _empty_uploaded_files()

