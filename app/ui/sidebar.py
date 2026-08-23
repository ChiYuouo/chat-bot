"""侧边栏界面。"""

import os

import streamlit as st

from app.state import clear_uploaded_files, remove_pdf_source


def render_sidebar() -> None:
    with st.sidebar:
        st.header("⚙️ 配置")
        api_key = st.text_input(
            "DashScope API Key",
            type="password",
            value=os.getenv("DASHSCOPE_API_KEY", ""),
        )
        if api_key:
            os.environ["DASHSCOPE_API_KEY"] = api_key

        st.divider()
        st.header("📂 已上传文件")
        files = st.session_state.uploaded_files
        has_files = False
        if files.get("csv_df") is not None:
            st.success(f"📊 CSV: {files.get('csv_name', 'unknown')}")
            has_files = True
        for source in (files.get("pdf_sources") or {}).values():
            source_col, delete_col = st.columns([5, 1])
            with source_col:
                st.success(f"📚 {source.name} · {source.chunk_count} 块")
            with delete_col:
                if st.button("✕", key=f"delete_{source.source_id}", help="删除该资料"):
                    remove_pdf_source(files, source.source_id)
                    st.session_state.last_intents = []
                    st.rerun()
            has_files = True
        if files.get("image_path") is not None:
            st.success(f"🖼️ 图片: {files.get('image_name', 'unknown')}")
            has_files = True
        if not has_files:
            st.info("暂无文件，请在底部聊天区上传")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ 清空对话", use_container_width=True):
                st.session_state.messages = []
                st.session_state.last_intents = []
                st.rerun()
        with col2:
            if st.button("📛 清空文件", use_container_width=True):
                clear_uploaded_files()
                st.rerun()

