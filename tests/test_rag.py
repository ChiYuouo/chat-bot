import unittest
from unittest.mock import patch

from app.capabilities.rag import _display_page, process_pdf


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


if __name__ == "__main__":
    unittest.main()
