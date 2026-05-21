# 2Care.ai — Real-Time Multilingual Voice AI Agent

> Clinical appointment booking via natural voice conversation in English, Hindi, and Tamil.
> Target latency: **< 450 ms** from speech end to first audio response.

---

## Architecture Overview

```
Patient Voice
     │
     ▼  (WebSocket — raw PCM audio)
┌─────────────────────┐
│   WebSocket Layer   │  ← FastAPI /ws/voice/{session_id}
└──────────┬──────────┘
           │
     ┌─────▼──────┐
     │ STT Service│  ← OpenAI Whisper-1 (~120ms)
     └─────┬──────┘
           │ transcript
     ┌─────▼──────────┐
     │Language Detector│  ← Script heuristic + langdetect (~1ms)
     └─────┬──────────┘
           │ lang: en/hi/ta
     ┌─────▼──────────────────────────────────────┐
     │            Voice Agent (LLM)               │
     │  ┌─────────────┐   ┌────────────────────┐  │
     │  │Session Memory│   │ Persistent Patient │  │
     │  │  (Redis TTL) │   │  Memory (Redis)    │  │
     │  └─────────────┘   └────────────────────┘  │
     │                                             │
     │  Claude 3.5 Haiku / GPT-4o-mini (~150-200ms)│
     │  + Tool Orchestration                       │
     └─────┬───────────────────────────────────────┘
           │ tool calls
     ┌─────▼──────────────────┐
     │  Appointment Engine    │
     │  ┌────────────────┐    │
     │  │ Conflict Check │    │
     │  │ Availability   │    │
     │  │ Book/Cancel/   │    │
     │  │ Reschedule     │    │
     │  └────────────────┘    │
     └─────┬──────────────────┘
           │ result
     ┌─────▼──────┐
     │ TTS Service│  ← OpenAI TTS-1 / Google TTS (~80-100ms)
     └─────┬──────┘
           │ audio bytes (MP3)
     ◄─────┘  (WebSocket response)
Patient hears response
```

---

## Latency Breakdown

| Stage | Target | Notes |
|-------|--------|-------|
| Speech-to-Text (Whisper-1) | ~120ms | Streaming VAD → send on silence |
| Language Detection | ~1ms | Script heuristics (zero API calls) |
| LLM Agent (Haiku / GPT-4o-mini) | ~150-200ms | Compact system prompt, max_tokens=512 |
| Tool Execution (in-process) | ~5ms | Appointment engine is in-memory |
| Text-to-Speech (tts-1) | ~80-100ms | tts-1 (not HD) for speed |
| **Total** | **< 450ms** | Logged per turn |

Latency is **measured and logged** for every pipeline turn. A `met_target` flag is emitted in the WebSocket metadata frame.

---

## Memory Design

### Session Memory (Redis, TTL: 2 hours)
Stores per-conversation state:
- Conversation history (last 10 turns, to control context window size)
- Detected language
- Pending booking intent (partial state during multi-turn booking)
- Last intent

Key: `session:{session_id}` — expires automatically after 2 hours of inactivity.

### Persistent Patient Memory (Redis, TTL: 90 days)
Stores cross-session patient context:
- `preferred_language` — updated on every detected language
- `preferred_doctor`, `preferred_hospital`
- `past_appointments` (last 20)
- Personal details (name, etc.)

Key: `patient:{patient_id}` — TTL refreshed on every access.

**Design rationale**: Redis is used for both layers because it provides sub-millisecond reads, built-in TTL, and horizontal scalability. In production, the persistent layer would be backed by PostgreSQL with Redis as a read-through cache.

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- Docker + Docker Compose
- API keys: Anthropic or OpenAI (LLM), OpenAI (Whisper + TTS)

### 1. Clone and configure
```bash
git clone <repo>
cd voice-ai-agent
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run with Docker (recommended)
```bash
docker-compose up --build
```

### 3. Run locally
```bash
pip install -r requirements.txt
# Start Redis
redis-server --daemonize yes
# Start API
uvicorn backend.main:app --reload --port 8000
```

### 4. Run tests
```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## API Reference

### WebSocket — Inbound Voice
```
ws://localhost:8000/ws/voice/{session_id}?patient_id={patient_id}
```
Send: raw PCM or WAV audio bytes
Receive:
- Audio bytes (MP3) — spoken response
- JSON metadata frame: `{ type, transcript, response_text, language, intent, latency }`

