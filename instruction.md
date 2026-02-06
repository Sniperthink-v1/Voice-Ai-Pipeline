# Project Instructions: Voice AI Pipeline

## Project Overview

**Voice AI Pipeline** is a production-grade real-time voice agent system that enables natural conversation with AI through voice. The system uses a state machine architecture to ensure correct turn-taking, supports user interruptions (barge-in), and implements speculative execution to guarantee the agent never speaks incorrect intent out loud.

---

## Key Features

- **Real-time Speech-to-Text** using Deepgram streaming API
- **Natural Language Understanding** via OpenAI GPT-4
- **Text-to-Speech** using ElevenLabs streaming
- **Intelligent Turn Control** with state machine (IDLE → LISTENING → SPECULATIVE → COMMITTED → SPEAKING)
- **Barge-in Support** - user can interrupt agent at any time
- **Speculative Execution** - LLM starts during silence but output held until confirmed
- **Adaptive Behavior** - silence debounce adjusts based on cancellation rate
- **Comprehensive Telemetry** - tracks metrics, cancellations, latency
- **Persistent Storage** - all conversations stored in Neon Postgres
- **UI-Managed Settings** - configure behavior without code changes

---

## Technology Stack

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **WebSocket**: Native FastAPI WebSocket support
- **Speech-to-Text**: Deepgram Streaming API
- **LLM**: OpenAI GPT-4 with streaming
- **Text-to-Speech**: ElevenLabs streaming TTS
- **Database**: Neon Postgres (serverless)
- **ORM**: SQLAlchemy 2.0 (async)
- **Migrations**: Alembic
- **Testing**: pytest
- **Async Runtime**: asyncio with uvloop (production)

### Frontend
- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **WebSocket Client**: Native WebSocket API
- **Audio APIs**: 
  - Web Audio API (playback, processing)
  - MediaRecorder API (microphone capture)
  - AudioContext (audio manipulation)
- **Styling**: CSS Modules / Tailwind CSS (TBD)
- **State Management**: React hooks (useState, useEffect, useContext)

### External APIs
**Refer to [api.md](api.md) for detailed documentation on all third-party APIs and WebSocket message schemas.**

---

## Project Folder Structure

