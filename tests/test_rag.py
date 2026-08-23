import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from app.capabilities.rag import _display_page, _split_structured_documents, process_pdf
from app.config import Config


class RagMetadataTests(unittest.TestCase):
    def test_converts_zero_based_pymupdf_page(self):
        self.assertEqual(_display_page({"page": 0}), 1)
        self.assertEqual(_display_page({"page": 4}), 5)

    def test_keeps_fallback_page_number(self):
        self.assertEqual(_display_page({"page_number": 3}), 3)

    @patch("app.capabilities.rag.PyMuPDFLoader")
    def test_rejects_pdf_without_extractable_text(self, loader_class):
        loader_class.return_value.load.return_value = []

        with self.assertRaisesRegex(ValueError, "未提取到可检索文本"):
            process_pdf(b"%PDF-empty", source_name="empty.pdf")

    @patch("app.capabilities.rag.PyMuPDFLoader")
    def test_adds_source_metadata_to_every_chunk(self, loader_class):
        loader_class.return_value.load.return_value = [
            Document(page_content="第一章 年假\n员工年假十天。", metadata={"page": 0})
        ]

        chunks = process_pdf(
            b"%PDF-source",
            source_name="员工手册.pdf",
            source_id="source-handbook",
        )

        self.assertTrue(chunks)
        self.assertTrue(
            all(chunk.metadata["source_id"] == "source-handbook" for chunk in chunks)
        )
        self.assertTrue(
            all(chunk.metadata["source"] == "员工手册.pdf" for chunk in chunks)
        )


class StructuredChunkTests(unittest.TestCase):
    def test_preserves_section_title_in_every_child_chunk(self):
        document = Document(
            page_content="第一章 总则\n" + "适用范围说明。" * 30 + "\n第二章 年假\n员工年假十天。",
            metadata={"page": 0},
        )

        with patch.object(Config, "CHUNK_SIZE", 80), patch.object(Config, "CHUNK_OVERLAP", 10):
            chunks = _split_structured_documents([document])

        first_section_chunks = [
            chunk for chunk in chunks if chunk.metadata.get("section_title") == "第一章 总则"
        ]
        self.assertGreater(len(first_section_chunks), 1)
        self.assertTrue(
            all(chunk.page_content.startswith("第一章 总则") for chunk in first_section_chunks)
        )
        self.assertEqual(chunks[-1].metadata["section_title"], "第二章 年假")
        self.assertIn("员工年假十天", chunks[-1].page_content)


if __name__ == "__main__":
    unittest.main()
