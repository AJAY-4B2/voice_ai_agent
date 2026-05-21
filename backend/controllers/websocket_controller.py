"""
WebSocket Controller — orchestrates the real-time voice pipeline.

Pipeline per turn:
  audio bytes → STT → language detect → Agent → TTS → audio bytes

Measures and logs latency at each stage.
Target: < 450 ms end-to-end.
"""

import asyncio
import json
import logging
import time
import base64
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect

from backend.api.models import LatencyMetrics
from memory.session_memory.session_store import SessionStore
from services.speech_to_text.stt_service import STTService
from services.text_to_speech.tts_service import TTSService
from services.language_detection.detector import LanguageDetector
from agent.reasoning.agent import VoiceAgent

logger = logging.getLogger(__name__)

LATENCY_TARGET_MS = 450.0


class WebSocketController:
    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        patient_id: Optional[str],
        voice_agent: VoiceAgent,
        stt_service: STTService,
        tts_service: TTSService,
        language_detector: LanguageDetector,
        session_store: SessionStore,
        outbound_mode: bool = False,
        campaign_id: Optional[str] = None,
    ):
        self.ws = websocket
        self.session_id = session_id
        self.patient_id = patient_id
        self.voice_agent = voice_agent
        self.stt = stt_service
        self.tts = tts_service
        self.lang_detector = language_detector
        self.session_store = session_store
        self.outbound_mode = outbound_mode
        self.campaign_id = campaign_id

    async def handle(self):
        await self.ws.accept()
        logger.info(f"WebSocket connected: session={self.session_id}")

        # Initialize session
        await self.session_store.create_session(self.session_id, self.patient_id)

        try:
            if self.outbound_mode:
                await self._handle_outbound_opening()

            while True:
                message = await self.ws.receive()

                if "bytes" in message:
                    # Audio frame received
                    await self._process_audio_frame(message["bytes"])
                elif "text" in message:
                    # Control message (e.g. {"type": "interrupt"})
                    ctrl = json.loads(message["text"])
                    await self._handle_control(ctrl)

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected: session={self.session_id}")
        except Exception as e:
            logger.error(f"WebSocket error [{self.session_id}]: {e}", exc_info=True)
            await self._send_error(str(e))
        finally:
            await self.session_store.close_session(self.session_id)

    # ------------------------------------------------------------------
    # Core pipeline
    # ------------------------------------------------------------------

    async def _process_audio_frame(self, audio_bytes: bytes):
        """Full STT → Agent → TTS pipeline with latency tracking."""
        pipeline_start = time.monotonic()

        # 1. Speech-to-Text
        t0 = time.monotonic()
        transcript = await self.stt.transcribe(audio_bytes)
        stt_ms = (time.monotonic() - t0) * 1000

        if not transcript or not transcript.strip():
            return  # silence / noise — skip

        logger.info(f"[{self.session_id}] STT ({stt_ms:.0f}ms): {transcript!r}")

        # 2. Language Detection
        detected_lang = await self.lang_detector.detect(transcript)

        # 3. Load session context
        session = await self.session_store.get_session(self.session_id)
        if session and session.get("language") and detected_lang == "unknown":
            detected_lang = session["language"]

        # 4. Agent Reasoning + Tool Orchestration
        t1 = time.monotonic()
        agent_response = await self.voice_agent.process(
            session_id=self.session_id,
            patient_id=self.patient_id,
            user_text=transcript,
            language=detected_lang,
        )
        agent_ms = (time.monotonic() - t1) * 1000

        logger.info(f"[{self.session_id}] Agent ({agent_ms:.0f}ms): {agent_response['text']!r}")

        # 5. Text-to-Speech
        t2 = time.monotonic()
        audio_response = await self.tts.synthesize(
            text=agent_response["text"],
            language=agent_response.get("language", detected_lang),
        )
        tts_ms = (time.monotonic() - t2) * 1000

        total_ms = (time.monotonic() - pipeline_start) * 1000

        # 6. Send audio back
        await self.ws.send_bytes(audio_response)

        # 7. Send metadata frame
        metrics = LatencyMetrics(
            session_id=self.session_id,
            stt_latency_ms=stt_ms,
            agent_latency_ms=agent_ms,
            tts_latency_ms=tts_ms,
            total_latency_ms=total_ms,
            met_target=total_ms < LATENCY_TARGET_MS,
        )
        await self.ws.send_text(json.dumps({
            "type": "metadata",
            "transcript": transcript,
            "response_text": agent_response["text"],
            "language": agent_response.get("language", detected_lang),
            "intent": agent_response.get("intent"),
            "latency": metrics.dict(),
        }))

        # 8. Log latency
        self._log_latency(metrics)

    def _log_latency(self, m: LatencyMetrics):
        status = "✅" if m.met_target else "❌ OVER TARGET"
        logger.info(
            f"[LATENCY] {status} session={m.session_id} "
            f"stt={m.stt_latency_ms:.0f}ms "
            f"agent={m.agent_latency_ms:.0f}ms "
            f"tts={m.tts_latency_ms:.0f}ms "
            f"total={m.total_latency_ms:.0f}ms"
        )

    # ------------------------------------------------------------------
    # Outbound campaign opening
    # ------------------------------------------------------------------

    async def _handle_outbound_opening(self):
        """Agent speaks first in outbound campaign mode."""
        opening_text = await self.voice_agent.get_campaign_opening(
            patient_id=self.patient_id,
            campaign_id=self.campaign_id,
            session_id=self.session_id,
        )
        audio = await self.tts.synthesize(opening_text["text"], opening_text["language"])
        await self.ws.send_bytes(audio)
        await self.ws.send_text(json.dumps({
            "type": "agent_opening",
            "text": opening_text["text"],
            "language": opening_text["language"],
        }))

    # ------------------------------------------------------------------
    # Control messages (interrupt / barge-in)
    # ------------------------------------------------------------------

    async def _handle_control(self, ctrl: dict):
        ctrl_type = ctrl.get("type")
        if ctrl_type == "interrupt":
            logger.info(f"[{self.session_id}] Barge-in / interrupt received — stopping TTS")
            # Signal TTS cancellation (handled via asyncio task cancellation in real deployment)
            await self.ws.send_text(json.dumps({"type": "interrupt_ack"}))
        elif ctrl_type == "ping":
            await self.ws.send_text(json.dumps({"type": "pong"}))

    async def _send_error(self, detail: str):
        try:
            await self.ws.send_text(json.dumps({"type": "error", "detail": detail}))
        except Exception:
            pass
