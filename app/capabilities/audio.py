"""短音频同步转写能力。"""

import base64
import json
import os
from typing import Any, Dict, List

import httpx

from app.config import Config


def _parse_response_payloads(response: httpx.Response) -> List[Dict[str, Any]]:
    content_type = response.headers.get("content-type", "").lower()
    if "text/event-stream" not in content_type and not response.text.lstrip().startswith("id:"):
        payload = response.json()
        return [payload] if isinstance(payload, dict) else []

    payloads = []
    for line in response.text.splitlines():
        if not line.startswith("data:"):
            continue
        try:
            payload = json.loads(line[5:].strip())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads


def _normalize_text(text: str) -> str:
    return "".join(text.split())


def _extract_transcription(payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    segments_by_id: Dict[int, Dict[str, Any]] = {}
    full_text = ""
    duration_seconds = 0.0

    for payload in payloads:
        if payload.get("code") and not payload.get("output"):
            raise ValueError(str(payload.get("message") or payload["code"]))

        output = payload.get("output") or {}
        current_text = str(output.get("text") or "").strip()
        if current_text:
            full_text = current_text

        usage = payload.get("usage") or {}
        try:
            duration_seconds = max(duration_seconds, float(usage.get("duration") or 0))
        except (TypeError, ValueError):
            pass

        sentence = output.get("sentence") or {}
        if not sentence.get("sentence_end"):
            continue
        text = str(sentence.get("text") or "").strip()
        if not text:
            continue
        try:
            sentence_id = int(sentence.get("sentence_id") or len(segments_by_id) + 1)
            begin_time = float(sentence.get("begin_time") or 0) / 1000
            end_time = float(sentence.get("end_time") or 0) / 1000
        except (TypeError, ValueError):
            continue
        segments_by_id[sentence_id] = {
            "text": text,
            "start_seconds": max(0.0, begin_time),
            "end_seconds": max(begin_time, end_time),
        }

    segments = sorted(
        segments_by_id.values(),
        key=lambda value: (value["start_seconds"], value["end_seconds"]),
    )
    if segments:
        duration_seconds = max(
            duration_seconds,
            max(segment["end_seconds"] for segment in segments),
        )

    combined_text = "".join(segment["text"] for segment in segments)
    # 非流式响应可能只返回最后一句的时间戳，此时保留完整转写并使用整段时长。
    if full_text and _normalize_text(full_text) != _normalize_text(combined_text):
        segments = [{
            "text": full_text,
            "start_seconds": 0.0,
            "end_seconds": duration_seconds,
        }]
    elif not segments and full_text:
        segments = [{
            "text": full_text,
            "start_seconds": 0.0,
            "end_seconds": duration_seconds,
        }]

    if not segments:
        raise ValueError("音频中未识别到可检索文字")
    return {
        "text": full_text or combined_text,
        "segments": segments,
        "duration_seconds": duration_seconds,
    }


def transcribe_audio(
    audio_bytes: bytes,
    media_type: str,
    audio_format: str,
    *,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> Dict[str, Any]:
    """使用 DashScope 的同步 ASR 接口转写 Base64 音频。"""
    active_api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
    if not active_api_key:
        raise ValueError("缺少 DashScope API Key")

    encoded = base64.b64encode(audio_bytes).decode("ascii")
    payload = {
        "model": Config.ASR_MODEL,
        "input": {
            "messages": [{
                "role": "user",
                "content": [{
                    "type": "input_audio",
                    "input_audio": {
                        "data": f"data:{media_type};base64,{encoded}",
                    },
                }],
            }],
        },
        "parameters": {"format": audio_format},
    }
    headers = {
        "Authorization": f"Bearer {active_api_key}",
        "Content-Type": "application/json",
        "X-DashScope-SSE": "enable",
    }

    owns_client = client is None
    active_client = client or httpx.Client(timeout=Config.ASR_TIMEOUT_SECONDS)
    try:
        response = active_client.post(
            Config.ASR_ENDPOINT,
            headers=headers,
            json=payload,
            timeout=Config.ASR_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return _extract_transcription(_parse_response_payloads(response))
    except httpx.HTTPError as exc:
        raise ValueError(f"音频转写请求失败：{exc}") from exc
    finally:
        if owns_client:
            active_client.close()
