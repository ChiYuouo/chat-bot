import socket
import unittest
from unittest.mock import patch

import httpx

from app.ingestion import (
    URL_RESPONSE_MAX_BYTES,
    _fetch_url,
    _validate_fetch_url,
    ingest_text,
    ingest_url,
)


class TextSourceTests(unittest.TestCase):
    def test_ingests_text_with_shared_source_metadata(self):
        source, chunks = ingest_text("项目会议纪要", "第一章 决议\n项目将在九月上线。")

        self.assertEqual(source.modality, "text")
        self.assertEqual(source.chunk_count, len(chunks))
        self.assertTrue(chunks)
        self.assertTrue(
            all(chunk.metadata["source_id"] == source.source_id for chunk in chunks)
        )
        self.assertTrue(all(chunk.metadata["modality"] == "text" for chunk in chunks))
        self.assertTrue(all("display_page" not in chunk.metadata for chunk in chunks))

    def test_rejects_empty_text(self):
        with self.assertRaisesRegex(ValueError, "正文不能为空"):
            ingest_text("空资料", "   ")


class UrlSourceTests(unittest.TestCase):
    @patch("app.ingestion.socket.getaddrinfo")
    def test_blocks_private_network_addresses(self, getaddrinfo):
        getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))
        ]

        with self.assertRaisesRegex(ValueError, "内网地址"):
            _validate_fetch_url("http://internal.example/path")

    @patch("app.ingestion._validate_fetch_url")
    def test_extracts_html_and_keeps_final_url(self, validate_url):
        def handler(request):
            if request.url.host == "example.com":
                return httpx.Response(
                    302,
                    headers={"location": "https://www.example.com/article"},
                )
            return httpx.Response(
                200,
                headers={"content-type": "text/html; charset=utf-8"},
                text=(
                    "<html><head><title>公司制度</title><script>ignore()</script></head>"
                    "<body><nav>导航</nav><main>员工年假为十天。</main></body></html>"
                ),
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            source, chunks = ingest_url("https://example.com/start", client=client)

        self.assertEqual(source.name, "公司制度")
        self.assertEqual(source.modality, "url")
        self.assertEqual(source.url, "https://www.example.com/article")
        self.assertIn("员工年假为十天", chunks[0].page_content)
        self.assertNotIn("ignore", chunks[0].page_content)
        self.assertNotIn("导航", chunks[0].page_content)
        self.assertEqual(validate_url.call_count, 2)

    @patch("app.ingestion._validate_fetch_url")
    def test_rejects_oversized_responses(self, _validate_url):
        def handler(_request):
            return httpx.Response(
                200,
                headers={"content-type": "text/plain"},
                content=b"x" * (URL_RESPONSE_MAX_BYTES + 1),
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ValueError, "超过 2 MB"):
                _fetch_url("https://example.com/large", client)

    @patch("app.ingestion._validate_fetch_url")
    def test_rejects_non_text_content(self, _validate_url):
        def handler(_request):
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"%PDF",
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ValueError, "不支持网页内容类型"):
                _fetch_url("https://example.com/file", client)


if __name__ == "__main__":
    unittest.main()
