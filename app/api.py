"""React 前端使用的 FastAPI 适配层。"""

from __future__ import annotations

import json
import os
import re
import secrets
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from queue import Queue
from typing import Any, Iterator, Literal

import pandas as pd
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from app.config import Config
from app.ingestion import (
    _detect_image_media_type,
    ingest_audio,
    ingest_image,
    ingest_pdf,
    ingest_text_file,
    ingest_url,
)
from app.knowledge_base import add_source, remove_source
from app.models import KnowledgeSource
from app.router import process_user_message
from app.state import (
    _empty_uploaded_files,
    clear_uploaded_files,
    remove_uploaded_image_temp_file,
)


SESSION_COOKIE_NAME = "copilot_session_id"
SESSION_MAX_AGE_SECONDS = 6 * 60 * 60
MAX_API_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_STORED_CHARTS = 10
_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
_CREDENTIAL_LOCK = threading.RLock()
UploadKind = Literal["pdf", "text", "image", "audio", "csv", "vision"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    conversation_id: str | None = Field(default=None, max_length=128)
    history: list[ChatMessage] = Field(default_factory=list, max_length=100)


class UrlSourceRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2_048)
    title: str | None = Field(default=None, max_length=160)


@dataclass(frozen=True)
class RequestCredentials:
    api_key: str | None = None
    model: str | None = None


@dataclass
class ApiSession:
    uploaded_files: dict[str, Any] = field(default_factory=_empty_uploaded_files)
    messages: list[dict[str, Any]] = field(default_factory=list)
    last_intents: list[str] = field(default_factory=list)
    conversation_intents: dict[str, list[str]] = field(default_factory=dict)
    charts: dict[str, bytes] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)
    lock: threading.RLock = field(default_factory=threading.RLock)


class SessionStore:
    """进程内会话存储，适合本地演示和单进程运行。"""

    def __init__(self) -> None:
        self._sessions: dict[str, ApiSession] = {}
        self._lock = threading.RLock()

    def get_or_create(self, session_id: str | None) -> tuple[str, ApiSession, bool]:
        normalized = session_id if session_id and len(session_id) <= 128 else None
        with self._lock:
            self._discard_expired_locked()
            if normalized and normalized in self._sessions:
                session = self._sessions[normalized]
                session.updated_at = time.time()
                return normalized, session, False

            new_id = secrets.token_urlsafe(24)
            session = ApiSession()
            self._sessions[new_id] = session
            return new_id, session, True

    def get(self, session_id: str | None) -> ApiSession | None:
        if not session_id:
            return None
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.updated_at = time.time()
            return session

    def clear(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            with session.lock:
                clear_uploaded_files(session.uploaded_files)

    def _discard_expired_locked(self) -> None:
        cutoff = time.time() - SESSION_MAX_AGE_SECONDS
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session.updated_at < cutoff
        ]
        for session_id in expired_ids:
            session = self._sessions.pop(session_id)
            with session.lock:
                clear_uploaded_files(session.uploaded_files)


session_store = SessionStore()


def _cors_origins() -> list[str]:
    configured = os.getenv("COPILOT_CORS_ORIGINS", "")
    if configured.strip():
        return [origin.strip() for origin in configured.split(",") if origin.strip()]
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


app = FastAPI(title="Enterprise AI Copilot API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-DashScope-Api-Key", "X-Model"],
)


@app.middleware("http")
async def bind_session(request: Request, call_next):
    session_id, session, created = session_store.get_or_create(
        request.cookies.get(SESSION_COOKIE_NAME)
    )
    request.state.api_session = session
    response = await call_next(request)
    if created:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_id,
            max_age=SESSION_MAX_AGE_SECONDS,
            httponly=True,
            samesite="lax",
        )
    return response


def get_session(request: Request) -> ApiSession:
    return request.state.api_session


def get_credentials(
    x_dashscope_api_key: str | None = Header(default=None),
    x_model: str | None = Header(default=None),
) -> RequestCredentials:
    api_key = x_dashscope_api_key.strip() if x_dashscope_api_key else None
    model = x_model.strip() if x_model else None
    if model and not _MODEL_NAME_RE.fullmatch(model):
        raise HTTPException(status_code=400, detail="模型名称格式无效")
    return RequestCredentials(api_key=api_key, model=model)


@contextmanager
def request_credentials(credentials: RequestCredentials) -> Iterator[None]:
    """串行设置现有模型代码读取的进程级配置，并在请求后恢复。"""
    with _CREDENTIAL_LOCK:
        original_key = os.environ.get("DASHSCOPE_API_KEY")
        original_model = Config.LLM_MODEL
        if credentials.api_key:
            os.environ["DASHSCOPE_API_KEY"] = credentials.api_key
        if credentials.model:
            Config.LLM_MODEL = credentials.model
        try:
            yield
        finally:
            Config.LLM_MODEL = original_model
            if original_key is None:
                os.environ.pop("DASHSCOPE_API_KEY", None)
            else:
                os.environ["DASHSCOPE_API_KEY"] = original_key


