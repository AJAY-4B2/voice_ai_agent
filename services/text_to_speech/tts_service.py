"""
Text-to-Speech Service.

Primary: OpenAI TTS API (tts-1 — low latency) or Google Cloud TTS.
Language routing:
  en  → OpenAI TTS (alloy/nova voice)
  hi  → Google Cloud TTS (hi-IN-Wavenet-A) or ElevenLabs
  ta  → Google Cloud TTS (ta-IN-Wavenet-A)

Returns: raw MP3 bytes.

Latency optimization:
- Use tts-1 (not tts-1-hd) for speed
- Short responses only (< 200 chars) for sub-100ms synthesis
- Cache common phrases (greetings, confirmations)
"""

import asyncio
import base64
import hashlib
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GOOGLE_TTS_KEY = os.getenv("GOOGLE_TTS_KEY", "")
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "openai")

# Voice mappings for OpenAI TTS
OPENAI_VOICE_MAP = {
    "en": "nova",
    "hi": "shimmer",  # OpenAI doesn't support Hindi natively; use shimmer and romanize
    "ta": "shimmer",
}

# Google TTS voice names
GOOGLE_VOICE_MAP = {
    "en": {"languageCode": "en-IN", "name": "en-IN-Wavenet-D"},
    "hi": {"languageCode": "hi-IN", "name": "hi-IN-Wavenet-A"},
    "ta": {"languageCode": "ta-IN", "name": "ta-IN-Wavenet-A"},
}


class TTSService:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=8.0)
        self._cache: dict = {}  # Simple in-process cache

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """
        Convert text to speech audio bytes (MP3).
        Returns empty bytes on failure.
        """
        if not text:
            return b""

        # Cache key
        cache_key = hashlib.md5(f"{language}:{text}".encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            if TTS_PROVIDER == "google" and GOOGLE_TTS_KEY:
                audio = await self._google_tts(text, language)
            else:
                audio = await self._openai_tts(text, language)

            if len(audio) > 0:
                self._cache[cache_key] = audio
            return audio
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return b""

    async def _openai_tts(self, text: str, language: str) -> bytes:
        voice = OPENAI_VOICE_MAP.get(language, "nova")
        payload = {
            "model": "tts-1",  # Use tts-1 (not hd) for low latency
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        resp = await self._client.post(
            "https://api.openai.com/v1/audio/speech",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.content

    async def _google_tts(self, text: str, language: str) -> bytes:
        voice_config = GOOGLE_VOICE_MAP.get(language, GOOGLE_VOICE_MAP["en"])
        payload = {
            "input": {"text": text},
            "voice": {**voice_config, "ssmlGender": "FEMALE"},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.05},
        }
        resp = await self._client.post(
            f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_TTS_KEY}",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return base64.b64decode(data["audioContent"])


class MockTTSService(TTSService):
    """Returns a minimal valid MP3 for testing."""

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        logger.info(f"[MockTTS] ({language}): {text}")
        # Return a tiny silent MP3 frame
        return b"\xff\xfb\x90\x00" + b"\x00" * 417
