import unittest

from app.capabilities.rag import _display_page


class RagMetadataTests(unittest.TestCase):
    def test_converts_zero_based_pymupdf_page(self):
        self.assertEqual(_display_page({"page": 0}), 1)
        self.assertEqual(_display_page({"page": 4}), 5)

    def test_keeps_fallback_page_number(self):
        self.assertEqual(_display_page({"page_number": 3}), 3)


if __name__ == "__main__":
    unittest.main()
