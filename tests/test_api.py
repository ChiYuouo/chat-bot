import os
import unittest
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
    return SimpleNamespace(metadata={"source_id": source_id, "chunk_id": "chunk-a"})


class ApiTests(unittest.TestCase):
    def setUp(self):
        session_store.clear()
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        session_store.clear()

    def test_health_and_session_cookie(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("copilot_session_id", response.cookies)

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
    def test_chat_returns_chart_url_and_preserves_history(self, process_user_message):
        process_user_message.return_value = {
            "content": "分析完成",
            "chart": b"png-bytes",
            "rag_debug": {"stage": "done"},
            "intents": ["data_agent"],
        }

        response = self.client.post(
            "/api/chat",
            json={
                "message": "分析销售额",
                "history": [{"role": "user", "content": "上一轮"}],
            },
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
            {"role": "user", "content": "上一轮"},
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
            json={"message": "你好", "history": []},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(os.environ.get("DASHSCOPE_API_KEY"), original_key)

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
            json={"conversation_id": "conversation-a", "message": "A1", "history": []},
        )
        self.client.post(
            "/api/chat",
            json={"conversation_id": "conversation-b", "message": "B1", "history": []},
        )
        self.client.post(
            "/api/chat",
            json={
                "conversation_id": "conversation-a",
                "message": "A2",
                "history": [
                    {"role": "user", "content": "A1"},
                    {"role": "assistant", "content": "ok"},
                ],
            },
        )

        self.assertEqual(seen_last_intents, [[], [], ["rag_qa"]])

    def test_missing_source_returns_404(self):
        response = self.client.delete("/api/sources/not-found")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "资料不存在")


if __name__ == "__main__":
    unittest.main()
