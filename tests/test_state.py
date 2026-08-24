import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from app.models import KnowledgeSource
from app.state import _empty_uploaded_files, add_source, remove_source


def _chunk(source_id, chunk_id):
    return SimpleNamespace(
        page_content=chunk_id,
        metadata={"source_id": source_id, "chunk_id": chunk_id},
    )


class KnowledgeSourceStateTests(unittest.TestCase):
    def test_keeps_chunks_from_multiple_modalities(self):
        files = _empty_uploaded_files()
        first = KnowledgeSource(
            source_id="source-a",
            name="A.pdf",
            modality="pdf",
            chunk_count=1,
        )
        second = KnowledgeSource(
            source_id="source-b",
            name="会议纪要",
            modality="text",
            chunk_count=1,
        )

        add_source(files, first, [_chunk("source-a", "a-1")])
        add_source(files, second, [_chunk("source-b", "b-1")])

        self.assertEqual(list(files["knowledge_sources"]), ["source-a", "source-b"])
        self.assertEqual(
            [chunk.metadata["chunk_id"] for chunk in files["knowledge_chunks"]],
            ["a-1", "b-1"],
        )

    def test_removes_only_selected_source_and_invalidates_indexes(self):
        files = _empty_uploaded_files()
        first = KnowledgeSource(
            source_id="source-a",
            name="A.pdf",
            modality="pdf",
            chunk_count=1,
        )
        second = KnowledgeSource(
            source_id="source-b",
            name="B.pdf",
            modality="pdf",
            chunk_count=1,
        )
        add_source(files, first, [_chunk("source-a", "a-1")])
        add_source(files, second, [_chunk("source-b", "b-1")])
        store = Mock()
        files["knowledge_store"] = store
        files["knowledge_keyword_index"] = Mock()

        removed = remove_source(files, "source-a")

        self.assertTrue(removed)
        self.assertEqual(list(files["knowledge_sources"]), ["source-b"])
        self.assertEqual(
            [chunk.metadata["chunk_id"] for chunk in files["knowledge_chunks"]],
            ["b-1"],
        )
        store.delete_collection.assert_called_once_with()
        self.assertIsNone(files["knowledge_store"])
        self.assertIsNone(files["knowledge_keyword_index"])


if __name__ == "__main__":
    unittest.main()
