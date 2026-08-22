import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.rag.rerank import llm_rerank
from app.rag.retrieval import SearchCandidate


def _candidate(chunk_id, content):
    document = SimpleNamespace(
        page_content=content,
        metadata={"display_page": 1},
    )
    return SearchCandidate(chunk_id=chunk_id, document=document)


class LlmRerankTests(unittest.TestCase):
    @patch("app.rag.rerank.create_chat_model")
    def test_uses_only_valid_ids_and_keeps_model_order(self, create_chat_model):
        llm = Mock()
        llm.invoke.return_value = Mock(
            content='{"ranked_chunk_ids":["chunk-b","invented","chunk-a"]}'
        )
        create_chat_model.return_value = llm

        ranked, debug = llm_rerank(
            "问题",
            [_candidate("chunk-a", "A"), _candidate("chunk-b", "B")],
        )

        self.assertEqual([item.chunk_id for item in ranked], ["chunk-b", "chunk-a"])
        self.assertTrue(debug["applied"])

    @patch("app.rag.rerank.create_chat_model")
    def test_falls_back_to_fusion_order_on_invalid_json(self, create_chat_model):
        llm = Mock()
        llm.invoke.return_value = Mock(content="不是 JSON")
        create_chat_model.return_value = llm
        original = [_candidate("chunk-a", "A"), _candidate("chunk-b", "B")]

        ranked, debug = llm_rerank("问题", original)

        self.assertEqual(ranked, original)
        self.assertFalse(debug["applied"])
        self.assertIn("已保留混排顺序", debug["reason"])


if __name__ == "__main__":
    unittest.main()
