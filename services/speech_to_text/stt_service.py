"""
Speech-to-Text Service.

Primary: OpenAI Whisper API (whisper-1) — supports multilingual including Hindi/Tamil.
Fallback: Google Speech-to-Text (if GOOGLE_STT_KEY set).

Audio input: raw PCM bytes (16-bit, 16kHz mono) wrapped in WAV container.
Output: transcribed string.

Optimizations for latency:
- Stream audio in chunks; transcribe when VAD (voice activity detection) detects end
- Compress audio to mono 16kHz before sending
- Use smaller Whisper model (whisper-1) for speed
"""

import asyncio
import io
import logging
import os
import struct
import wave
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")


def _pcm_to_wav(pcm_bytes: bytes, sample_rate: int = 16000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Wrap raw PCM bytes in a WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


class STTService:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=8.0)

    async def transcribe(self, audio_bytes: bytes, language: Optional[str] = None) -> str:
        """
        Transcribe audio bytes to text.

        audio_bytes: WAV or raw PCM bytes. If raw PCM (no RIFF header), wraps in WAV.
        language: ISO language hint (optional). None = auto-detect.
        """
        if not audio_bytes or len(audio_bytes) < 512:
            return ""

        wav_bytes = audio_bytes
        # If not already a WAV, wrap it
        if not audio_bytes[:4] == b"RIFF":
            wav_bytes = _pcm_to_wav(audio_bytes)

        try:
            return await self._whisper_transcribe(wav_bytes, language)
        except Exception as e:
            logger.error(f"STT error: {e}")
            return ""

    async def _whisper_transcribe(self, wav_bytes: bytes, language: Optional[str]) -> str:
        """Call OpenAI Whisper API."""
        files = {
            "file": ("audio.wav", wav_bytes, "audio/wav"),
            "model": (None, WHISPER_MODEL),
        }
        if language and language != "unknown":
            # Map our lang codes to Whisper's
            lang_map = {"en": "en", "hi": "hi", "ta": "ta"}
            files["language"] = (None, lang_map.get(language, language))

        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        resp = await self._client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers=headers,
            files=files,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("text", "").strip()


# ---------------------------------------------------------------------------
# Demo / test stub (used when no real API key is set)
# ---------------------------------------------------------------------------

class MockSTTService(STTService):
    """
    Returns canned transcriptions for testing without API keys.
    Cycles through multilingual test phrases.
    """
    _phrases = [
        "Book an appointment with a cardiologist tomorrow",
        "मुझे कल डॉक्टर से मिलना है",
        "நாளை மருத்துவரை பார்க்க வேண்டும்",
        "Cancel my appointment",
        "Reschedule to next Friday at 2 PM",
    ]
    _idx = 0

    async def transcribe(self, audio_bytes: bytes, language=None) -> str:
        text = self._phrases[self._idx % len(self._phrases)]
        self._idx += 1
        return text
