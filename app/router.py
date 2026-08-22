"""意图到能力模块的路由。"""

import json
from typing import Any, Dict

import streamlit as st

from app.capabilities.data_agent import agent_answer
from app.capabilities.general import general_answer
from app.capabilities.rag import build_vector_store, rag_answer
from app.capabilities.vision import vision_answer
from app.config import Config
from app.intent import recognize_intent


def get_intent_badge(intent: str) -> str:
    badges = {
        "rag_qa": "📚 RAG",
        "data_agent": "📊 数据分析",
        "vision_extract": "🖼️ Vision",
        "general": "💬 普通问答",
    }
    return badges.get(intent, intent)


def process_user_message(user_input: str) -> Dict[str, Any]:
    files = st.session_state.uploaded_files
    chart = None

    try:
        intent_result = recognize_intent(user_input)
    except Exception as exc:
        with st.spinner("意图识别失败，正在使用普通问答..."):
            answer = general_answer(user_input, st.session_state.messages)
        return {
            "content": f"⚠️ **意图识别已降级**: {exc}\n\n💬 **回答**:\n{answer}",
            "chart": None,
        }

    intents = intent_result.intent
    fallback_reason = None
    if not intents:
        intents = ["general"]
        fallback_reason = "未识别到有效意图"
    elif intent_result.confidence < Config.CONFIDENCE_THRESHOLD:
        intents = ["general"]
        fallback_reason = f"意图置信度较低（{intent_result.confidence:.0%}）"

    intent_str = ", ".join(get_intent_badge(intent) for intent in intents)
    confidence_str = f"{intent_result.confidence:.0%}"
    response_parts = [f"🎆 **意图识别**: {intent_str} (置信度: {confidence_str})\n"]
    if fallback_reason:
        response_parts.append(f"⚠️ {fallback_reason}，已自动降级为普通问答。\n")

    for intent in intents:
        try:
            if intent == "rag_qa":
                if files["pdf_chunks"] is None:
                    response_parts.append("⚠️ **RAG 问答**需要先上传 PDF 文件（在左侧边栏上传）\n")
                else:
                    if files.get("pdf_store") is None:
                        with st.spinner("首次构建文档向量库..."):
                            files["pdf_store"] = build_vector_store(files["pdf_chunks"])
                    with st.spinner("正在检索文档并生成答案..."):
                        result = rag_answer(user_input, files["pdf_store"])
                    response_parts.append(f"📚 **RAG 回答**:\n{result['answer']}\n")
                    if result["citations"]:
                        citations = "\n".join(
                            f"  - 第 {citation['page']} 页: {citation['content'][:50]}..."
                            for citation in result["citations"][:3]
                        )
                        response_parts.append(f"\n🔎 **引用来源**:\n{citations}\n")

            elif intent == "data_agent":
                if files["csv_df"] is None:
                    response_parts.append("⚠️ **数据分析**需要先上传 CSV 文件（在左侧边栏上传）\n")
                else:
                    with st.spinner("正在生成并安全执行代码..."):
                        result = agent_answer(files["csv_df"], user_input)
                    response_parts.append(f"📊 **数据分析结果**:\n```\n{result['answer']}\n```\n")
                    response_parts.append(f"\n📝 **生成的代码**:\n```python\n{result['code']}\n```\n")
                    if result["chart"]:
                        chart = result["chart"]
                        response_parts.append("\n📈 **图表已生成**\n")

            elif intent == "vision_extract":
                if files["image_path"] is None:
                    response_parts.append("⚠️ **图片识别**需要先上传图片（在左侧边栏上传）\n")
                else:
                    with st.spinner("正在识别图片..."):
                        result = vision_answer(files["image_path"], user_input)
                    response_parts.append(f"🖼️ **图片识别结果**:\n{result['answer']}\n")
                    if result.get("contract"):
                        response_parts.append(
                            f"\n📄 **结构化数据**:\n```json\n"
                            f"{json.dumps(result['contract'], ensure_ascii=False, indent=2)}\n```\n"
                        )

            else:
                with st.spinner("正在思考..."):
                    answer = general_answer(user_input, st.session_state.messages)
                response_parts.append(f"💬 **回答**:\n{answer}\n")
        except Exception as exc:
            response_parts.append(f"❌ **{get_intent_badge(intent)} 执行失败**: {exc}\n")

    return {"content": "\n".join(response_parts), "chart": chart}

