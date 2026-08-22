import unittest
from unittest.mock import Mock, patch

from langchain_core.messages import AIMessage, HumanMessage

from app.capabilities.general import general_answer


class GeneralAnswerTests(unittest.TestCase):
    @patch("app.capabilities.general.create_chat_model")
    def test_current_question_is_added_once(self, create_chat_model):
        llm = Mock()
        llm.invoke.return_value = Mock(content="回答")
        create_chat_model.return_value = llm
        history = [
            {"role": "user", "content": "上一个问题"},
            {"role": "assistant", "content": "上一个回答"},
        ]

        answer = general_answer("当前问题", history)

        self.assertEqual(answer, "回答")
        sent_messages = llm.invoke.call_args.args[0]
        self.assertEqual(
            sent_messages,
            [
                HumanMessage(content="上一个问题"),
                AIMessage(content="上一个回答"),
                HumanMessage(content="当前问题"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