```
Voice AI Pipeline/
│
├── PRD.md                          # Product Requirements Document
├── plan.md                         # Detailed implementation plan
├── instruction.md                  # This file - project instructions
├── api.md                          # Third-party API documentation
├── README.md                       # Quickstart guide
│
├── backend/                        # Python FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── config.py               # Configuration management
│   │   ├── models.py               # Pydantic models for WebSocket messages
│   │   ├── websocket.py            # WebSocket endpoint & connection manager
│   │   ├── state_machine.py        # Core state machine logic
│   │   │
│   │   ├── stt/                    # Speech-to-Text
│   │   │   ├── __init__.py
│   │   │   └── deepgram.py         # Deepgram streaming client
│   │   │
│   │   ├── llm/                    # Language Model
│   │   │   ├── __init__.py
│   │   │   └── openai.py           # OpenAI streaming + cancellation
│   │   │
│   │   ├── tts/                    # Text-to-Speech
│   │   │   ├── __init__.py
│   │   │   └── elevenlabs.py       # ElevenLabs streaming TTS
│   │   │
│   │   ├── orchestration/          # Core orchestration logic
│   │   │   ├── __init__.py
│   │   │   ├── turn_controller.py  # Main turn orchestration
│   │   │   ├── transcript_buffer.py # Transcript management
│   │   │   ├── cancellation.py     # Cancellation detection
│   │   │   └── silence_timer.py    # Silence debounce logic
│   │   │
│   │   ├── db/                     # Database layer
│   │   │   ├── __init__.py
│   │   │   ├── postgres.py         # Database connection
│   │   │   ├── models.py           # SQLAlchemy models
│   │   │   └── migrations/         # Alembic migrations
│   │   │       └── versions/
│   │   │
│   │   └── utils/                  # Utilities
│   │       ├── __init__.py
│   │       ├── telemetry.py        # Metrics tracking
│   │       └── audio.py            # Audio format utilities
│   │
│   ├── tests/                      # pytest tests
│   │   ├── __init__.py
│   │   ├── conftest.py             # Pytest fixtures
│   │   ├── test_state_machine.py
│   │   ├── test_transcript_buffer.py
│   │   ├── test_cancellation.py
│   │   ├── test_turn_controller.py
│   │   ├── test_websocket.py
│   │   ├── test_integration.py
│   │   └── test_e2e.py
│   │
│   ├── requirements.txt            # Python dependencies
│   ├── .env.example                # Environment variables template
│   ├── .gitignore                  # Git ignore patterns
│   ├── alembic.ini                 # Alembic configuration
│   ├── Dockerfile                  # Backend Docker image
│   └── README.md                   # Backend setup guide
│
├── frontend/                       # React TypeScript frontend
│   ├── src/
│   │   ├── audio/                  # Audio handling
│   │   │   ├── recorder.ts         # Microphone capture
│   │   │   ├── player.ts           # Audio playback
│   │   │   └── audioContext.ts     # Web Audio API setup
│   │   │
│   │   ├── websocket/              # WebSocket client
│   │   │   ├── client.ts           # Connection manager
│   │   │   ├── messageHandler.ts   # Message routing
│   │   │   └── types.ts            # Message type definitions
│   │   │
│   │   ├── ui/                     # UI components
│   │   │   ├── ConnectionPanel.tsx # Connection controls
│   │   │   ├── TranscriptDisplay.tsx # Transcript display
│   │   │   ├── StateIndicator.tsx  # State machine visualization
│   │   │   ├── HistoryPanel.tsx    # Turn history
│   │   │   ├── MetricsPanel.tsx    # Telemetry display
│   │   │   ├── SettingsPanel.tsx   # Configuration UI
│   │   │   ├── NotificationToast.tsx # Notifications
│   │   │   └── AudioWaveform.tsx   # Audio visualization (optional)
│   │   │
│   │   ├── hooks/                  # React hooks
│   │   │   ├── useVoiceAgent.ts    # Main orchestration hook
│   │   │   └── useAudioStream.ts   # Audio stream management
│   │   │
│   │   ├── types.ts                # Global TypeScript types
│   │   ├── app.tsx                 # Root component
│   │   └── main.tsx                # Entry point
│   │
│   ├── public/
│   │   └── index.html              # HTML template
│   │
│   ├── package.json                # NPM dependencies
│   ├── tsconfig.json               # TypeScript configuration
│   ├── vite.config.ts              # Vite configuration
│   ├── .env.example                # Frontend environment variables
│   ├── Dockerfile                  # Frontend Docker image
│   └── README.md                   # Frontend setup guide
│
└── docker-compose.yml              # Multi-container setup
```

---

## Development Workflow

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "Voice AI Pipeline"
   ```

2. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   cp .env.example .env
   # Edit .env with backend WebSocket URL
   ```

4. **Database Setup**
   ```bash
   cd backend
   alembic upgrade head
   ```

### Running Development Servers

**Backend:**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm run dev
```

Access the app at `http://localhost:5173` (Vite default port).

### Running Tests

**Backend:**
```bash
cd backend
pytest                     # Run all tests
pytest tests/test_state_machine.py  # Run specific test file
pytest -v                  # Verbose output
pytest --cov=app          # With coverage report
```

**Frontend:**
```bash
cd frontend
npm run test              # If test framework added (e.g., Vitest)
```

---

## Architecture Principles

### State Machine (Core Design)

The system is built around a deterministic state machine with 5 states:

```
IDLE → LISTENING → SPECULATIVE → COMMITTED → SPEAKING → IDLE
                       ↓              ↑
                   (cancel)    (confirm silence)
```

