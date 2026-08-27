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

    @patch("app.capabilities.general.create_chat_model")
    def test_streams_chunks_and_returns_complete_answer(self, create_chat_model):
        llm = Mock()
        llm.stream.return_value = [
            Mock(content="你"),
            Mock(content=[{"text": "好"}]),
        ]
        create_chat_model.return_value = llm
        received = []

        answer = general_answer("打个招呼", [], received.append)

        self.assertEqual(answer, "你好")
        self.assertEqual(received, ["你", "好"])
        llm.invoke.assert_not_called()
        self.assertTrue(create_chat_model.call_args.kwargs["streaming"])
        self.assertEqual(
            llm.stream.call_args.args[0],
            [HumanMessage(content="打个招呼")],
        )


if __name__ == "__main__":
    unittest.main()
