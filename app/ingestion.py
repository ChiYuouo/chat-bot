"""PDF、文本和网页资料的解析与切分。"""

import hashlib
import ipaddress
import os
import re
import socket
import tempfile
import uuid
from html.parser import HTMLParser
from typing import Any, List
from urllib.parse import urljoin, urlparse

import httpx
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import Config
from app.models import KnowledgeSource, SourceModality
from app.source_utils import display_page


TEXT_SOURCE_MAX_CHARS = 200_000
URL_RESPONSE_MAX_BYTES = 2 * 1024 * 1024
URL_TEXT_MAX_CHARS = 120_000
URL_REDIRECT_LIMIT = 5
URL_TIMEOUT_SECONDS = 15
_ALLOWED_URL_CONTENT_TYPES = {
    "application/xhtml+xml",
    "text/html",
    "text/plain",
}
_SKIPPED_HTML_TAGS = {"footer", "header", "nav", "noscript", "script", "style"}
_STRUCTURE_HEADING_RE = re.compile(
    r"^\s*(?:"
    r"#{1,6}\s+\S+|"
    r"第[一二三四五六七八九十百千万零〇两\d]+[编章节条款]\s*.*|"
    r"[一二三四五六七八九十百]+、\s*\S+|"
    r"\d+(?:\.\d+)*[、.．)]\s*\S+"
    r")\s*$"
)


class _ReadableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: List[str] = []
        self.title_parts: List[str] = []
        self._skipped_tags: List[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        if tag in _SKIPPED_HTML_TAGS:
            self._skipped_tags.append(tag)
        elif tag == "title" and not self._skipped_tags:
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if self._skipped_tags and tag == self._skipped_tags[-1]:
            self._skipped_tags.pop()
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skipped_tags:
            return
        if self._in_title:
            self.title_parts.append(data)
        else:
            self.text_parts.append(data)


def _split_into_sections(document: Any) -> List[Document]:
    """按文本中的章节、条款和编号标题切成结构段。"""
    text = str(document.page_content).strip()
    if not text:
        return []

    sections: List[Document] = []
    current_lines: List[str] = []
    current_title: str | None = None

    def flush() -> None:
        if not current_lines:
            return
        content = "\n".join(current_lines).strip()
        if not content:
            return
        metadata = dict(document.metadata)
        if current_title:
            metadata["section_title"] = current_title
        sections.append(Document(page_content=content, metadata=metadata))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue
        if _STRUCTURE_HEADING_RE.match(line):
            flush()
            current_lines = [line]
            current_title = line
        else:
            current_lines.append(line)
    flush()
    return sections


def _split_structured_documents(documents: List[Any]) -> List[Document]:
    """先识别资料结构，再在每个结构段内部按长度切分。"""
    sections = [
        section
        for document in documents
        for section in _split_into_sections(document)
    ]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=Config.CHUNK_SIZE,
        chunk_overlap=Config.CHUNK_OVERLAP,
        is_separator_regex=True,
        keep_separator=True,
        separators=[
            r"\n{2,}",
            r"\n",
            r"(?<=。)",
            r"(?<=！)",
            r"(?<=？)",
            r"(?<=，)",
            r"\s+",
            "",
        ],
    )
    chunks = splitter.split_documents(sections)

    # 长章节拆分后重复标题，保证每个子块都能独立参与检索。
    for chunk in chunks:
        title = chunk.metadata.get("section_title")
        if title and not chunk.page_content.lstrip().startswith(str(title)):
            chunk.page_content = f"{title}\n{chunk.page_content}"
    return chunks


def _attach_source_metadata(
    chunks: List[Document],
    source_id: str,
    source_name: str,
    modality: SourceModality,
    url: str | None = None,
) -> None:
    for index, chunk in enumerate(chunks):
        page = display_page(chunk.metadata) if modality == "pdf" else None
        identity = f"{source_id}|{page}|{index}|{chunk.page_content}".encode("utf-8")
        chunk.metadata.update({
            "chunk_id": f"chunk-{hashlib.sha1(identity).hexdigest()[:12]}",
            "source_id": source_id,
            "source": source_name,
            "modality": modality,
        })
        if page is not None:
            chunk.metadata["display_page"] = page
        if url:
            chunk.metadata["url"] = url


def process_pdf(
    pdf_bytes: bytes,
    source_name: str = "uploaded.pdf",
    source_id: str | None = None,
) -> List[Document]:
    source_id = source_id or f"source-{uuid.uuid4().hex[:12]}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    try:
        documents = PyMuPDFLoader(tmp_path).load()
        chunks = _split_structured_documents(documents)
        if not chunks:
            raise ValueError("PDF 中未提取到可检索文本，请确认 PDF 包含文本内容")
        _attach_source_metadata(chunks, source_id, source_name, "pdf")
        return chunks
    finally:
        os.unlink(tmp_path)