**Rules:**
- **IDLE**: Awaiting user input
- **LISTENING**: User is speaking, receiving audio + partial transcripts
- **SPECULATIVE**: STT final received, silence debounce running, LLM may start (output hidden)
- **COMMITTED**: User intent confirmed, LLM output can surface, TTS can start
- **SPEAKING**: Agent is speaking (interruptible)

**Critical Transitions:**
- `LISTENING → SPECULATIVE`: On STT final + silence timer start
- `SPECULATIVE → COMMITTED`: On silence timer complete (no new audio)
- `SPECULATIVE → LISTENING`: On new audio (cancels LLM silently)
- `SPEAKING → LISTENING`: On user interruption (barge-in)

### Input Buffering vs Output Streaming

**Asymmetry Principle:**
- **Input (user speech)**: Buffered, gated, conservative - wait for confirmation before acting
- **Output (agent speech)**: Streamed, aggressive, interruptible - start quickly, allow interruption

### Speculative Execution

**Purpose:** Start LLM call during silence window to reduce latency, but hold output until confirmed.

**Flow:**
1. User finishes speaking (STT sends `is_final=true`)
2. Start 400ms silence debounce timer
3. Start LLM call immediately (in SPECULATIVE state)
4. If timer completes without new audio: Transition to COMMITTED, surface LLM output
5. If new audio arrives: Cancel LLM silently, discard output, transition to LISTENING

**Benefit:** Reduces perceived latency by ~400ms without risking incorrect output.

### Cancellation Rules

Cancel LLM/TTS immediately if:
- User speaks during SPECULATIVE or SPEAKING state
- Correction marker detected: "actually", "wait", "sorry", "no"
- New audio frame received during debounce window

**Log cancellations** for telemetry and adaptive debounce adjustment.

---

## Configuration & Settings

### Environment Variables

**Backend (.env):**
```
DEEPGRAM_API_KEY=your_deepgram_key
OPENAI_API_KEY=your_openai_key
ELEVENLABS_API_KEY=your_elevenlabs_key
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
ENVIRONMENT=development
LOG_LEVEL=INFO
MIN_SILENCE_DEBOUNCE_MS=400
MAX_SILENCE_DEBOUNCE_MS=1200
CANCELLATION_RATE_THRESHOLD=0.30
```

**Frontend (.env):**
```
VITE_WEBSOCKET_URL=ws://localhost:8000/ws/voice
VITE_API_BASE_URL=http://localhost:8000
```

### UI-Managed Settings

All runtime configuration is managed via the **SettingsPanel** component:

- **Silence Debounce (ms)**: 400-1200ms (adaptive or manual)
- **Cancellation Rate Threshold (%)**: 10-50% (triggers debounce increase)
- **Adaptive Debounce**: Enable/disable automatic adjustment
- **Voice Selection**: Choose ElevenLabs voice
- **LLM Model**: GPT-4 vs GPT-3.5-turbo
- **Show Partial Transcripts**: Toggle partial transcript display
- **Show Confidence Scores**: Display STT confidence
- **Audio Visualization**: Enable waveform display

Settings are sent to backend via WebSocket and persisted in localStorage.

---

## Third-Party API Integration

### Deepgram (Speech-to-Text)

**See [api.md](api.md) for detailed Deepgram API documentation.**

- Real-time streaming transcription
- Interim and final results
- Built-in silence detection (endpointing)
- High accuracy and low latency

### OpenAI (Language Model)

**See [api.md](api.md) for detailed OpenAI API documentation.**

- GPT-4 streaming completions
- Token-by-token streaming for responsiveness
- Cancellable streams for speculative execution

### ElevenLabs (Text-to-Speech)

**See [api.md](api.md) for detailed ElevenLabs API documentation.**

- High-quality voice synthesis
- Streaming audio generation
- Low latency with Turbo V2 model

### WebSocket Protocol

**See [api.md](api.md) for complete WebSocket message schemas.**