### WebSocket — Outbound Campaign
```
ws://localhost:8000/ws/campaign/{campaign_id}/{patient_id}
```
Agent speaks first. Patient responds naturally.

### REST Endpoints
```
GET  /api/health
POST /api/appointments/book
POST /api/appointments/reschedule
POST /api/appointments/cancel
GET  /api/appointments/availability?doctor_id=&date=
GET  /api/appointments/{id}
GET  /api/appointments/patient/{patient_id}
POST /api/campaigns/schedule
GET  /api/campaigns/{campaign_id}/status
```

---

## Multilingual Support

| Language | Script Detection | STT | TTS |
|----------|-----------------|-----|-----|
| English | Latin (fallback) | Whisper | OpenAI TTS nova |
| Hindi | Devanagari (U+0900–U+097F) | Whisper hi | Google TTS hi-IN / OpenAI |
| Tamil | Tamil (U+0B80–U+0BFF) | Whisper ta | Google TTS ta-IN |

Language preference persists across sessions in patient memory. If a patient always speaks Hindi, the agent responds in Hindi from the first utterance of subsequent sessions.

---

## Outbound Campaign Mode

The agent initiates outbound calls for:
- **Reminders** — "Your appointment with Dr. Sharma is tomorrow at 10 AM."
- **Follow-ups** — Post-visit check-in
- **Vaccination** — Vaccination schedule reminders

Campaigns are scheduled via `POST /api/campaigns/schedule`. Each patient receives an outbound WebSocket call; the agent speaks first, then handles natural responses (booking, rescheduling, polite refusal).

---

## Trade-offs and Known Limitations

### Trade-offs
- **In-memory appointment store**: Fast for demo, loses state on restart. Production: swap to AsyncPG.
- **OpenAI TTS for Hindi**: OpenAI doesn't natively support Hindi; Google Cloud TTS gives better quality for hi/ta but adds latency. Toggle via `TTS_PROVIDER=google`.
- **Compact context window**: Keeping only last 10 turns keeps LLM latency low but loses very long conversation context.
- **Single-process Redis**: For production horizontal scaling, a Redis Cluster with consistent hashing on `patient_id` is recommended.

### Known Limitations
- Barge-in / interrupt handling is signalled via control frame but full duplex audio cancellation requires a WebRTC layer (e.g. LiveKit).
- No real telephony integration (SIP/Twilio) in this implementation; WebSocket assumes a web/app client.
- Whisper processes complete audio chunks, not streaming frames; true streaming STT (e.g. Deepgram) would reduce STT latency to ~60ms.
- Doctor database is in-memory; production would use a proper DB with specialty search.

---

## Project Structure

```
voice-ai-agent/
├── backend/
│   ├── main.py              # FastAPI app + WebSocket endpoints
│   ├── api/models.py        # Pydantic schemas
│   ├── controllers/
│   │   └── websocket_controller.py  # Pipeline orchestrator
│   └── routes/
│       ├── appointments.py
│       ├── campaigns.py
│       └── health.py
├── agent/
│   ├── reasoning/agent.py   # LLM agent + tool dispatch
│   ├── prompt/templates.py  # System prompt builders
│   └── tools/
│       └── appointment_tools.py  # Tool definitions + executors
├── memory/
│   ├── session_memory/session_store.py    # Redis session (TTL 2h)
│   └── persistent_memory/patient_store.py # Redis patient (TTL 90d)
├── services/
│   ├── speech_to_text/stt_service.py   # Whisper integration
│   ├── text_to_speech/tts_service.py   # OpenAI/Google TTS
│   └── language_detection/detector.py  # Script heuristic + langdetect
├── scheduler/
│   └── appointment_engine/engine.py    # Booking, conflicts, availability
├── tests/
│   └── test_agent.py        # Full test suite
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## Evaluation Checklist

| Criterion | Implementation |
|-----------|---------------|
| Real-time voice architecture | WebSocket pipeline, latency measured per turn |
| Agentic reasoning & tool orchestration | Anthropic/OpenAI tool calling, 5 tools |
| Memory design | Redis session (TTL 2h) + persistent patient (TTL 90d) |
| Appointment & conflict management | Full lifecycle, double-booking prevented, past-time rejected |
| Multilingual handling | en/hi/ta, script detection, language persists |
| Performance optimisation | Haiku model, tts-1, compact prompts, phrase cache |
| Code quality & structure | Modular, typed, documented |
| Documentation | This README |
