"""意图到能力模块的路由。"""

import json
import re
from collections.abc import Callable
from contextlib import nullcontext
from typing import Any, Dict

import streamlit as st

from app.capabilities.data_agent import agent_answer
from app.capabilities.general import general_answer
from app.capabilities.rag import rag_answer
from app.capabilities.vision import vision_answer
from app.config import Config
from app.intent import recognize_intent
from app.knowledge_base import ensure_indexes


def get_intent_badge(intent: str) -> str:
    badges = {
        "rag_qa": "📚 RAG",
        "data_agent": "📊 数据分析",
        "vision_extract": "🖼️ Vision",
        "general": "💬 普通问答",
    }
    return badges.get(intent, intent)


def _looks_like_contextual_follow_up(text: str) -> bool:
    """识别需要依赖上一轮才能理解的短追问，保证它能进入 Rewrite。"""
    normalized = text.strip()
    return len(normalized) <= 30 and bool(
        re.search(r"^(那|那么|它|其中|这个|上述|前面|再|还有|多少|几|为什么|如何)", normalized)
    )


def _format_citation(citation: Dict[str, Any]) -> str:
    location = re.sub(r"\s+", " ", str(citation.get("location") or "未知资料")).strip()
    url = re.sub(r"\s+", "", str(citation.get("url") or ""))
    if url:
        # 使用 Markdown 自动链接，避免长 URL 与来源名称粘连。
        safe_url = url.replace("<", "%3C").replace(">", "%3E")
        return f"- {location} · <{safe_url}>"
    return f"- {location}"