Custom protocol for real-time bidirectional communication between frontend and backend.

---

## Database Schema

### Tables

**sessions:**
- `id` (UUID, PK)
- `created_at` (TIMESTAMP)
- `ended_at` (TIMESTAMP, nullable)
- `total_turns` (INTEGER)

**turns:**
- `id` (UUID, PK)
- `session_id` (UUID, FK → sessions)
- `user_transcript` (TEXT)
- `agent_response` (TEXT, nullable)
- `state_history` (JSONB) - Array of state transitions
- `started_at` (TIMESTAMP)
- `completed_at` (TIMESTAMP, nullable)
- `was_interrupted` (BOOLEAN)

**llm_calls:**
- `id` (UUID, PK)
- `turn_id` (UUID, FK → turns)
- `status` (VARCHAR) - 'completed', 'canceled', 'failed'
- `tokens_used` (INTEGER)
- `latency_ms` (INTEGER)
- `created_at` (TIMESTAMP)

**telemetry:**
- `id` (UUID, PK)
- `session_id` (UUID, FK → sessions)
- `metric_name` (VARCHAR) - 'cancellation_rate', 'turn_latency', etc.
- `metric_value` (FLOAT)
- `recorded_at` (TIMESTAMP)

---

## Error Handling

### Error Recovery Strategies

**Deepgram Connection Loss:**
- Exponential backoff reconnection (5 attempts: 0s, 1s, 2s, 4s, 8s)
- Buffer audio during outage (max 5s)
- Send buffered audio on reconnect if < 3s old
- Notify user, provide manual reconnect button

**OpenAI API Failure:**
- Single retry with 5s timeout
- On both failures: Log error, notify user, return to IDLE
- Mark turn as `llm_failed` in database

**ElevenLabs TTS Failure:**
- Retry once immediately
- On failure: Fall back to text-only response
- Display "Audio unavailable" in UI
- Mark turn as `tts_failed` in database

**Database Connection Loss:**
- Use connection pooling with pre-ping validation
- On write failure: Queue writes, retry on reconnect
- On read failure: Use in-memory session data
- Don't block voice pipeline on DB issues

**WebSocket Disconnection:**
- Client auto-reconnect with exponential backoff (1s, 2s, 4s)
- Backend: Keep session for 5 minutes to allow reconnect
- Show "Reconnecting..." status in UI

### Error Notification

All errors sent to frontend via WebSocket `error` message type:

```json
{
  "type": "error",
  "data": {
    "code": "STT_CONNECTION_FAILED",
    "message": "Deepgram connection lost",
    "recoverable": true
  }
}
```

Displayed in UI via NotificationToast component.

---

## Testing Strategy

### Unit Tests (pytest)

- **State Machine**: Test all transitions, guards, hooks
- **Transcript Buffer**: Test merge logic, locking, clearing
- **Cancellation**: Test marker detection, event propagation
- **Turn Controller**: Test turn lifecycle, interruptions

**Run:** `pytest tests/test_*.py`

### Integration Tests

- Mock external APIs (Deepgram, OpenAI, ElevenLabs)
- Test WebSocket message flow
- Test complete conversation scenarios
- Test error recovery flows

**Run:** `pytest tests/test_integration.py`

### End-to-End Tests

- Use real API keys in test environment
- Test with sample audio files
- Verify complete turn cycle with real services
- Measure end-to-end latency

**Run:** `pytest tests/test_e2e.py`

### Manual Testing

See `plan.md` Phase 8.5 for comprehensive manual testing checklist.

---

## Deployment

### Docker (Recommended for Production)

**Build and run:**
```bash
docker-compose up --build
```

**Production deployment:**
1. Build Docker images
2. Push to container registry
3. Deploy to cloud platform (AWS ECS, GCP Cloud Run, Azure Container Apps, Render, Railway)
4. Configure environment variables
5. Set up HTTPS/WSS with SSL certificates
6. Configure monitoring and logging

