"""Streamlit 会话状态初始化。"""

import streamlit as st


def init_session_state() -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = {
            "csv_name": None,
            "csv_df": None,
            "pdf_name": None,
            "pdf_chunks": None,
            "image_name": None,
            "image_path": None,
            "image_bytes": None,
        }


def clear_uploaded_files() -> None:
    st.session_state.uploaded_files = {
        "csv_name": None,
        "csv_df": None,
        "pdf_name": None,
        "pdf_chunks": None,
        "image_name": None,
        "image_path": None,
        "image_bytes": None,
    }

