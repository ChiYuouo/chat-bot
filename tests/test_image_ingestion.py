import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.capabilities.vision import extract_image_content
from app.config import Config
from app.ingestion import ingest_image
from app.source_utils import build_retrieval_documents, source_location


_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"test-image"


class ImageSourceTests(unittest.TestCase):
    @patch("app.ingestion.extract_image_content")
    def test_ingests_image_as_shared_knowledge_chunks(self, extract_image_content):
        extract_image_content.return_value = {
            "text": "图片描述\n季度销售额同比增长 20%。\n\n图片文字\n2026 Q2",
            "contract": {},
        }

        source, chunks = ingest_image(_PNG_BYTES, "季度报告.png")

        self.assertEqual(source.modality, "image")
        self.assertEqual(source.chunk_count, len(chunks))
        self.assertTrue(chunks)
        self.assertTrue(
            all(chunk.metadata["source_id"] == source.source_id for chunk in chunks)
        )
        self.assertTrue(all(chunk.metadata["modality"] == "image" for chunk in chunks))
        self.assertTrue(all(chunk.metadata["media_type"] == "image/png" for chunk in chunks))
        self.assertIn("季度销售额", chunks[0].page_content)

        retrieval_document = build_retrieval_documents(chunks)[0]
        self.assertIn("资料类型：图片", retrieval_document.page_content)

    @patch("app.ingestion.extract_image_content")
    def test_rejects_invalid_image_before_model_call(self, extract_image_content):
        with self.assertRaisesRegex(ValueError, "只支持有效的"):
            ingest_image(b"not-an-image", "伪造图片.png")

        extract_image_content.assert_not_called()

    @patch("app.ingestion.extract_image_content")
    def test_rejects_oversized_image_before_model_call(self, extract_image_content):
        with patch.object(Config, "IMAGE_SOURCE_MAX_BYTES", 8):
            with self.assertRaisesRegex(ValueError, "不能超过"):
                ingest_image(_PNG_BYTES, "large.png")

        extract_image_content.assert_not_called()

    def test_removes_temporary_file_when_extraction_fails(self):
        observed_path = None

        def fail_extraction(image_path):
            nonlocal observed_path
            observed_path = image_path
            self.assertTrue(Path(image_path).is_file())
            raise RuntimeError("model failed")

        with patch("app.ingestion.extract_image_content", side_effect=fail_extraction):
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                ingest_image(_PNG_BYTES, "failure.png")

        self.assertIsNotNone(observed_path)
        self.assertFalse(Path(observed_path).exists())

    def test_formats_image_source_location(self):
        self.assertEqual(
            source_location({"source": "组织架构.png", "modality": "image"}),
            "组织架构.png，图片资料",
        )


class ImageExtractionTests(unittest.TestCase):
    @patch("app.capabilities.vision.create_chat_model")
    def test_converts_model_contract_to_retrieval_text(self, create_chat_model):
        model = create_chat_model.return_value
        model.invoke.return_value = SimpleNamespace(
            content='{"ocr_text":"员工年假 10 天","description":"制度截图",'
            '"entities":["人力资源部"]}'
        )

        result = extract_image_content("knowledge.png")

        self.assertIn("制度截图", result["text"])
        self.assertIn("员工年假 10 天", result["text"])
        self.assertIn("人力资源部", result["text"])
        message = model.invoke.call_args.args[0][0]
        self.assertTrue(message.content[1]["image"].startswith("file://"))

    @patch("app.capabilities.vision.create_chat_model")
    def test_rejects_empty_extraction(self, create_chat_model):
        create_chat_model.return_value.invoke.return_value = SimpleNamespace(
            content='{"ocr_text":"","description":"","entities":[]}'
        )

        with self.assertRaisesRegex(ValueError, "未提取到"):
            extract_image_content("empty.png")


if __name__ == "__main__":
    unittest.main()