### Environment-Specific Configuration

**Development:**
- Debug logging enabled
- Hot reload for code changes
- CORS allows all origins

**Production:**
- Info-level logging
- CORS restricted to specific origins
- Use secrets manager for API keys (AWS Secrets Manager, etc.)
- Enable performance monitoring (Sentry, Datadog)
- Set up log aggregation

---

## Monitoring & Telemetry

### Metrics Tracked

- **Cancellation Rate**: % of turns canceled (target: <30%)
- **Turn Latency**: Time from speech end to first audio (target: <1000ms)
- **Tokens Wasted**: Tokens from canceled LLM calls
- **Average Silence Debounce**: Current debounce value (ms)
- **Interruption Count**: Number of barge-ins
- **API Error Rates**: Failures for each external service

### Adaptive Behavior

**Silence Debounce Adjustment:**
- If cancellation rate > 30%: Increase debounce by 100ms (max 1200ms)
- If cancellation rate < 15%: Decrease debounce by 50ms (min 400ms)
- Adjust every 10 turns

**Goal:** Balance responsiveness (low latency) with accuracy (avoid false starts).

---

## Code Style & Conventions

### Python (Backend)

- **PEP 8** style guide
- **Google-style** or **NumPy-style** docstrings
- Type hints for all function signatures
- Use `async/await` for all I/O operations
- Maximum line length: 100 characters
- Use `black` for auto-formatting (optional)

### TypeScript (Frontend)

- **ESLint** with recommended rules
- Functional components with hooks (no class components)
- Type all props and state
- Use `const` for immutable variables
- Maximum line length: 100 characters
- Use Prettier for auto-formatting (optional)

### Git Commit Messages

- Use conventional commits format: `type(scope): message`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
- Example: `feat(stt): add Deepgram reconnection logic`

---

## Troubleshooting

### Common Issues

**WebSocket connection fails:**
- Check backend is running on correct port (8000)
- Verify CORS configuration allows frontend origin
- Check firewall rules

**No audio output:**
- Verify ElevenLabs API key is valid
- Check browser console for audio errors
- Ensure user granted microphone permission

**High cancellation rate:**
- Check if silence debounce is too low
- Enable adaptive debounce
- Review user speech patterns (fast talker?)

**Database connection errors:**
- Verify DATABASE_URL is correct
- Check network connectivity to Neon Postgres
- Ensure database exists and migrations are applied

**API rate limits:**
- Monitor API usage in respective dashboards
- Implement request throttling if needed
- Consider upgrading API plan

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Commit changes: `git commit -am 'feat(scope): add new feature'`
4. Push to branch: `git push origin feat/my-feature`
5. Submit pull request

**Before submitting:**
- Run all tests: `pytest`
- Ensure code follows style guide
- Update documentation if needed
- Add tests for new features

---

## Resources

- **PRD**: [PRD.md](PRD.md) - Full product requirements
- **Plan**: [plan.md](plan.md) - Detailed implementation plan
- **API Docs**: [api.md](api.md) - Third-party API reference (REQUIRED for API integration)
- **Deepgram Docs**: https://developers.deepgram.com/docs
- **OpenAI Docs**: https://platform.openai.com/docs
- **ElevenLabs Docs**: https://docs.elevenlabs.io/
- **FastAPI Docs**: https://fastapi.tiangolo.com/
- **React Docs**: https://react.dev/

---

## Support

For issues or questions:
1. Check this instruction document
2. Review [api.md](api.md) for API-specific guidance
3. Review [plan.md](plan.md) for implementation details
4. Check existing issues in repository
5. Create new issue with reproduction steps

---

## License

[Specify license - MIT, Apache 2.0, etc.]

---

**Remember:** When working with third-party APIs (Deepgram, OpenAI, ElevenLabs, WebSocket), always refer to [api.md](api.md) for complete documentation, message schemas, error handling, and best practices.
