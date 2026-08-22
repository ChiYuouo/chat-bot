import unittest

from app.rag.retrieval import reciprocal_rank_fusion


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
