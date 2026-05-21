"""
2Care.ai Voice AI Agent - Main FastAPI Application
Real-Time Multilingual Clinical Appointment Booking System
"""

import asyncio
import json
import time
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routes import appointments, health, campaigns
from backend.controllers.websocket_controller import WebSocketController
from memory.session_memory.session_store import SessionStore
from memory.persistent_memory.patient_store import PatientStore
from scheduler.appointment_engine.engine import AppointmentEngine
from services.speech_to_text.stt_service import STTService
from services.text_to_speech.tts_service import TTSService
from services.language_detection.detector import LanguageDetector
from agent.reasoning.agent import VoiceAgent
from backend.api.models import AppointmentRequest, PatientContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown application resources."""
    logger.info("Initializing Voice AI Agent services...")

    # Redis connection
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    app.state.redis = await aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)

    # Initialize services
    app.state.session_store = SessionStore(app.state.redis)
    app.state.patient_store = PatientStore(app.state.redis)
    app.state.appointment_engine = AppointmentEngine()
    app.state.stt_service = STTService()
    app.state.tts_service = TTSService()
    app.state.language_detector = LanguageDetector()
    app.state.voice_agent = VoiceAgent(
        session_store=app.state.session_store,
        patient_store=app.state.patient_store,
        appointment_engine=app.state.appointment_engine,
    )

    logger.info("All services initialized successfully.")
    yield

    logger.info("Shutting down Voice AI Agent...")
    await app.state.redis.close()


app = FastAPI(
    title="2Care.ai Voice AI Agent",
    description="Real-Time Multilingual Clinical Appointment Booking via Voice",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(appointments.router, prefix="/api/appointments", tags=["appointments"])
app.include_router(campaigns.router, prefix="/api/campaigns", tags=["campaigns"])


@app.websocket("/ws/voice/{session_id}")
async def voice_websocket(websocket: WebSocket, session_id: str, patient_id: Optional[str] = None):
    """
    Main WebSocket endpoint for real-time voice interaction.
    Handles the full STT → Agent → TTS pipeline with latency tracking.
    """
    controller = WebSocketController(
        websocket=websocket,
        session_id=session_id,
        patient_id=patient_id,
        voice_agent=app.state.voice_agent,
        stt_service=app.state.stt_service,
        tts_service=app.state.tts_service,
        language_detector=app.state.language_detector,
        session_store=app.state.session_store,
    )
    await controller.handle()


@app.websocket("/ws/campaign/{campaign_id}/{patient_id}")
async def campaign_websocket(websocket: WebSocket, campaign_id: str, patient_id: str):
    """
    Outbound campaign WebSocket — agent initiates the conversation.
    """
    controller = WebSocketController(
        websocket=websocket,
        session_id=f"campaign_{campaign_id}_{patient_id}",
        patient_id=patient_id,
        voice_agent=app.state.voice_agent,
        stt_service=app.state.stt_service,
        tts_service=app.state.tts_service,
        language_detector=app.state.language_detector,
        session_store=app.state.session_store,
        outbound_mode=True,
        campaign_id=campaign_id,
    )
    await controller.handle()
