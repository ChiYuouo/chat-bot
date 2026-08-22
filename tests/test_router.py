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

    @patch("app.router.general_answer", return_value="普通回答")
    @patch("app.router.recognize_intent")
    def test_low_confidence_intent_falls_back_to_general(self, recognize_intent, general_answer):
        recognize_intent.return_value = IntentResult(
            intent=["data_agent"],
            confidence=0.2,
        )
        files = {"csv_df": object(), "pdf_chunks": None, "image_path": None}

        with patch.object(router, "st", _fake_streamlit(files)):
            result = router.process_user_message("帮我分析")

        general_answer.assert_called_once()
        self.assertIn("已自动降级", result["content"])
        self.assertIsNone(result["chart"])

    @patch("app.router.rag_answer")
    @patch("app.router.build_keyword_index")
    @patch("app.router.build_vector_store")
    @patch("app.router.recognize_intent")
    def test_pdf_vector_store_is_built_only_once(
        self,
        recognize_intent,
        build_vector_store,
        build_keyword_index,
        rag_answer,
    ):
        recognize_intent.return_value = IntentResult(intent=["rag_qa"], confidence=0.9)
        store = Mock()
        keyword_index = Mock()
        build_vector_store.return_value = store
        build_keyword_index.return_value = keyword_index
        rag_answer.return_value = {"answer": "文档回答", "citations": [], "debug": {}}
        files = {
            "csv_df": None,
            "pdf_chunks": [Mock()],
            "pdf_store": None,
            "pdf_keyword_index": None,
            "image_path": None,
        }

        with patch.object(router, "st", _fake_streamlit(files)):
            router.process_user_message("文档内容是什么？")
            router.process_user_message("再总结一下")

        build_vector_store.assert_called_once_with(files["pdf_chunks"])
        build_keyword_index.assert_called_once_with(files["pdf_chunks"])
        self.assertEqual(rag_answer.call_count, 2)
        self.assertIs(files["pdf_store"], store)
        self.assertIs(files["pdf_keyword_index"], keyword_index)


if __name__ == "__main__":
    unittest.main()
