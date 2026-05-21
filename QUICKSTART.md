# 2Care.ai Voice AI Agent — Quick Start Guide

## Prerequisites

- Python 3.10+
- Redis (local or Docker)
- LLM API keys (Anthropic or OpenAI)
- Speech API keys (OpenAI for STT/TTS recommended)

## Installation

### 1. Clone & Setup

```bash
cd voice-ai-agent
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

**Required keys:**
- `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
- Redis running on localhost:6379 (or set `REDIS_URL`)

### 3. Start Redis (if local)

```bash
# Using Docker (recommended)
docker run -d -p 6379:6379 redis:7-alpine

# Or if Redis installed locally
redis-server
```

## Running the Application

### Development Mode (with hot reload)

```bash
make dev
# or
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Server runs on: `http://localhost:8000`

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Testing

```bash
# Run all tests
make test

# Run with watch mode
make test-watch

# Run specific test class
pytest tests/test_agent.py::TestAppointmentBooking -v
```

## Architecture Quick Reference

```
Patient Voice (WebSocket)
    ↓
STT (OpenAI Whisper) ~120ms
    ↓
Language Detection (script + langdetect) ~1ms
    ↓
Voice Agent (LLM + Tools) ~150-200ms
    ├─ Session Memory (Redis)
    └─ Persistent Memory (Redis)
    ↓
Tool Execution (Appointment Engine) ~30ms
    ├─ Book Appointment
    ├─ Reschedule
    ├─ Cancel
    └─ Check Availability
    ↓
TTS (OpenAI TTS-1) ~80-100ms
    ↓
Audio Response (WebSocket)

Target: < 450ms end-to-end
```

## WebSocket Endpoints

### 1. Inbound Voice (Patient initiates)

```
ws://localhost:8000/ws/voice/{session_id}?patient_id={patient_id}
```

**Message Format:**
```json
{
  "type": "audio_chunk",
  "data": "<base64-encoded-pcm-audio>",
  "sample_rate": 16000
}
```

**Response:**
```json
{
  "type": "response_audio",
  "data": "<base64-encoded-mp3>",
  "transcript": "What appointment would you like?",
  "language": "en",
  "latency_ms": 245
}
```

### 2. Outbound Campaign (Agent initiates)

```
ws://localhost:8000/ws/campaign/{campaign_id}/{patient_id}
```

Agent initiates conversation for campaign reminders/follow-ups.

## REST API Endpoints

### Health Check
```
GET /api/health
```

### Appointments
```
GET  /api/appointments/availability?doctor_id={doctor_id}&date={date}
POST /api/appointments/book
```

### Campaigns
```
GET  /api/campaigns
POST /api/campaigns
```

## Troubleshooting

### Redis Connection Error

```
ERROR: Cannot connect to redis://localhost:6379
```

**Solution:**
```bash
# Start Redis
docker run -d -p 6379:6379 redis:7-alpine

# Or update REDIS_URL in .env
REDIS_URL=redis://your-redis-host:6379
```

### LLM API Key Error

```
401 Unauthorized: Invalid API key
```

**Solution:**
1. Verify API key in `.env` is correct
2. Check provider is set correctly (`LLM_PROVIDER`)
3. Ensure keys have proper permissions

### Tests Failing

```bash
# Run with verbose output
pytest -vv --tb=long

# Run specific test
pytest tests/test_agent.py::TestAppointmentBooking::test_book_appointment_success -vv
```

## Performance Monitoring

Latency metrics are logged for each request:

```
2026-05-21 13:23:40 INFO backend.controllers: STT latency: 118ms
2026-05-21 13:23:40 INFO backend.controllers: Agent latency: 195ms
2026-05-21 13:23:40 INFO backend.controllers: TTS latency: 92ms
2026-05-21 13:23:40 INFO backend.controllers: Total latency: 405ms ✓
```

Target: `< 450ms`

## Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build

# Or run manually
docker build -t voice-ai-agent .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY voice-ai-agent
```

## Project Structure

```
voice-ai-agent/
├── agent/                  # LLM reasoning + tool orchestration
│   ├── prompt/            # System prompts
│   ├── reasoning/         # Agent logic
│   └── tools/             # Appointment tools
├── backend/               # FastAPI application
│   ├── api/              # Data models
│   ├── controllers/      # WebSocket orchestration
│   ├── routes/           # REST endpoints
│   └── main.py           # App entry point
├── memory/               # Session + persistent stores
├── scheduler/            # Appointment engine
├── services/             # STT, TTS, language detection
├── tests/                # Test suite
├── requirements.txt      # Python dependencies
└── Makefile             # Development commands
```

## Next Steps

- [ ] Set up your LLM provider API keys
- [ ] Start Redis
- [ ] Run tests: `make test`
- [ ] Start dev server: `make dev`
- [ ] Explore API: http://localhost:8000/docs
- [ ] Connect WebSocket client for voice testing

---

For more details, see [README.md](./README.md)