def _format_citations(citations: list[Dict[str, Any]]) -> str:
    """按实际来源位置去重，只展示来源，不渲染原始 Chunk 正文。"""
    lines = []
    seen = set()
    for citation in citations:
        key = (
            str(citation.get("location") or "").strip(),
            str(citation.get("url") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        lines.append(_format_citation(citation))
    return "\n".join(lines)


def process_user_message(
    user_input: str,
    *,
    uploaded_files: Dict[str, Any] | None = None,
    messages: list[Dict[str, Any]] | None = None,
    last_intents: list[str] | None = None,
    spinner_factory: Any | None = None,
    stream_callback: Callable[[str], None] | None = None,
) -> Dict[str, Any]:
    """处理一次对话，可由 Streamlit 或 HTTP 适配层复用。"""
    uses_streamlit_state = uploaded_files is None
    files = uploaded_files if uploaded_files is not None else st.session_state.uploaded_files
    message_history = messages if messages is not None else st.session_state.messages
    previous_intents = (
        list(last_intents)
        if last_intents is not None
        else list(getattr(st.session_state, "last_intents", []))
    )
    spinner = spinner_factory or (
        st.spinner if uses_streamlit_state else lambda _message: nullcontext()
    )
    chart = None
    rag_debug = None
    prefetched_rag_result = None

    try:
        intent_result = recognize_intent(user_input)
    except Exception as exc:
        with spinner("意图识别失败，正在使用普通问答..."):
            answer = general_answer(user_input, message_history, stream_callback)
        return {
            "content": f"⚠️ **意图识别已降级**: {exc}\n\n💬 **回答**:\n{answer}",
            "chart": None,
            "rag_debug": None,
            "intents": ["general"],
        }

    intents = intent_result.intent
    fallback_reason = None
    routing_note = None
    if not intents:
        intents = ["general"]
        fallback_reason = "未识别到有效意图"
    elif intent_result.confidence < Config.CONFIDENCE_THRESHOLD:
        intents = ["general"]
        fallback_reason = f"意图置信度较低（{intent_result.confidence:.0%}）"

    # 展示模型最初识别出的意图；后续自适应切换通过 routing_note 单独说明，
    # 避免把 general 的置信度错误标成 RAG 置信度。
    display_intents = list(intents)

    # “那最多几天”通常会被意图模型判为 general；结合上一轮意图把短追问送回 RAG，
    # 后续 Rewrite 才有机会将其中的指代补全为可独立检索的问题。
    if (
        intents == ["general"]
        and "rag_qa" in previous_intents
        and bool(files.get("knowledge_chunks"))
        and _looks_like_contextual_follow_up(user_input)
    ):
        intents = ["rag_qa"]
        fallback_reason = None
        routing_note = "识别为上一轮知识库问答的追问"


    # 请求先做一次知识库相关性预检：只有精排明确命中时才切换到 RAG；未命中或精排
    # 降级时继续普通问答，避免知识库存在后所有闲聊都返回“资料中未找到”。
    eligible_for_knowledge_precheck = (
        not intent_result.intent
        or all(intent in {"general", "rag_qa"} for intent in intent_result.intent)
    )
    if (
        intents == ["general"]
        and eligible_for_knowledge_precheck
        and bool(files.get("knowledge_chunks"))
    ):
        try:
            with spinner("正在检查知识库中是否有相关资料..."):
                store, keyword_index = ensure_indexes(files)
                rag_history = (
                    message_history[-2:]
                    if "rag_qa" in previous_intents
                    else []
                )
                candidate_result = rag_answer(
                    user_input,
                    store,
                    keyword_index,
                    rag_history,
                )
            rag_debug = candidate_result.get("debug")
            rerank_applied = bool(
                (rag_debug or {}).get("rerank", {}).get("applied")
            )
            has_answer = candidate_result.get(
                "has_answer",
                bool(candidate_result.get("citations")),
            )
            if candidate_result.get("citations") and rerank_applied and has_answer:
                intents = ["rag_qa"]
                prefetched_rag_result = candidate_result
                fallback_reason = None
                routing_note = "知识库命中相关资料，已自动使用 RAG"
        except Exception as exc:
            # 自适应预检是普通问答的增强能力，失败不能阻断原有普通问答。
            rag_debug = {"adaptive_rag_error": str(exc)}

    intent_str = ", ".join(get_intent_badge(intent) for intent in display_intents)
    confidence_str = f"{intent_result.confidence:.0%}"
    response_parts = [f"🎆 **意图识别**: {intent_str} (置信度: {confidence_str})\n"]
    if fallback_reason:
        response_parts.append(f"⚠️ {fallback_reason}，已自动降级为普通问答。\n")
    if routing_note:
        response_parts.append(f"ℹ️ {routing_note}。\n")

    for intent in intents:
        try:
            if intent == "rag_qa":
                if not files.get("knowledge_chunks"):
                    response_parts.append("⚠️ **RAG 问答**需要先添加知识库资料\n")
                else:
                    result = prefetched_rag_result
                    if result is None:
                        with spinner("正在准备知识库检索索引..."):
                            store, keyword_index = ensure_indexes(files)
                        rag_history = (
                            message_history[-2:]
                            if "rag_qa" in previous_intents
                            else []
                        )
                        with spinner("正在改写问题、混合检索并精排..."):
                            result = rag_answer(
                                user_input,
                                store,
                                keyword_index,
                                rag_history,
                            )
                    rag_debug = result.get("debug")
                    response_parts.append(f"📚 **RAG 回答**:\n{result['answer']}\n")
                    if result["citations"]:
                        citations = _format_citations(result["citations"])
                        response_parts.append(f"\n🔎 **引用来源**:\n{citations}\n")

            elif intent == "data_agent":
                if files["csv_df"] is None:
                    response_parts.append("⚠️ **数据分析**需要先上传 CSV 文件（在左侧边栏上传）\n")
                else:
                    with spinner("正在生成并安全执行代码..."):
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
                    with spinner("正在识别图片..."):
                        result = vision_answer(files["image_path"], user_input)
                    response_parts.append(f"🖼️ **图片识别结果**:\n{result['answer']}\n")
                    if result.get("contract"):
                        response_parts.append(
                            f"\n📄 **结构化数据**:\n```json\n"
                            f"{json.dumps(result['contract'], ensure_ascii=False, indent=2)}\n```\n"
                        )

            else:
                with spinner("正在思考..."):
                    answer = general_answer(user_input, message_history, stream_callback)
                response_parts.append(f"💬 **回答**:\n{answer}\n")
        except Exception as exc:
            response_parts.append(f"❌ **{get_intent_badge(intent)} 执行失败**: {exc}\n")

    if uses_streamlit_state:
        st.session_state.last_intents = intents
    return {
        "content": "\n".join(response_parts),
        "chart": chart,
        "rag_debug": rag_debug,
        "intents": intents,
    }
