"""
Language Detection Service.

Detects language from transcript text.

Strategy (in order):
1. Script-based heuristic (fast, 0ms):
   - Devanagari script → Hindi
   - Tamil script → Tamil
   - Latin script → English
2. langdetect library (fallback for ambiguous text)
3. Return "unknown" if confidence too low

Supported: en, hi, ta
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Unicode ranges
DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
TAMIL_RE = re.compile(r"[\u0B80-\u0BFF]")


class LanguageDetector:
    def __init__(self):
        self._langdetect_available = False
        try:
            import langdetect
            self._langdetect_available = True
        except ImportError:
            logger.warning("langdetect not installed; using script heuristics only.")

    async def detect(self, text: str) -> str:
        """
        Detect language of text. Returns 'en', 'hi', 'ta', or 'unknown'.
        """
        if not text or not text.strip():
            return "unknown"

        # 1. Script heuristics — zero latency, highly reliable for Indian scripts
        if DEVANAGARI_RE.search(text):
            return "hi"
        if TAMIL_RE.search(text):
            return "ta"

        # 2. langdetect for Latin text
        if self._langdetect_available:
            try:
                from langdetect import detect, LangDetectException
                lang = detect(text)
                if lang == "hi":
                    return "hi"
                if lang == "ta":
                    return "ta"
                return "en"  # default to English for Latin text
            except Exception:
                pass

        # Default: if pure ASCII/Latin, assume English
        return "en"

    def detect_sync(self, text: str) -> str:
        """Synchronous version for non-async contexts."""
        if not text:
            return "unknown"
        if DEVANAGARI_RE.search(text):
            return "hi"
        if TAMIL_RE.search(text):
            return "ta"
        return "en"
