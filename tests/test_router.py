import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models import IntentResult
from app import router


def _fake_streamlit(files):
    return SimpleNamespace(
        session_state=SimpleNamespace(uploaded_files=files, messages=[]),
        spinner=lambda _message: nullcontext(),
    )


class RouterTests(unittest.TestCase):
    def test_detects_short_contextual_follow_up(self):
        self.assertTrue(router._looks_like_contextual_follow_up("那最多有几天？"))
        self.assertFalse(router._looks_like_contextual_follow_up("请帮我写一封会议邀请邮件"))

    def test_citation_list_does_not_render_chunk_markdown_and_deduplicates_source(self):
        citations = [
            {
                "location": "Flutter Day02 - Telus，网页资料",
                "url": "https://example.com/flutter",
                "content": "## TextField\n10\n- [ ] 任务项\n```dart\n代码",
            },
            {
                "location": "Flutter Day02 - Telus，网页资料",
                "url": "https://example.com/flutter",
                "content": "另一个 Chunk 的正文",
            },
        ]

        formatted = router._format_citations(citations)

        self.assertEqual(
            formatted,
            "- Flutter Day02 - Telus，网页资料 · <https://example.com/flutter>",
        )
        self.assertNotIn("TextField", formatted)
        self.assertNotIn("任务项", formatted)

    def test_citation_without_url_only_shows_location(self):
        formatted = router._format_citation({
            "location": "员工手册.pdf，\n第 3 页",
            "content": "员工年假为十天。",
        })

        self.assertEqual(formatted, "- 员工手册.pdf， 第 3 页")

    @patch("app.router.recognize_intent")
    def test_rag_requires_at_least_one_knowledge_chunk(self, recognize_intent):
        recognize_intent.return_value = IntentResult(intent=["rag_qa"], confidence=0.9)
        files = {
            "csv_df": None,
            "knowledge_chunks": [],
            "knowledge_store": None,
            "knowledge_keyword_index": None,
            "image_path": None,
        }

        with patch.object(router, "st", _fake_streamlit(files)):
            result = router.process_user_message("文档内容是什么？")

        self.assertIn("需要先添加知识库资料", result["content"])

    @patch("app.router.general_answer", return_value="普通回答")
    @patch("app.router.recognize_intent")
    def test_low_confidence_intent_falls_back_to_general(self, recognize_intent, general_answer):
        recognize_intent.return_value = IntentResult(
            intent=["data_agent"],
            confidence=0.2,
        )
        files = {"csv_df": object(), "knowledge_chunks": [], "image_path": None}

        with patch.object(router, "st", _fake_streamlit(files)):
            result = router.process_user_message("帮我分析")

        general_answer.assert_called_once()
        self.assertIn("已自动降级", result["content"])
        self.assertIsNone(result["chart"])

    @patch("app.router.general_answer")
    @patch("app.router.rag_answer")
    @patch("app.router.ensure_indexes")
    @patch("app.router.recognize_intent")
    def test_general_question_uses_rag_when_knowledge_is_relevant(
        self,
        recognize_intent,
        ensure_indexes,
        rag_answer,
        general_answer,
    ):
        recognize_intent.return_value = IntentResult(intent=["general"], confidence=0.9)
        store = Mock()
        keyword_index = Mock()
        ensure_indexes.return_value = store, keyword_index
        rag_answer.return_value = {
            "answer": "TextField 可通过 controller 读取输入值。",
            "citations": [{
                "chunk_id": "flutter-text-field",
                "location": "Flutter Day02，网页资料",
                "url": "https://example.com/flutter",
                "content": "controller 用于读取输入内容。",
            }],
            "debug": {"rerank": {"applied": True}},
        }
        files = {
            "csv_df": None,
            "knowledge_chunks": [Mock()],
            "knowledge_store": None,
            "knowledge_keyword_index": None,
            "image_path": None,
        }
        fake_st = _fake_streamlit(files)

        with patch.object(router, "st", fake_st):
            result = router.process_user_message("TextField 如何获取输入内容？")

        rag_answer.assert_called_once_with(
            "TextField 如何获取输入内容？",
            store,
            keyword_index,
            [],
        )
        general_answer.assert_not_called()
        self.assertIn("RAG 回答", result["content"])
        self.assertIn("普通问答 (置信度: 90%)", result["content"])
        self.assertNotIn("RAG (置信度: 90%)", result["content"])
        self.assertNotIn("执行失败", result["content"])
        self.assertEqual(fake_st.session_state.last_intents, ["rag_qa"])

    @patch("app.router.general_answer", return_value="这是普通对话生成的计算器代码")
    @patch("app.router.rag_answer")
    @patch("app.router.ensure_indexes")
    @patch("app.router.recognize_intent")
    def test_adaptive_rag_falls_back_when_answer_model_rejects_context(
        self,
        recognize_intent,
        ensure_indexes,
        rag_answer,
        general_answer,
    ):
        recognize_intent.return_value = IntentResult(intent=["general"], confidence=0.91)
        ensure_indexes.return_value = Mock(), Mock()
        rag_answer.return_value = {
            "answer": "资料中未找到相关信息。",
            "citations": [{
                "chunk_id": "false-positive",
                "location": "sample_document.pdf，第 2 页",
                "url": None,
            }],
            "debug": {"rerank": {"applied": True}},
            "has_answer": False,
        }
        files = {
            "csv_df": None,
            "knowledge_chunks": [Mock()],
            "knowledge_store": None,
            "knowledge_keyword_index": None,
            "image_path": None,
        }

        with patch.object(router, "st", _fake_streamlit(files)):
            result = router.process_user_message("一个基本的计算器")

        general_answer.assert_called_once()
        self.assertIn("这是普通对话生成的计算器代码", result["content"])
        self.assertNotIn("资料中未找到相关信息", result["content"])
        self.assertNotIn("引用来源", result["content"])

    @patch("app.router.general_answer", return_value="普通回答")
    @patch("app.router.rag_answer")
    @patch("app.router.ensure_indexes")
    @patch("app.router.recognize_intent")
    def test_general_question_falls_back_when_knowledge_is_not_relevant(
        self,
        recognize_intent,
        ensure_indexes,
        rag_answer,
        general_answer,
    ):
        recognize_intent.return_value = IntentResult(intent=["general"], confidence=0.9)
        ensure_indexes.return_value = Mock(), Mock()
        rag_answer.return_value = {
            "answer": "资料中未找到相关信息。",
            "citations": [],
            "debug": {"rerank": {"applied": True}},
        }
        files = {
            "csv_df": None,
            "knowledge_chunks": [Mock()],
            "knowledge_store": None,
            "knowledge_keyword_index": None,
            "image_path": None,
        }
        fake_st = _fake_streamlit(files)

        with patch.object(router, "st", fake_st):
            result = router.process_user_message("帮我写一句生日祝福")

        rag_answer.assert_called_once()
        general_answer.assert_called_once()
        self.assertIn("普通回答", result["content"])
        self.assertNotIn("资料中未找到相关信息", result["content"])
        self.assertEqual(fake_st.session_state.last_intents, ["general"])

    @patch("app.router.general_answer", return_value="普通回答")
    @patch("app.router.rag_answer")
    @patch("app.router.ensure_indexes")
    @patch("app.router.recognize_intent")
    def test_general_question_does_not_trust_unfiltered_rag_fallback(
        self,
        recognize_intent,
        ensure_indexes,
        rag_answer,
        general_answer,
    ):
        recognize_intent.return_value = IntentResult(intent=["general"], confidence=0.9)
        ensure_indexes.return_value = Mock(), Mock()
        rag_answer.return_value = {
            "answer": "候选块生成的回答",
            "citations": [{"chunk_id": "unverified"}],
            "debug": {"rerank": {"applied": False}},
        }
        files = {
            "csv_df": None,
            "knowledge_chunks": [Mock()],
            "knowledge_store": None,
            "knowledge_keyword_index": None,
            "image_path": None,
        }

        with patch.object(router, "st", _fake_streamlit(files)):
            result = router.process_user_message("帮我写一句生日祝福")

        general_answer.assert_called_once()
        self.assertIn("普通回答", result["content"])
        self.assertNotIn("候选块生成的回答", result["content"])

    @patch("app.router.general_answer")
    @patch("app.router.rag_answer")
    @patch("app.router.ensure_indexes")
    @patch("app.router.recognize_intent")
    def test_low_confidence_rag_intent_is_rescued_by_relevant_knowledge(
        self,
        recognize_intent,
        ensure_indexes,
        rag_answer,
        general_answer,
    ):
        recognize_intent.return_value = IntentResult(intent=["rag_qa"], confidence=0.4)
        ensure_indexes.return_value = Mock(), Mock()
        rag_answer.return_value = {
            "answer": "资料回答",
            "citations": [{
                "chunk_id": "relevant",
                "location": "员工手册，第 3 页",
                "url": None,
                "content": "员工年假为十天。",
            }],
            "debug": {"rerank": {"applied": True}},
        }
        files = {
            "csv_df": None,
            "knowledge_chunks": [Mock()],
            "knowledge_store": None,
            "knowledge_keyword_index": None,
            "image_path": None,
        }

        with patch.object(router, "st", _fake_streamlit(files)):
            result = router.process_user_message("员工年假有多少天？")

        general_answer.assert_not_called()
        self.assertIn("RAG 回答", result["content"])
        self.assertNotIn("已自动降级为普通问答", result["content"])

    @patch("app.router.rag_answer")
    @patch("app.router.ensure_indexes")
    @patch("app.router.recognize_intent")
    def test_rag_uses_knowledge_base_indexes(
        self,
        recognize_intent,
        ensure_indexes,
        rag_answer,
    ):
        recognize_intent.return_value = IntentResult(intent=["rag_qa"], confidence=0.9)
        store = Mock()
        keyword_index = Mock()
        ensure_indexes.return_value = store, keyword_index
        rag_answer.return_value = {"answer": "文档回答", "citations": [], "debug": {}}
        files = {
            "csv_df": None,
            "knowledge_chunks": [Mock()],
            "knowledge_store": None,
            "knowledge_keyword_index": None,
            "image_path": None,
        }

        with patch.object(router, "st", _fake_streamlit(files)):
            router.process_user_message("文档内容是什么？")

        ensure_indexes.assert_called_once_with(files)
        rag_answer.assert_called_once_with("文档内容是什么？", store, keyword_index, [])

    @patch("app.router.rag_answer")
    @patch("app.router.ensure_indexes")
    @patch("app.router.recognize_intent")
    def test_knowledge_rewrite_uses_previous_global_turn_after_rag(
        self,
        recognize_intent,
        ensure_indexes,
        rag_answer,
    ):
        recognize_intent.return_value = IntentResult(intent=["rag_qa"], confidence=0.9)
        ensure_indexes.return_value = Mock(), Mock()
        seen_histories = []

        def answer(_question, _store, _keyword_index, history):
            seen_histories.append(list(history))
            return {"answer": "当前文档回答", "citations": [], "debug": {}}

        rag_answer.side_effect = answer
        files = {
            "csv_df": None,
            "knowledge_chunks": [Mock()],
            "knowledge_store": None,
            "knowledge_keyword_index": None,
            "image_path": None,
        }
        fake_st = _fake_streamlit(files)
        fake_st.session_state.messages = [
            {"role": "user", "content": "普通聊天问题"},
            {"role": "assistant", "content": "普通聊天回答"},
        ]

        with patch.object(router, "st", fake_st):
            router.process_user_message("当前 PDF 的问题")
            # Streamlit 主流程会在本轮处理完成后把问答写入全局 messages。
            fake_st.session_state.messages.extend([
                {"role": "user", "content": "当前 PDF 的问题"},
                {"role": "assistant", "content": "当前文档回答"},
            ])
            router.process_user_message("那具体是多少？")

        self.assertEqual(seen_histories[0], [])
        self.assertEqual(
            seen_histories[1],
            [
                {"role": "user", "content": "当前 PDF 的问题"},
                {"role": "assistant", "content": "当前文档回答"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