def ingest_pdf(pdf_bytes: bytes, source_name: str) -> tuple[KnowledgeSource, List[Document]]:
    source_id = f"source-{uuid.uuid4().hex[:12]}"
    chunks = process_pdf(pdf_bytes, source_name=source_name, source_id=source_id)
    source = KnowledgeSource(
        source_id=source_id,
        name=source_name,
        modality="pdf",
        chunk_count=len(chunks),
    )
    return source, chunks


def _ingest_textual_source(
    title: str,
    text: str,
    modality: SourceModality,
    url: str | None = None,
) -> tuple[KnowledgeSource, List[Document]]:
    source_name = title.strip()
    content = text.strip()
    if not source_name:
        raise ValueError("资料标题不能为空")
    if not content:
        raise ValueError("资料正文不能为空")
    if len(content) > TEXT_SOURCE_MAX_CHARS:
        raise ValueError(f"资料正文不能超过 {TEXT_SOURCE_MAX_CHARS} 个字符")

    source_id = f"source-{uuid.uuid4().hex[:12]}"
    chunks = _split_structured_documents([Document(page_content=content, metadata={})])
    if not chunks:
        raise ValueError("资料正文中没有可检索文本")
    _attach_source_metadata(chunks, source_id, source_name, modality, url)
    source = KnowledgeSource(
        source_id=source_id,
        name=source_name,
        modality=modality,
        chunk_count=len(chunks),
        url=url,
    )
    return source, chunks


def ingest_text(title: str, text: str) -> tuple[KnowledgeSource, List[Document]]:
    return _ingest_textual_source(title, text, "text")


def _validate_fetch_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("只支持 HTTP 和 HTTPS 地址")
    if len(url) > 2_048:
        raise ValueError("URL 长度不能超过 2048 个字符")
    if parsed.username or parsed.password:
        raise ValueError("URL 不能包含用户名或密码")

    hostname = parsed.hostname.lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise ValueError("不允许访问本机或内网地址")

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"无法解析 URL 主机：{hostname}") from exc
    if not addresses:
        raise ValueError(f"无法解析 URL 主机：{hostname}")

    for address_info in addresses:
        address = ipaddress.ip_address(address_info[4][0].split("%", 1)[0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
            or address.is_unspecified
        ):
            raise ValueError("不允许访问本机或内网地址")


def _fetch_url(url: str, client: httpx.Client | None = None) -> tuple[str, str, str]:
    owns_client = client is None
    active_client = client or httpx.Client(
        timeout=URL_TIMEOUT_SECONDS,
        follow_redirects=False,
        headers={"User-Agent": "Enterprise-AI-Copilot/1.0"},
    )
    current_url = url
    try:
        for _ in range(URL_REDIRECT_LIMIT + 1):
            _validate_fetch_url(current_url)
            with active_client.stream("GET", current_url) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("网页返回了无效重定向")
                    current_url = urljoin(current_url, location)
                    continue

                response.raise_for_status()
                content_type = (
                    response.headers.get("content-type", "")
                    .split(";", 1)[0]
                    .strip()
                    .lower()
                )
                if content_type not in _ALLOWED_URL_CONTENT_TYPES:
                    raise ValueError(f"不支持网页内容类型：{content_type or '未知'}")

                body = bytearray()
                for block in response.iter_bytes():
                    body.extend(block)
                    if len(body) > URL_RESPONSE_MAX_BYTES:
                        raise ValueError("网页内容超过 2 MB 限制")
                encoding = response.encoding or "utf-8"
                return current_url, bytes(body).decode(encoding, errors="replace"), content_type
        raise ValueError("网页重定向次数过多")
    except httpx.HTTPError as exc:
        raise ValueError(f"网页请求失败：{exc}") from exc
    finally:
        if owns_client:
            active_client.close()


def _extract_web_text(raw_text: str, content_type: str) -> tuple[str, str | None]:
    if content_type == "text/plain":
        return " ".join(raw_text.split()), None

    parser = _ReadableHtmlParser()
    parser.feed(raw_text)
    text = " ".join(" ".join(parser.text_parts).split())
    title = " ".join(" ".join(parser.title_parts).split()) or None
    return text, title


def ingest_url(
    url: str,
    title: str = "",
    client: httpx.Client | None = None,
) -> tuple[KnowledgeSource, List[Document]]:
    final_url, raw_text, content_type = _fetch_url(url.strip(), client)
    text, page_title = _extract_web_text(raw_text, content_type)
    if not text:
        raise ValueError("网页中没有提取到可检索正文")
    source_name = title.strip() or page_title or urlparse(final_url).hostname or "网页资料"
    return _ingest_textual_source(
        source_name[:160],
        text[:URL_TEXT_MAX_CHARS],
        "url",
        final_url,
    )