def _existing_source_hashes(files: dict[str, Any]) -> set[str]:
    return {
        content_hash
        for source in (files.get("knowledge_sources") or {}).values()
        if (content_hash := getattr(source, "content_hash", None))
    }


def _serialize_source(source: KnowledgeSource) -> dict[str, Any]:
    return source.model_dump(mode="json")


def _session_sources(session: ApiSession) -> list[dict[str, Any]]:
    files = session.uploaded_files
    sources: list[dict[str, Any]] = []
    if files.get("csv_df") is not None:
        sources.append({
            "id": "csv",
            "name": files.get("csv_name") or "data.csv",
            "kind": "csv",
            "meta": f"{len(files['csv_df']):,} 行",
            "status": "ready",
        })
    sources.extend(
        _serialize_source(source)
        for source in (files.get("knowledge_sources") or {}).values()
    )
    if files.get("image_path"):
        sources.append({
            "id": "vision",
            "name": files.get("image_name") or "image.png",
            "kind": "vision",
            "meta": "临时识图",
            "status": "ready",
        })
    return sources


def _read_upload(upload: UploadFile) -> tuple[str, bytes]:
    name = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not name:
        raise HTTPException(status_code=400, detail="文件名不能为空")
    data = upload.file.read(MAX_API_UPLOAD_BYTES + 1)
    if len(data) > MAX_API_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="上传文件不能超过 50 MB")
    if not data:
        raise HTTPException(status_code=400, detail="文件内容不能为空")
    return name, data


def _store_chart(session: ApiSession, chart: bytes) -> str:
    chart_id = uuid.uuid4().hex
    session.charts[chart_id] = chart
    while len(session.charts) > MAX_STORED_CHARTS:
        session.charts.pop(next(iter(session.charts)))
    return chart_id


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat")
def chat(
    payload: ChatRequest,
    request: Request,
    session: ApiSession = Depends(get_session),
    credentials: RequestCredentials = Depends(get_credentials),
) -> dict[str, Any]:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    history = [item.model_dump() for item in payload.history]
    conversation_id = payload.conversation_id or "default"
    with session.lock, request_credentials(credentials):
        if not history:
            session.conversation_intents.pop(conversation_id, None)
        session.messages = history
        previous_intents = session.conversation_intents.get(conversation_id, [])
        result = process_user_message(
            message,
            uploaded_files=session.uploaded_files,
            messages=session.messages,
            last_intents=previous_intents,
        )
        session.last_intents = list(result.get("intents") or [])
        session.conversation_intents[conversation_id] = session.last_intents
        session.messages.extend([
            {"role": "user", "content": message},
            {"role": "assistant", "content": result["content"]},
        ])

        chart_url = None
        if isinstance(result.get("chart"), bytes):
            chart_id = _store_chart(session, result["chart"])
            chart_url = str(request.url_for("get_chart", chart_id=chart_id))

        return {
            "content": result["content"],
            "chart_url": chart_url,
            "rag_debug": result.get("rag_debug"),
        }


def _ndjson_event(event: dict[str, Any]) -> bytes:
    return (json.dumps(event, ensure_ascii=False, default=str) + "\n").encode("utf-8")


