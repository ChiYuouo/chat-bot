import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.rag.retrieval import BM25Index, hybrid_retrieve, reciprocal_rank_fusion


def _document(chunk_id):
    return SimpleNamespace(
        page_content=chunk_id,
        metadata={"chunk_id": chunk_id},
    )


class BM25IndexTests(unittest.TestCase):
    def test_small_corpus_keeps_relevant_high_frequency_terms(self):
        chunks = [
            SimpleNamespace(page_content="员工年假十天"),
            SimpleNamespace(page_content="员工年假规定"),
        ]

        results = BM25Index(chunks).search("员工年假", k=2)

        self.assertEqual(results, chunks)

    def test_rejects_empty_chunks(self):
        with self.assertRaisesRegex(ValueError, "无文本块"):
            BM25Index([])


class ReciprocalRankFusionTests(unittest.TestCase):
    def test_accumulates_scores_from_multiple_rankings(self):
        scores = reciprocal_rank_fusion(
            {
                "vector": ["chunk-a", "chunk-b"],
                "keyword": ["chunk-b", "chunk-c"],
            },
            rrf_k=60,
        )

        self.assertAlmostEqual(scores["chunk-a"], 1 / 61)
        self.assertAlmostEqual(scores["chunk-b"], 1 / 62 + 1 / 61)
        self.assertAlmostEqual(scores["chunk-c"], 1 / 62)
        self.assertGreater(scores["chunk-b"], scores["chunk-a"])

    def test_supports_more_than_two_rankings(self):
        scores = reciprocal_rank_fusion(
            {"dense": ["a"], "sparse": ["a"], "extra": ["b", "a"]},
            rrf_k=10,
        )

        self.assertAlmostEqual(scores["a"], 1 / 11 + 1 / 11 + 1 / 12)
        self.assertAlmostEqual(scores["b"], 1 / 11)


class HybridRetrieveTests(unittest.TestCase):
    def test_retrieves_with_rewritten_and_original_queries(self):
        documents = {name: _document(name) for name in ["a", "b", "c", "d"]}
        vector_store = Mock()
        vector_store.similarity_search.side_effect = [
            [documents["a"], documents["b"]],
            [documents["c"], documents["a"]],
        ]
        keyword_index = Mock()
        keyword_index.search.side_effect = [
            [documents["b"]],
            [documents["d"], documents["a"]],
        ]

        candidates, debug = hybrid_retrieve(
            "员工年假有多少天",
            vector_store,
            keyword_index,
            per_route_k=2,
            fusion_k=4,
            original_query="那有多少天",
        )

        self.assertEqual(vector_store.similarity_search.call_count, 2)
        self.assertEqual(keyword_index.search.call_count, 2)
        self.assertEqual(debug["queries"]["original"], "那有多少天")
        self.assertIn("vector_original", debug["route_rankings"])
        self.assertEqual(candidates[0].chunk_id, "a")

    def test_does_not_repeat_routes_when_queries_are_equal(self):
        document = _document("a")
        vector_store = Mock()
        vector_store.similarity_search.return_value = [document]
        keyword_index = Mock()
        keyword_index.search.return_value = [document]

        _, debug = hybrid_retrieve(
            "员工年假",
            vector_store,
            keyword_index,
            per_route_k=2,
            fusion_k=2,
            original_query="员工年假",
        )

        vector_store.similarity_search.assert_called_once()
        keyword_index.search.assert_called_once()
        self.assertNotIn("original", debug["queries"])


if __name__ == "__main__":
    unittest.main()
