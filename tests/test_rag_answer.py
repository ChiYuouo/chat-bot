import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.capabilities.rag import rag_answer
from app.rag.retrieval import SearchCandidate


class RagAnswerTests(unittest.TestCase):
    @patch("app.capabilities.rag.create_chat_model")
    @patch("app.capabilities.rag.llm_rerank")
    @patch("app.capabilities.rag.hybrid_retrieve")
    @patch("app.capabilities.rag.rewrite_query")
    def test_answer_prompt_leaves_citations_to_the_ui(
        self,
        rewrite_query,
        hybrid_retrieve,
        llm_rerank,
        create_chat_model,
    ):
        document = SimpleNamespace(
            page_content="TextField 可以使用 controller 读取输入内容。",
            metadata={
                "chunk_id": "chunk-text-field",
                "source_id": "source-flutter",
                "source": "Flutter Day02",
                "modality": "url",
                "url": "https://example.com/flutter",
            },
        )
        candidate = SearchCandidate("chunk-text-field", document)
        rewrite_query.return_value = "TextField 如何读取输入内容？", {"applied": False}
        hybrid_retrieve.return_value = [candidate], {"fusion_method": "rrf"}
        llm_rerank.return_value = [candidate], {"applied": True}
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content="使用 controller 读取输入内容。")
        create_chat_model.return_value = model

        result = rag_answer("TextField 如何读取输入内容？", Mock(), Mock())

        prompt = model.invoke.call_args.args[0]
        self.assertIn("不要在每个要点后插入来源标注", prompt)
        self.assertIn("界面会在回答末尾统一展示引用来源", prompt)
        self.assertNotIn("每个关键信息都要说明具体来源", prompt)
        self.assertEqual(result["answer"], "使用 controller 读取输入内容。")
        self.assertEqual(len(result["citations"]), 1)
        self.assertTrue(result["has_answer"])

    @patch("app.capabilities.rag.create_chat_model")
    @patch("app.capabilities.rag.llm_rerank")
    @patch("app.capabilities.rag.hybrid_retrieve")
    @patch("app.capabilities.rag.rewrite_query")
    def test_removes_citations_when_answer_model_rejects_context(
        self,
        rewrite_query,
        hybrid_retrieve,
        llm_rerank,
        create_chat_model,
    ):
        document = SimpleNamespace(
            page_content="与问题只有表面词语相似的内容。",
            metadata={
                "chunk_id": "chunk-false-positive",
                "source_id": "source-pdf",
                "source": "sample.pdf",
                "modality": "pdf",
                "page": 0,
            },
        )
        candidate = SearchCandidate("chunk-false-positive", document)
        rewrite_query.return_value = "一个基本的计算器", {"applied": False}
        hybrid_retrieve.return_value = [candidate], {"fusion_method": "rrf"}
        llm_rerank.return_value = [candidate], {"applied": True}
        model = Mock()
        model.invoke.return_value = SimpleNamespace(content="资料中未找到相关信息。")
        create_chat_model.return_value = model

        result = rag_answer("一个基本的计算器", Mock(), Mock())

        self.assertFalse(result["has_answer"])
        self.assertEqual(result["citations"], [])
        self.assertFalse(result["debug"]["has_answer"])


if __name__ == "__main__":
    unittest.main()