@app.post("/api/chat/stream")
def chat_stream(
    payload: ChatRequest,
    request: Request,
    session: ApiSession = Depends(get_session),
    credentials: RequestCredentials = Depends(get_credentials),
) -> StreamingResponse:
    """以 NDJSON 事件流返回回答；普通问答的模型内容会逐块发送。"""
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    history = [item.model_dump() for item in payload.history]
    conversation_id = payload.conversation_id or "default"

    def stream_events() -> Iterator[bytes]:
        event_queue: Queue[Any] = Queue()
        finished = object()

        def emit_delta(content: str) -> None:
            event_queue.put({"type": "delta", "content": content})

        def emit_status(content: str) -> None:
            event_queue.put({"type": "status", "content": content})

        def produce() -> None:
            try:
                with session.lock, request_credentials(credentials):
                    if not history:
                        session.conversation_intents.pop(conversation_id, None)
                    session.messages = history
                    previous_intents = session.conversation_intents.get(
                        conversation_id, []
                    )
                    result = process_user_message(
                        message,
                        uploaded_files=session.uploaded_files,
                        messages=session.messages,
                        last_intents=previous_intents,
                        stream_callback=emit_delta,
                        status_callback=emit_status,
                    )
                    session.last_intents = list(result.get("intents") or [])
                    session.conversation_intents[conversation_id] = session.last_intents
                    session.messages.extend([
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": result["content"]},
                    ])

                    chart_url = None
                    if isinstance(result.get("chart"), bytes):
                        chart_id = _store_chart(session, result["chart"])
                        chart_url = str(
                            request.url_for("get_chart", chart_id=chart_id)
                        )

                    event_queue.put({
                        "type": "done",
                        "content": result["content"],
                        "chart_url": chart_url,
                        "rag_debug": result.get("rag_debug"),
                    })
            except Exception as exc:
                event_queue.put({
                    "type": "error",
                    "message": f"生成回答失败：{exc}",
                })
            finally:
                event_queue.put(finished)

        threading.Thread(target=produce, daemon=True).start()
        yield _ndjson_event({"type": "status", "content": "正在识别问题类型..."})
        while True:
            event = event_queue.get()
            if event is finished:
                break
            yield _ndjson_event(event)

    return StreamingResponse(
        stream_events(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/sources")
def list_sources(session: ApiSession = Depends(get_session)) -> dict[str, Any]:
    with session.lock:
        return {"sources": _session_sources(session)}


@app.post("/api/sources")
def upload_source(
    kind: UploadKind = Form(...),
    file: UploadFile = File(...),
    session: ApiSession = Depends(get_session),
    credentials: RequestCredentials = Depends(get_credentials),
) -> dict[str, Any]:
    name, data = _read_upload(file)
    files = session.uploaded_files
    try:
        with session.lock, request_credentials(credentials):
            if kind == "pdf":
                source, chunks = ingest_pdf(data, source_name=name)
            elif kind == "text":
                source, chunks = ingest_text_file(
                    data,
                    source_name=name,
                    existing_content_hashes=_existing_source_hashes(files),
                )
            elif kind == "image":
                source, chunks = ingest_image(
                    data,
                    source_name=name,
                    existing_content_hashes=_existing_source_hashes(files),
                )
            elif kind == "audio":
                source, chunks = ingest_audio(
                    data,
                    source_name=name,
                    existing_content_hashes=_existing_source_hashes(files),
                )
            elif kind == "csv":
                if Path(name).suffix.lower() != ".csv":
                    raise ValueError("只支持 CSV 文件")
                dataframe = pd.read_csv(BytesIO(data))
                files["csv_name"] = name
                files["csv_df"] = dataframe
                return {
                    "id": "csv",
                    "name": name,
                    "kind": "csv",
                    "meta": f"{len(dataframe):,} 行",
                    "status": "ready",
                }
            else:
                media_type = _detect_image_media_type(data)
                suffix = ".png" if media_type == "image/png" else ".jpg"
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(data)
                    new_path = tmp.name
                remove_uploaded_image_temp_file(files)
                files["image_name"] = name
                files["image_path"] = new_path
                files["image_bytes"] = data
                return {
                    "id": "vision",
                    "name": name,
                    "kind": "vision",
                    "meta": "临时识图",
                    "status": "ready",
                }

            add_source(files, source, chunks)
            return _serialize_source(source)
    except HTTPException:
        raise
    except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"资料处理失败：{exc}") from exc


@app.post("/api/sources/url")
def add_url_source(
    payload: UrlSourceRequest,
    session: ApiSession = Depends(get_session),
    credentials: RequestCredentials = Depends(get_credentials),
) -> dict[str, Any]:
    try:
        with session.lock, request_credentials(credentials):
            source, chunks = ingest_url(payload.url, payload.title or "")
            add_source(session.uploaded_files, source, chunks)
            return _serialize_source(source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"网页资料处理失败：{exc}") from exc


@app.delete("/api/sources/{source_id}", status_code=204)
def delete_source(
    source_id: str,
    session: ApiSession = Depends(get_session),
) -> None:
    with session.lock:
        files = session.uploaded_files
        if source_id == "csv" and files.get("csv_df") is not None:
            files["csv_name"] = None
            files["csv_df"] = None
            return
        if source_id == "vision" and files.get("image_path"):
            remove_uploaded_image_temp_file(files)
            files["image_name"] = None
            files["image_path"] = None
            files["image_bytes"] = None
            return
        if remove_source(files, source_id):
            session.last_intents = []
            session.conversation_intents.clear()
            return
        raise HTTPException(status_code=404, detail="资料不存在")


@app.delete("/api/sources", status_code=204)
def delete_all_sources(session: ApiSession = Depends(get_session)) -> None:
    with session.lock:
        clear_uploaded_files(session.uploaded_files)
        session.last_intents = []
        session.conversation_intents.clear()
        session.charts.clear()


@app.get("/api/assets/{chart_id}", name="get_chart")
def get_chart(chart_id: str, request: Request) -> Response:
    session = session_store.get(request.cookies.get(SESSION_COOKIE_NAME))
    if session is None:
        raise HTTPException(status_code=404, detail="图表不存在")
    with session.lock:
        chart = session.charts.get(chart_id)
        if chart is None:
            raise HTTPException(status_code=404, detail="图表不存在")
        return Response(content=chart, media_type="image/png")
