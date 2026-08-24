import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.knowledge_base import add_source, ensure_indexes, remove_source
from app.models import KnowledgeSource
from app.source_utils import document_content
from app.state import _empty_uploaded_files


def _chunk(source_id, chunk_id, source="测试资料"):
    return SimpleNamespace(
        page_content=chunk_id,
        metadata={
            "source_id": source_id,
            "source": source,
            "modality": "pdf",
            "chunk_id": chunk_id,
        },
    )


class KnowledgeBaseTests(unittest.TestCase):
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

    @patch("app.knowledge_base._build_keyword_index")
    @patch("app.knowledge_base._build_vector_store")
    def test_builds_source_aware_indexes_only_once(
        self,
        build_vector_store,
        build_keyword_index,
    ):
        files = _empty_uploaded_files()
        files["knowledge_chunks"] = [
            _chunk("source-a", "员工年假十天。", source="员工手册.pdf")
        ]
        store = Mock()
        keyword_index = Mock()
        build_vector_store.return_value = store
        build_keyword_index.return_value = keyword_index

        first = ensure_indexes(files)
        second = ensure_indexes(files)

        indexed_document = build_vector_store.call_args.args[0][0]
        self.assertIn("员工手册.pdf", indexed_document.page_content)
        self.assertEqual(document_content(indexed_document), "员工年假十天。")
        build_vector_store.assert_called_once()
        build_keyword_index.assert_called_once()
        self.assertEqual(first, (store, keyword_index))
        self.assertEqual(second, first)


if __name__ == "__main__":
    unittest.main()
