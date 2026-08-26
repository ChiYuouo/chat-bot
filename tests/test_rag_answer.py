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


if __name__ == "__main__":
    unittest.main()
