"""聊天区和文件上传界面。"""
import os
import tempfile

import pandas as pd
import streamlit as st

from app.ingestion import ingest_audio, ingest_image, ingest_pdf, ingest_text, ingest_url
from app.knowledge_base import add_source
from app.router import process_user_message
from app.state import (
    clear_uploaded_files,
    init_session_state,
    remove_uploaded_image_temp_file,
)
from app.ui.sidebar import render_sidebar


_INPUT_PANELS = ("pdf", "text", "url", "image_source", "audio", "csv", "img")


def _toggle_input_panel(selected: str) -> None:
    should_open = not st.session_state.get(f"show_{selected}", False)
    for panel in _INPUT_PANELS:
        st.session_state[f"show_{panel}"] = panel == selected and should_open
    st.rerun()


def render_chat_input_area():
    for key in _INPUT_PANELS:
        if f"show_{key}" not in st.session_state:
            st.session_state[f"show_{key}"] = False

    uploaded = st.session_state.uploaded_files
    uploaded_names = []
    if uploaded.get("csv_df") is not None:
        uploaded_names.append("📊CSV")
    source_count = len(uploaded.get("knowledge_sources") or {})
    if source_count:
        uploaded_names.append(f"📚资料 × {source_count}")
    if uploaded.get("image_path") is not None:
        uploaded_names.append("👁️临时识图")
    if uploaded_names:
        st.caption(f"当前资料: {' | '.join(uploaded_names)}")

    with st.container(border=True):
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
        with c1:
            if st.button("📚 PDF", use_container_width=True, type="secondary"):
                _toggle_input_panel("pdf")
        with c2:
            if st.button("📝 文本", use_container_width=True, type="secondary"):
                _toggle_input_panel("text")
        with c3:
            if st.button("🔗 网页", use_container_width=True, type="secondary"):
                _toggle_input_panel("url")
        with c4:
            if st.button("🖼️ 图片资料", use_container_width=True, type="secondary"):
                _toggle_input_panel("image_source")
        with c5:
            if st.button("🎧 音频资料", use_container_width=True, type="secondary"):
                _toggle_input_panel("audio")
        with c6:
            if st.button("📄 CSV", use_container_width=True, type="secondary"):
                _toggle_input_panel("csv")
        with c7:
            if st.button("👁️ 临时识图", use_container_width=True, type="secondary"):
                _toggle_input_panel("img")
        with c8:
            if st.button("🗑️ 清空", use_container_width=True, type="secondary"):
                clear_uploaded_files()
                for panel in _INPUT_PANELS:
                    st.session_state[f"show_{panel}"] = False
                st.rerun()

        if st.session_state.get("show_csv"):
            file = st.file_uploader("选择 CSV 文件", type=["csv"], key="up_csv")
            if file:
                st.session_state.uploaded_files["csv_df"] = pd.read_csv(file)
                st.session_state.uploaded_files["csv_name"] = file.name
                st.session_state.show_csv = False
                st.rerun()

        if st.session_state.get("show_pdf"):
            revision = st.session_state.setdefault("pdf_upload_revision", 0)
            file = st.file_uploader(
                "选择 PDF 文件",
                type=["pdf"],
                key=f"up_pdf_{revision}",
            )
            if file:
                try:
                    source, chunks = ingest_pdf(file.read(), source_name=file.name)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    add_source(st.session_state.uploaded_files, source, chunks)
                    st.session_state.pdf_upload_revision += 1
                    st.session_state.show_pdf = False
                    st.rerun()

        if st.session_state.get("show_text"):
            with st.form("add_text_source"):
                title = st.text_input("资料标题", max_chars=160)
                text = st.text_area("资料正文", height=180)
                submitted = st.form_submit_button("添加文本资料")
            if submitted:
                try:
                    source, chunks = ingest_text(title, text)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    add_source(st.session_state.uploaded_files, source, chunks)
                    st.session_state.show_text = False
                    st.rerun()

        if st.session_state.get("show_url"):
            with st.form("add_url_source"):
                title = st.text_input("资料标题（可选）", max_chars=160)
                url = st.text_input("网页 URL", placeholder="https://example.com/article")
                submitted = st.form_submit_button("抓取并添加")
            if submitted:
                try:
                    with st.spinner("正在抓取并解析网页..."):
                        source, chunks = ingest_url(url, title)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    add_source(st.session_state.uploaded_files, source, chunks)
                    st.session_state.show_url = False
                    st.rerun()

        if st.session_state.get("show_image_source"):
            revision = st.session_state.setdefault("image_source_upload_revision", 0)
            file = st.file_uploader(
                "选择要加入知识库的图片",
                type=["png", "jpg", "jpeg"],
                key=f"up_image_source_{revision}",
            )
            if file:
                image_bytes = file.read()
                existing_hashes = {
                    source_hash
                    for source in (
                        st.session_state.uploaded_files.get("knowledge_sources") or {}
                    ).values()
                    if (source_hash := getattr(source, "content_hash", None))
                }
                try:
                    with st.spinner("正在提取图片内容并加入知识库..."):
                        source, chunks = ingest_image(
                            image_bytes,
                            source_name=file.name,
                            existing_content_hashes=existing_hashes,
                        )
                except Exception as exc:
                    st.error(str(exc))
                else:
                    add_source(st.session_state.uploaded_files, source, chunks)
                    st.session_state.image_source_upload_revision += 1
                    st.session_state.show_image_source = False
                    st.rerun()

        if st.session_state.get("show_audio"):
            revision = st.session_state.setdefault("audio_upload_revision", 0)
            file = st.file_uploader(
                "选择要加入知识库的音频",
                type=["mp3", "wav", "m4a"],
                key=f"up_audio_{revision}",
            )
            if file:
                audio_bytes = file.read()
                existing_hashes = {
                    source_hash
                    for source in (
                        st.session_state.uploaded_files.get("knowledge_sources") or {}
                    ).values()
                    if (source_hash := getattr(source, "content_hash", None))
                }
                try:
                    with st.spinner("正在转写音频并加入知识库..."):
                        source, chunks = ingest_audio(
                            audio_bytes,
                            source_name=file.name,
                            existing_content_hashes=existing_hashes,
                        )
                except Exception as exc:
                    st.error(str(exc))
                else:
                    add_source(st.session_state.uploaded_files, source, chunks)
                    st.session_state.audio_upload_revision += 1
                    st.session_state.show_audio = False
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

