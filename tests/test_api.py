import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import app, session_store
from app.models import KnowledgeSource


def _source(source_id="source-a", name="A.md", modality="text"):
    return KnowledgeSource(
        source_id=source_id,
        name=name,
        modality=modality,
        chunk_count=1,
    )


def _chunk(source_id="source-a"):
    return SimpleNamespace(
        page_content="测试资料内容",
        metadata={"source_id": source_id, "chunk_id": "chunk-a"},
    )


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "copilot.sqlite3"
        self.database_environment = patch.dict(
            os.environ,
            {
                "COPILOT_DATABASE_PATH": str(self.database_path),
            },
        )
        self.database_environment.start()
        session_store.clear()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        session_store.clear()
        self.database_environment.stop()
        self.temporary_directory.cleanup()

    def test_health_and_session_cookie(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("copilot_session_id", response.cookies)

    @patch("app.api.process_user_message")
    def test_register_migrates_anonymous_conversation_to_user_account(
        self, process_user_message
    ):
        process_user_message.side_effect = [
            {"content": "第一轮回答", "chart": None, "rag_debug": None, "intents": ["general"]},
            {"content": "第二轮回答", "chart": None, "rag_debug": None, "intents": ["general"]},
        ]
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-a", "message": "匿名问题"},
        )

        registered = self.client.post(
            "/api/auth/register",
            json={"email": "learner@example.com", "password": "correct-horse"},
        )

        self.assertEqual(registered.status_code, 201)
        self.assertEqual(registered.json()["email"], "learner@example.com")
        self.assertIn("copilot_auth_token", registered.cookies)

        # 内存 Session 消失后，数据仍按用户 ID 恢复，而不是依赖匿名 Cookie。
        session_store.clear()
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-a", "message": "登录后追问"},
        )
        self.assertEqual(process_user_message.call_args_list[1].kwargs["messages"][0]["content"], "匿名问题")

        self.client.post("/api/auth/logout")
        self.assertEqual(self.client.get("/api/conversations").json(), {"conversations": []})

    def test_login_recovers_account_data_in_a_new_browser_session(self):
        registered = self.client.post(
            "/api/auth/register",
            json={"email": "learner@example.com", "password": "correct-horse"},
        )
        self.assertEqual(registered.status_code, 201)

        with TestClient(app) as another_client:
            wrong_password = another_client.post(
                "/api/auth/login",
                json={"email": "learner@example.com", "password": "incorrect-password"},
            )
            logged_in = another_client.post(
                "/api/auth/login",
                json={"email": "learner@example.com", "password": "correct-horse"},
            )

        self.assertEqual(wrong_password.status_code, 401)
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(logged_in.json()["email"], "learner@example.com")

    @patch("app.api.ingest_text_file")
    def test_register_migrates_anonymous_knowledge_sources(self, ingest_text_file):
        ingest_text_file.return_value = (_source(), [_chunk()])
        self.client.post(
            "/api/sources",
            data={"kind": "text"},
            files={"file": ("A.md", b"content", "text/markdown")},
        )
        self.client.post(
            "/api/auth/register",
            json={"email": "learner@example.com", "password": "correct-horse"},
        )

        session_store.clear()
        restored = self.client.get("/api/sources")

        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["sources"][0]["source_id"], "source-a")

    @patch("app.api.ingest_text_file")
    def test_upload_list_and_delete_knowledge_source(self, ingest_text_file):
        ingest_text_file.return_value = (_source(), [_chunk()])

        uploaded = self.client.post(
            "/api/sources",
            data={"kind": "text"},
            files={"file": ("A.md", b"# title\ncontent", "text/markdown")},
        )
        listed = self.client.get("/api/sources")
        deleted = self.client.delete("/api/sources/source-a")

        self.assertEqual(uploaded.status_code, 200)
        self.assertEqual(uploaded.json()["source_id"], "source-a")
        self.assertEqual(listed.json()["sources"][0]["source_id"], "source-a")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/sources").json(), {"sources": []})

    @patch("app.api.ingest_text_file")
    def test_sessions_keep_sources_isolated(self, ingest_text_file):
        ingest_text_file.return_value = (_source(), [_chunk()])
        self.client.post(
            "/api/sources",
            data={"kind": "text"},
            files={"file": ("A.md", b"content", "text/markdown")},
        )

        with TestClient(app) as another_client:
            response = another_client.get("/api/sources")

        self.assertEqual(response.json(), {"sources": []})

    @patch("app.api.ingest_text_file")
    def test_sources_are_restored_after_api_process_restart(self, ingest_text_file):
        ingest_text_file.return_value = (_source(), [_chunk()])
        self.client.post(
            "/api/sources",
            data={"kind": "text"},
            files={"file": ("A.md", b"content", "text/markdown")},
        )

        # 模拟 Uvicorn 重启：内存 Session 消失，但浏览器 Cookie 仍在。
        session_store.clear()
        restored = self.client.get("/api/sources")

        self.assertEqual(restored.status_code, 200)
        self.assertEqual(restored.json()["sources"][0]["source_id"], "source-a")

    @patch("app.api.process_user_message")
    def test_conversation_history_and_intent_are_restored_after_restart(
        self, process_user_message
    ):
        process_user_message.side_effect = [
            {"content": "第一轮回答", "chart": None, "rag_debug": None, "intents": ["rag_qa"]},
            {"content": "第二轮回答", "chart": None, "rag_debug": None, "intents": ["rag_qa"]},
        ]
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-a", "message": "员工年假几天？"},
        )

        session_store.clear()
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-a", "message": "那最多几天？"},
        )

        second_call = process_user_message.call_args_list[1]
        self.assertEqual(second_call.kwargs["last_intents"], ["rag_qa"])
        self.assertEqual(
            second_call.kwargs["messages"],
            [
                {"role": "user", "content": "员工年假几天？"},
                {"role": "assistant", "content": "第一轮回答"},
                {"role": "user", "content": "那最多几天？"},
                {"role": "assistant", "content": "第二轮回答"},
            ],
        )

    @patch("app.api.process_user_message")
    def test_lists_reads_renames_and_deletes_persisted_conversation(
        self, process_user_message
    ):
        process_user_message.return_value = {
            "content": "回答", "chart": None, "rag_debug": None, "intents": ["general"]
        }
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-a", "message": "第一问"},
        )

        listed = self.client.get("/api/conversations")
        renamed = self.client.patch(
            "/api/conversations/conversation-a", json={"title": "年假咨询"}
        )
        renamed_list = self.client.get("/api/conversations")
        deleted = self.client.delete("/api/conversations/conversation-a")

        self.assertEqual(listed.json()["conversations"][0]["messages"][0]["content"], "第一问")
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed_list.json()["conversations"][0]["title"], "年假咨询")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(self.client.get("/api/conversations").json(), {"conversations": []})

    @patch("app.api.ingest_url")
    def test_add_url_source(self, ingest_url):
        ingest_url.return_value = (
            _source(source_id="source-url", name="网页", modality="url"),
            [_chunk("source-url")],
        )

        response = self.client.post(
            "/api/sources/url",
            json={"url": "https://example.com/article", "title": "网页"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["modality"], "url")
        ingest_url.assert_called_once_with("https://example.com/article", "网页")

    def test_upload_and_clear_csv(self):
        uploaded = self.client.post(
            "/api/sources",
            data={"kind": "csv"},
            files={"file": ("sales.csv", b"name,value\na,1\nb,2\n", "text/csv")},
        )

        self.assertEqual(uploaded.status_code, 200)
        self.assertEqual(uploaded.json()["id"], "csv")
        self.assertEqual(uploaded.json()["meta"], "2 行")
        self.assertEqual(self.client.delete("/api/sources").status_code, 204)
        self.assertEqual(self.client.get("/api/sources").json(), {"sources": []})

    @patch("app.api.process_user_message")
    def test_chat_returns_chart_url_and_persists_messages(self, process_user_message):
        process_user_message.return_value = {
            "content": "分析完成",
            "chart": b"png-bytes",
            "rag_debug": {"stage": "done"},
            "intents": ["data_agent"],
        }

        response = self.client.post(
            "/api/chat",
            json={"message": "分析销售额"},
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["content"], "分析完成")
        self.assertEqual(body["rag_debug"], {"stage": "done"})
        chart = self.client.get(body["chart_url"])
        self.assertEqual(chart.status_code, 200)
        self.assertEqual(chart.content, b"png-bytes")
        self.assertEqual(chart.headers["content-type"], "image/png")
        call = process_user_message.call_args
        self.assertEqual(call.kwargs["messages"], [
            {"role": "user", "content": "分析销售额"},
            {"role": "assistant", "content": "分析完成"},
        ])

    @patch("app.api.process_user_message")
    def test_request_api_key_is_restored_after_chat(self, process_user_message):
        process_user_message.return_value = {
            "content": "ok",
            "chart": None,
            "rag_debug": None,
            "intents": ["general"],
        }
        original_key = os.environ.get("DASHSCOPE_API_KEY")

        response = self.client.post(
            "/api/chat",
            headers={"X-DashScope-Api-Key": "request-key"},
            json={"message": "你好"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(os.environ.get("DASHSCOPE_API_KEY"), original_key)

    @patch("app.api.process_user_message")
    def test_chat_stream_returns_delta_and_done_events(self, process_user_message):
        def answer(_message, **kwargs):
            kwargs["status_callback"]("正在生成回答...")
            kwargs["stream_callback"]("你")
            kwargs["stream_callback"]("好")
            return {
                "content": "💬 **回答**:\n你好",
                "chart": None,
                "rag_debug": None,
                "intents": ["general"],
            }

        process_user_message.side_effect = answer

        response = self.client.post(
            "/api/chat/stream",
            json={"message": "你好"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("application/x-ndjson"))
        events = [json.loads(line) for line in response.text.splitlines()]
        self.assertEqual([event["type"] for event in events], [
            "status",
            "status",
            "delta",
            "delta",
            "done",
        ])
        self.assertEqual(events[1]["content"], "正在生成回答...")
        self.assertEqual(
            [event["content"] for event in events if event["type"] == "delta"],
            ["你", "好"],
        )
        self.assertEqual(events[-1]["content"], "💬 **回答**:\n你好")

    @patch("app.api.process_user_message")
    def test_conversations_keep_last_intents_isolated(self, process_user_message):
        seen_last_intents = []

        def answer(_message, **kwargs):
            seen_last_intents.append(list(kwargs["last_intents"]))
            intent = "rag_qa" if len(seen_last_intents) == 1 else "general"
            return {
                "content": "ok",
                "chart": None,
                "rag_debug": None,
                "intents": [intent],
            }

        process_user_message.side_effect = answer
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-a", "message": "A1"},
        )
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-b", "message": "B1"},
        )
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-a", "message": "A2"},
        )

        self.assertEqual(seen_last_intents, [[], [], ["rag_qa"]])

    def test_missing_source_returns_404(self):
        response = self.client.delete("/api/sources/not-found")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "资料不存在")


if __name__ == "__main__":
    unittest.main()
