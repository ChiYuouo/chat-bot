import json
import unittest
import wave
from io import BytesIO
from unittest.mock import patch

import httpx

from app.capabilities.audio import transcribe_audio
from app.config import Config
from app.ingestion import ingest_audio
from app.source_utils import build_retrieval_documents, source_location


def _make_wav_bytes(duration_seconds=1.0, sample_rate=8_000):
    output = BytesIO()
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * frame_count)
    return output.getvalue()


_WAV_BYTES = _make_wav_bytes()
_TRANSCRIPTION = {
    "text": "项目九月上线。预算为十万元。",
    "duration_seconds": 1.0,
    "segments": [
        {"text": "项目九月上线。", "start_seconds": 0.0, "end_seconds": 0.5},
        {"text": "预算为十万元。", "start_seconds": 0.5, "end_seconds": 1.0},
    ],
}


class AudioSourceTests(unittest.TestCase):
    @patch("app.ingestion.transcribe_audio", return_value=_TRANSCRIPTION)
    def test_ingests_timestamped_audio_chunks(self, transcribe_audio):
        source, chunks = ingest_audio(_WAV_BYTES, "项目会议.wav")

        self.assertEqual(source.modality, "audio")
        self.assertAlmostEqual(source.duration_seconds, 1.0, places=1)
        self.assertEqual(source.chunk_count, len(chunks))
        self.assertTrue(chunks)
        self.assertTrue(all(chunk.metadata["modality"] == "audio" for chunk in chunks))
        self.assertTrue(all(chunk.metadata["content_hash"] == source.content_hash for chunk in chunks))
        self.assertEqual(chunks[0].metadata["start_seconds"], 0.0)
        self.assertEqual(chunks[0].metadata["end_seconds"], 0.5)
        self.assertEqual(
            source_location(chunks[0].metadata),
            "项目会议.wav，00:00–00:01",
        )

        retrieval_document = build_retrieval_documents(chunks)[0]
        self.assertIn("资料类型：音频", retrieval_document.page_content)
        transcribe_audio.assert_called_once_with(_WAV_BYTES, "audio/wav", "wav")

    @patch("app.ingestion.transcribe_audio")
    def test_rejects_invalid_audio_before_asr(self, transcribe_audio):
        with self.assertRaisesRegex(ValueError, "未损坏"):
            ingest_audio(b"not-audio", "伪造音频.wav")

        transcribe_audio.assert_not_called()

    @patch("app.ingestion.transcribe_audio")
    def test_rejects_audio_over_duration_limit(self, transcribe_audio):
        with patch.object(Config, "AUDIO_SOURCE_MAX_SECONDS", 0.5):
            with self.assertRaisesRegex(ValueError, "音频时长不能超过"):
                ingest_audio(_WAV_BYTES, "过长音频.wav")

        transcribe_audio.assert_not_called()

    @patch("app.ingestion.transcribe_audio", return_value=_TRANSCRIPTION)
    def test_rejects_duplicate_before_asr(self, transcribe_audio):
        source, _ = ingest_audio(_WAV_BYTES, "项目会议.wav")
        transcribe_audio.reset_mock()

        with self.assertRaisesRegex(ValueError, "已存在"):
            ingest_audio(
                _WAV_BYTES,
                "项目会议副本.wav",
                existing_content_hashes={source.content_hash},
            )

        transcribe_audio.assert_not_called()


class AudioTranscriptionTests(unittest.TestCase):
    def test_parses_non_streaming_response(self):
        def handler(request):
            body = json.loads(request.content)
            self.assertEqual(body["model"], Config.ASR_MODEL)
            self.assertTrue(
                body["input"]["messages"][0]["content"][0]["input_audio"]["data"]
                .startswith("data:audio/wav;base64,")
            )
            return httpx.Response(
                200,
                json={
                    "output": {
                        "text": "项目九月上线。",
                        "sentence": {
                            "sentence_id": 1,
                            "sentence_end": True,
                            "begin_time": 100,
                            "end_time": 900,
                            "text": "项目九月上线。",
                        },
                    },
                    "usage": {"duration": 1},
                },
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = transcribe_audio(
                _WAV_BYTES,
                "audio/wav",
                "wav",
                api_key="test-key",
                client=client,
            )

        self.assertEqual(result["text"], "项目九月上线。")
        self.assertEqual(result["segments"][0]["start_seconds"], 0.1)
        self.assertEqual(result["segments"][0]["end_seconds"], 0.9)

    def test_collects_final_sentences_from_sse(self):
        events = [
            {
                "output": {
                    "text": "第一句。",
                    "sentence": {
                        "sentence_id": 1,
                        "sentence_end": True,
                        "begin_time": 0,
                        "end_time": 1000,
                        "text": "第一句。",
                    },
                }
            },
            {
                "output": {
                    "text": "第一句。第二句。",
                    "sentence": {
                        "sentence_id": 2,
                        "sentence_end": True,
                        "begin_time": 1100,
                        "end_time": 2000,
                        "text": "第二句。",
                    },
                },
                "usage": {"duration": 2},
            },
        ]
        sse = "\n\n".join(
            f"id:{index}\nevent:result\ndata:{json.dumps(event, ensure_ascii=False)}"
            for index, event in enumerate(events, start=1)
        )

        def handler(_request):
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text=sse,
            )

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            result = transcribe_audio(
                _WAV_BYTES,
                "audio/wav",
                "wav",
                api_key="test-key",
                client=client,
            )

        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(result["segments"][1]["start_seconds"], 1.1)
        self.assertEqual(result["duration_seconds"], 2.0)


if __name__ == "__main__":
    unittest.main()
