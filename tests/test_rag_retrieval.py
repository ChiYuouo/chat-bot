import unittest
from types import SimpleNamespace

from app.rag.retrieval import BM25Index, reciprocal_rank_fusion


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


if __name__ == "__main__":
    unittest.main()
