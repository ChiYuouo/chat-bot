"""聊天区和文件上传界面。"""
import os
import tempfile

import pandas as pd
import streamlit as st

from app.capabilities.rag import process_pdf
from app.router import process_user_message
from app.state import clear_uploaded_files, init_session_state, remove_uploaded_image_temp_file
from app.ui.sidebar import render_sidebar


def render_chat_input_area():
    for key in ["csv", "pdf", "img"]:
        if f"show_{key}" not in st.session_state:
            st.session_state[f"show_{key}"] = False

    uploaded = st.session_state.uploaded_files
    uploaded_names = []
    if uploaded.get("csv_df") is not None:
        uploaded_names.append("📊CSV")
    if uploaded.get("pdf_chunks") is not None:
        uploaded_names.append("📚PDF")
    if uploaded.get("image_path") is not None:
        uploaded_names.append("🖼️图片")
    if uploaded_names:
        st.caption(f"已上传: {' | '.join(uploaded_names)}")

    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("📄 CSV", use_container_width=True, type="secondary"):
                st.session_state.show_csv = not st.session_state.get("show_csv", False)
                st.session_state.show_pdf = False
                st.session_state.show_img = False
                st.rerun()
        with c2:
            if st.button("📚 PDF", use_container_width=True, type="secondary"):
                st.session_state.show_pdf = not st.session_state.get("show_pdf", False)
                st.session_state.show_csv = False
                st.session_state.show_img = False
                st.rerun()
        with c3:
            if st.button("🖼️ 图片", use_container_width=True, type="secondary"):
                st.session_state.show_img = not st.session_state.get("show_img", False)
                st.session_state.show_csv = False
                st.session_state.show_pdf = False
                st.rerun()
        with c4:
            if st.button("🗑️ 清空", use_container_width=True, type="secondary"):
                clear_uploaded_files()
                st.session_state.show_csv = False
                st.session_state.show_pdf = False
                st.session_state.show_img = False
                st.rerun()

        if st.session_state.get("show_csv"):
            file = st.file_uploader("选择 CSV 文件", type=["csv"], key="up_csv")
            if file:
                st.session_state.uploaded_files["csv_df"] = pd.read_csv(file)
                st.session_state.uploaded_files["csv_name"] = file.name
                st.session_state.show_csv = False
                st.rerun()

        if st.session_state.get("show_pdf"):
            file = st.file_uploader("选择 PDF 文件", type=["pdf"], key="up_pdf")
            if file:
                # 先解析新 PDF，解析失败时仍然保留旧 PDF。
                new_chunks = process_pdf(
                    file.read(),
                    source_name=file.name,
                )

                # 删除旧 PDF 对应的 Chroma Collection。
                old_store = st.session_state.uploaded_files.get("pdf_store")
                if old_store is not None:
                    old_store.delete_collection()

                # 替换为新 PDF，下一次提问时重新构建索引。
                st.session_state.uploaded_files["pdf_chunks"] = new_chunks
                st.session_state.uploaded_files["pdf_store"] = None
                st.session_state.uploaded_files["pdf_keyword_index"] = None
                # Query Rewrite 只使用当前 PDF 的问答历史，切换文件时不能沿用旧文档上下文。
                st.session_state.uploaded_files["pdf_chat_history"] = []
                st.session_state.uploaded_files["pdf_name"] = file.name
                st.session_state.last_intents = []
                st.session_state.show_pdf = False
                st.rerun()

        if st.session_state.get("show_img"):
            file = st.file_uploader("选择图片", type=["png", "jpg", "jpeg"], key="up_img")
            if file:
                image_bytes = file.read()
                remove_uploaded_image_temp_file()
                suffix = "." + file.name.rsplit(".", 1)[-1].lower()
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(image_bytes)
                    st.session_state.uploaded_files["image_path"] = tmp.name
                st.session_state.uploaded_files["image_name"] = file.name
                st.session_state.uploaded_files["image_bytes"] = image_bytes
                st.session_state.show_img = False
                st.rerun()

    return st.chat_input("发送消息...")


def main() -> None:
    st.set_page_config(page_title="Enterprise AI Copilot", page_icon="🤖", layout="wide")
    init_session_state()
    render_sidebar()

    st.title("🤖 Enterprise AI Copilot")
    st.caption("智能对话助手 | 支持 RAG 问答 · 数据分析 · 图片识别 · 多轮对话")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("chart"):
                st.image(message["chart"])
            if message.get("rag_debug"):
                with st.expander("查看 RAG 检索过程"):
                    st.json(message["rag_debug"])

    prompt = render_chat_input_area()
    if prompt:
        if not os.getenv("DASHSCOPE_API_KEY"):
            st.error("⚠️ 请先在侧边栏输入 DashScope API Key")
            st.stop()

        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            result = process_user_message(prompt)
            response = result["content"]
            chart = result["chart"]
            rag_debug = result.get("rag_debug")
            st.markdown(response)
            if chart:
                st.image(chart)
            if rag_debug:
                with st.expander("查看 RAG 检索过程"):
                    st.json(rag_debug)

        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
        })

        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "chart": chart,
            "rag_debug": rag_debug,
        })

