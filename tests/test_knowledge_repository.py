import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document

from app.models import KnowledgeSource
from app.repositories.conversations import SQLiteConversationRepository
from app.repositories.knowledge import SQLiteKnowledgeRepository


class SQLiteKnowledgeRepositoryTests(unittest.TestCase):
    def test_saves_restores_and_isolates_scope_data(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "copilot.sqlite3"
            with patch.dict(os.environ, {"COPILOT_DATABASE_PATH": str(database)}):
                repository = SQLiteKnowledgeRepository()
                source = KnowledgeSource(
                    source_id="source-a",
                    name="员工手册.md",
                    modality="text",
                    chunk_count=1,
                )
                repository.save_source(
                    "user-a-kb",
                    source,
                    [Document(
                        page_content="年假为十天。",
                        metadata={"chunk_id": "chunk-a", "source_id": "source-a"},
                    )],
                )

                # 新建仓储对象模拟后端进程重启后的恢复。
                restored = SQLiteKnowledgeRepository()
                sources = restored.load_sources("user-a-kb")
                chunks = restored.load_chunks("user-a-kb")

                self.assertEqual(sources["source-a"].name, "员工手册.md")
                self.assertEqual(chunks[0].page_content, "年假为十天。")
                self.assertEqual(restored.load_sources("user-b-kb"), {})
                self.assertEqual(restored.load_chunks("user-b-kb"), [])

    def test_conversation_is_restored_only_from_its_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "copilot.sqlite3"
            with patch.dict(os.environ, {"COPILOT_DATABASE_PATH": str(database)}):
                repository = SQLiteConversationRepository()
                repository.save_conversation(
                    "user-a",
                    "conversation-a",
                    [{"role": "user", "content": "年假几天？"}],
                    ["rag_qa"],
                )

                restored = SQLiteConversationRepository().load_conversation(
                    "user-a", "conversation-a"
                )

                self.assertEqual(restored, ([{"role": "user", "content": "年假几天？"}], ["rag_qa"]))
                self.assertIsNone(
                    repository.load_conversation("user-b", "conversation-a")
                )
