# Voice AI Pipeline - AI Agent Instructions

## Project Context

This is a **production-grade real-time voice agent** built with Python FastAPI backend and React TypeScript frontend. The core architecture uses a **deterministic state machine** to control turn-taking between user and AI, ensuring the agent never speaks incorrect intent through speculative execution.

**Critical Design Principle:** Input is buffered/gated (conservative), output is streamed/interruptible (aggressive). The system prioritizes correctness over speed - "never wrong out loud."

## Architecture Overview

### State Machine (Core Logic)
```
IDLE → LISTENING → SPECULATIVE → COMMITTED → SPEAKING → IDLE
                       ↓              ↑
                   (cancel)    (confirm silence)
```

- **SPECULATIVE state is key**: LLM starts during 400ms silence debounce but output is held. If user speaks again, cancel silently. If timer completes, transition to COMMITTED and surface output.
- **Cancellation triggers**: New audio, correction markers ("actually", "wait", "sorry", "no"), or user barge-in during SPEAKING.
- **Never skip state validation**: Use `can_transition(from, to)` before every state change.

### Key Components & Data Flow

**WebSocket Hub (`backend/app/websocket.py`):**
- Single endpoint `/ws/voice` handles all real-time communication
- `ConnectionManager` tracks sessions (session_id → websocket mapping)
- All external API results flow through WebSocket messages (see `api.md` for 20+ message schemas)

**Turn Controller (`backend/app/orchestration/turn_controller.py`):**
- Most complex component - orchestrates state machine, STT, LLM, TTS
- Manages cancellation via `asyncio.Event` shared across LLM/TTS streams
- Critical methods: `handle_audio_chunk()`, `handle_final_transcript()`, `on_silence_complete()`, `handle_interrupt()`
- **Pattern**: All state transitions must emit WebSocket `state_change` messages for frontend

**Transcript Buffer (`backend/app/orchestration/transcript_buffer.py`):**
- Separate storage for partial (UI display only) vs final (LLM input) transcripts
- Buffer locks during COMMITTED state to prevent mutations mid-turn
- **Never send partial transcripts to LLM** - this is a hard requirement

### External API Integration Pattern

**Always reference `api.md` for**:
- Complete WebSocket message schemas (client→server, server→client)
- Deepgram/OpenAI/ElevenLabs streaming setup and error handling
- Rate limits and cost implications (~$4/hour per user)

**Standard error recovery**:
- Deepgram: Exponential backoff (5 attempts: 0s, 1s, 2s, 4s, 8s)
- OpenAI: Single retry with 5s timeout
- ElevenLabs: Retry once, fallback to text-only
- All failures → WebSocket `error` message with `recoverable: boolean`

## Development Workflows

### Project Structure
- `backend/` - Python 3.11+, FastAPI, asyncio-based
- `frontend/` - React 18 + TypeScript, Vite bundler
- **No code exists yet** - this is MVP phase with comprehensive planning docs

### Critical Files (Reference Order)
1. **`PRD.md`** - Product requirements, non-negotiables, architecture rationale
2. **`instruction.md`** - Full dev guide: setup, folder structure, testing with pytest
3. **`api.md`** - Required reading for ANY external API work (WebSocket, Deepgram, OpenAI, ElevenLabs)
4. **`plan.md`** - 20-day implementation roadmap with 100+ tasks

### Running Tests (pytest)
```bash
cd backend
pytest tests/test_state_machine.py    # Unit tests for state transitions
pytest tests/test_turn_controller.py  # Core orchestration logic
pytest -v --cov=app                   # All tests with coverage
```

### Settings Management
**All configuration via UI** (no .env changes needed after setup):
- Silence debounce: 400-1200ms (adaptive based on cancellation rate)
- Cancellation threshold: 30% triggers debounce increase
- Voice selection, LLM model, UI toggles
- Send via WebSocket `update_settings` message type

## Code Conventions

### Python (Backend)
- **Async everywhere**: All I/O uses `async/await`, never blocking calls
- **Type hints required**: Function signatures must specify types
- **Cancellation pattern**: Use `asyncio.Event` for LLM/TTS stream cancellation
  ```python
  async def stream_with_cancellation(stream, cancel_event: asyncio.Event):
      async for chunk in stream:
          if cancel_event.is_set():
              await stream.close()
              return None
          yield chunk
  ```
- **State machine guards**: Always validate transitions before state changes
- **Database writes don't block**: Queue writes on failure, continue voice pipeline

### TypeScript (Frontend)
- **Functional components only**: React hooks, no classes
- **WebSocket message typing**: All messages must match `api.md` schemas exactly
- **Audio interruption**: `AudioPlayer.stop()` must clear queue immediately on barge-in
- **Base64 audio handling**: WebSocket sends base64, decode to ArrayBuffer for playback

### Testing Patterns
- **Mock external APIs**: Use `pytest-mock` for Deepgram/OpenAI/ElevenLabs in integration tests
- **State machine tests**: Verify all valid transitions + reject invalid ones
- **Cancellation tests**: Assert LLM/TTS streams close on cancel_event
- **No rate limiting tests**: This is MVP, cost control not implemented

## Critical Integration Points

### Deepgram → Turn Controller
- Partial transcripts → Update UI only (never to LLM)
- Final transcripts → Add to buffer, start silence timer
- On timer complete without new audio → Transition LISTENING → SPECULATIVE

### LLM → TTS Handoff
- **Wait for first punctuation** (`.`, `?`, `!`) before starting TTS
- Stream tokens internally during SPECULATIVE, only surface after COMMITTED
- Both must respect shared `cancel_event` for interruptions

### Frontend → Backend WebSocket
- Audio chunks: 16kHz mono PCM, send every 100-250ms
- Interrupt message: Triggers SPEAKING → LISTENING, cancels all streams
- Settings updates: Applied immediately without reconnection

## Database Schema
- `sessions`, `turns`, `llm_calls`, `telemetry` tables
- `state_history` in turns: JSONB array of all state transitions for debugging
- `was_interrupted` boolean: Critical for adaptive debounce calculation
- Writes queued on DB failure - never block voice pipeline

## Common Gotchas

1. **Speculative cancellations are silent**: Don't log as errors, these are expected (target <30% rate)
2. **Audio buffer overflow**: Max 10 seconds, drop oldest on overflow
3. **WebSocket reconnect**: Backend keeps session for 5 minutes, frontend auto-reconnects
4. **CORS in dev**: Backend must allow frontend origin (http://localhost:5173)
5. **No authentication**: MVP has no auth, rate limiting, or security features

## Metrics & Telemetry
- Cancellation rate: Drives adaptive debounce (>30% → increase, <15% → decrease)
- Turn latency: Speech end to first audio (target <1000ms)
- Tokens wasted: From canceled LLM calls (cost tracking only)
- All metrics sent to frontend via `telemetry` WebSocket message every 5 turns

---

**When implementing new features:**
1. Check if it affects state machine transitions → Update state_machine.py
2. Adding new WebSocket message → Document in api.md with full schema
3. External API integration → Follow error recovery patterns in api.md
4. New settings → Add to UI SettingsPanel, send via `update_settings`
5. Always test cancellation behavior - this is the hardest part to get right
