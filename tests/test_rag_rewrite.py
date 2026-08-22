import unittest
from unittest.mock import Mock, patch

from app.rag.rewrite import rewrite_query


class QueryRewriteTests(unittest.TestCase):
    @patch("app.rag.rewrite.create_chat_model")
    def test_skips_llm_without_history(self, create_chat_model):
        query, debug = rewrite_query("病假有几天？", [])

        self.assertEqual(query, "病假有几天？")
        self.assertFalse(debug["applied"])
        create_chat_model.assert_not_called()

    @patch("app.rag.rewrite.create_chat_model")
    def test_rewrites_contextual_question(self, create_chat_model):
        llm = Mock()
        llm.invoke.return_value = Mock(
            content='{"standalone_query":"员工手册规定病假最多有几天？"}'
        )
        create_chat_model.return_value = llm

        query, debug = rewrite_query(
            "那最多有几天？",
            [{"role": "user", "content": "员工手册中的病假规定是什么？"}],
        )

        self.assertEqual(query, "员工手册规定病假最多有几天？")
        self.assertTrue(debug["applied"])


if __name__ == "__main__":
    unittest.main()
