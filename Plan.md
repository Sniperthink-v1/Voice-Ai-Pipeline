# Implementation Plan: Voice AI Pipeline

## Overview
Production-grade real-time voice agent with Python FastAPI backend and React TypeScript frontend. System uses state machine architecture to control STT (Deepgram), LLM (OpenAI), and TTS (ElevenLabs) with strict turn-taking, interruption support, and speculative execution.

---

## Phase 1: Core Infrastructure & Project Setup (Days 1-2)

### 1.1 Backend Foundation
**Files to create:**
- `backend/requirements.txt` - Python dependencies
- `backend/.env.example` - Environment variable template
- `backend/.gitignore` - Git ignore patterns
- `backend/app/__init__.py` - Package initialization
- `backend/app/config.py` - Configuration management (env vars, constants)
- `backend/app/models.py` - Pydantic models for WebSocket messages

**Tasks:**
- [ ] Initialize Python virtual environment
- [ ] Install core dependencies:
  - `fastapi==0.109.0`
  - `uvicorn[standard]==0.27.0`
  - `websockets==12.0`
  - `pydantic==2.5.0`
  - `python-dotenv==1.0.0`
- [ ] Create FastAPI application instance in `main.py`
- [ ] Set up CORS middleware for frontend communication
- [ ] Define Pydantic models for all WebSocket message types (8 client → server, 9 server → client)

### 1.2 State Machine Implementation
**Files to create:**
- `backend/app/state_machine.py` - Core state machine logic

**Tasks:**
- [ ] Define `TurnState` enum with 5 states: IDLE, LISTENING, SPECULATIVE, COMMITTED, SPEAKING
- [ ] Implement `StateMachine` class with:
  - Current state tracking
  - Transition guards (allowed_transitions dict)
  - `can_transition(from_state, to_state) -> bool`
  - `async transition(to_state)` with validation
  - `on_enter(state)` and `on_exit(state)` hooks
  - State change event emission
- [ ] Add comprehensive transition logging
- [ ] Write pytest unit tests for all state transitions
- [ ] Test invalid transition rejection

### 1.3 Database Setup
**Files to create:**
- `backend/app/db/__init__.py`
- `backend/app/db/postgres.py` - Database connection and session management
- `backend/app/db/models.py` - SQLAlchemy models
- `backend/alembic.ini` - Alembic configuration
- `backend/app/db/migrations/versions/` - Migration versions directory

**Tasks:**
- [ ] Install dependencies: `sqlalchemy==2.0.25`, `asyncpg==0.29.0`, `alembic==1.13.0`
- [ ] Define SQLAlchemy models:
  - **sessions**: id (UUID), created_at, ended_at, total_turns
  - **turns**: id (UUID), session_id (FK), user_transcript, agent_response, state_history (JSONB), started_at, completed_at, was_interrupted
  - **llm_calls**: id (UUID), turn_id (FK), status (completed/canceled/failed), tokens_used, latency_ms, created_at
  - **telemetry**: id (UUID), session_id (FK), metric_name, metric_value, recorded_at
- [ ] Set up async connection pool with Neon Postgres
- [ ] Create initial Alembic migration
- [ ] Test database connection and CRUD operations

### 1.4 WebSocket Foundation
**Files to create:**
- `backend/app/websocket.py` - WebSocket endpoint and connection manager

**Tasks:**
- [ ] Implement `ConnectionManager` class:
  - Track active WebSocket connections (dict: session_id → websocket)
  - `async connect(websocket)` - Accept connection, create session
  - `async disconnect(session_id)` - Cleanup session
  - `async send_message(session_id, message)` - Send JSON message
  - `async broadcast(message)` - Send to all connections
- [ ] Create `/ws/voice` WebSocket endpoint in `main.py`
- [ ] Implement message routing based on `message.type`
- [ ] Add connection lifecycle logging
- [ ] Handle WebSocketDisconnect exception

### 1.5 Frontend Foundation
**Files to create:**
- `frontend/package.json` - Dependencies and scripts
- `frontend/tsconfig.json` - TypeScript configuration
- `frontend/vite.config.ts` - Vite bundler config
- `frontend/.env.example` - Frontend environment variables
- `frontend/src/main.tsx` - Entry point
- `frontend/src/app.tsx` - Root component
- `frontend/src/types.ts` - Global TypeScript types

**Tasks:**
- [ ] Initialize Vite React TypeScript project
- [ ] Install dependencies:
  - `react@18.2.0`
  - `typescript@5.3.0`
  - `vite@5.0.0`
  - `@types/react`
  - `@types/node`
- [ ] Set up basic app layout with header and main content area
- [ ] Create global type definitions for WebSocket messages (matching backend)
- [ ] Add hot module replacement for development

---

## Phase 2: STT Integration & Transcript Management (Days 3-4)

### 2.1 Deepgram Integration
**Files to create:**
- `backend/app/stt/__init__.py`
- `backend/app/stt/deepgram.py` - Deepgram streaming client

**Tasks:**
- [ ] Install `deepgram-sdk==3.2.0`
- [ ] Implement `DeepgramSTT` class:
  - `async connect()` - Initialize Deepgram live transcription
  - Configuration: punctuate=True, interim_results=True, endpointing=400ms, language='en-US'
  - `async send_audio(audio_chunk: bytes)` - Stream audio to Deepgram
  - `async on_transcript(callback)` - Register transcript handler
  - Handle `is_final` vs partial transcripts
  - Error handling with reconnection logic (exponential backoff: 0s, 1s, 2s, 4s, max 5 attempts)
- [ ] Add transcript event emission to WebSocket clients
- [ ] Test with sample audio files

### 2.2 Transcript Buffer
**Files to create:**
- `backend/app/orchestration/__init__.py`
- `backend/app/orchestration/transcript_buffer.py` - Transcript accumulation and merging

**Tasks:**
- [ ] Implement `TranscriptBuffer` class:
  - `partial_text: str` - Current partial transcript for UI
  - `final_segments: List[str]` - List of finalized segments
  - `is_locked: bool` - Buffer locked during COMMITTED state
  - `add_partial(text: str)` - Update partial transcript
  - `add_final(text: str)` - Append final segment
  - `get_complete_text() -> str` - Merge all final segments
  - `clear()` - Reset buffer (on turn complete or interrupt)
  - `lock()` / `unlock()` - Control buffer mutations
- [ ] Add timestamp tracking for each segment
- [ ] Implement confidence score aggregation
- [ ] Write pytest tests for merge logic

### 2.3 Silence Debounce Logic
**Files to create:**
- `backend/app/orchestration/silence_timer.py` - Debounce timer management

**Tasks:**
- [ ] Implement `SilenceTimer` class:
  - `debounce_ms: int` - Current debounce duration (starts at 400ms)
  - `timer_task: asyncio.Task` - Running timer task
  - `async start(callback)` - Start countdown, call callback on completion
  - `cancel()` - Cancel active timer
  - `is_active() -> bool` - Check if timer running
- [ ] Integrate with state machine:
  - On STT `is_final=true`: Start timer
  - On new audio/partial: Cancel timer
  - On timer complete: Transition LISTENING → SPECULATIVE
- [ ] Add timer state logging

### 2.4 Frontend Audio Capture
**Files to create:**
- `frontend/src/audio/recorder.ts` - Microphone capture and streaming
- `frontend/src/audio/audioContext.ts` - Web Audio API setup

**Tasks:**
- [ ] Implement `AudioRecorder` class:
  - `async init()` - Request microphone permission via getUserMedia
  - Audio constraints: 16kHz sample rate, mono channel
  - Use MediaRecorder API with `ondataavailable` handler
  - `start()` - Begin recording
  - `stop()` - Stop recording
  - Convert audio chunks to base64 for WebSocket transmission
  - Handle permission denied errors
- [ ] Create audio worklet for real-time processing (optional optimization)
- [ ] Add volume level visualization (for UI feedback)

### 2.5 Transcript Display UI
**Files to create:**
- `frontend/src/ui/TranscriptDisplay.tsx` - Display partial and final transcripts

**Tasks:**
- [ ] Create component with two sections:
  - **User transcripts**: Show partial (gray/italic) and final (bold/black)
  - **Agent responses**: Show completed turns
- [ ] Implement auto-scroll to latest transcript
- [ ] Add timestamp display for each turn
- [ ] Style differentiation for partial vs final
- [ ] Show confidence scores (optional, configurable)

### 2.6 WebSocket Client
**Files to create:**
- `frontend/src/websocket/client.ts` - WebSocket connection manager
- `frontend/src/websocket/messageHandler.ts` - Message routing
- `frontend/src/websocket/types.ts` - Message type definitions

**Tasks:**
- [ ] Implement `WebSocketClient` class:
  - `connect(url: string)` - Establish WebSocket connection
  - `disconnect()` - Close connection
  - `send(message: object)` - Send JSON message
  - `on(messageType: string, handler: Function)` - Register message handlers
  - Auto-reconnect on disconnect (exponential backoff: 1s, 2s, 4s)
  - Connection state: connecting, connected, disconnected, reconnecting
- [ ] Implement message routing in `messageHandler.ts`:
  - Route messages by `type` field
  - Dispatch to registered handlers
- [ ] Add connection status callbacks

---

## Phase 3: LLM Integration & Turn Control (Days 5-6)

### 3.1 OpenAI Integration
**Files to create:**
- `backend/app/llm/__init__.py`
- `backend/app/llm/openai.py` - OpenAI streaming with cancellation

**Tasks:**
- [ ] Install `openai==1.12.0`
- [ ] Implement `OpenAILLM` class:
  - `async stream_completion(messages, cancel_event: asyncio.Event)`
  - Use `stream=True` for token-by-token streaming
  - Model: `gpt-4-turbo-preview` (or latest GPT-4)
  - Check `cancel_event.is_set()` on each token
  - On cancellation: Close stream immediately, return None
  - Yield tokens as they arrive
  - Track token count and latency
- [ ] Add conversation context management (system prompt + history)
- [ ] Implement retry logic (single retry with 5s timeout on failure)
- [ ] Log all LLM calls to `llm_calls` table with status

### 3.2 Cancellation Detection
**Files to create:**
- `backend/app/orchestration/cancellation.py` - Detect cancellation signals

**Tasks:**
- [ ] Implement `CancellationDetector` class:
  - `correction_markers = ["actually", "wait", "sorry", "no"]`
  - `check_transcript(text: str) -> bool` - Scan for markers
  - `check_audio_activity(timestamp) -> bool` - Detect new audio
  - Create `cancel_event: asyncio.Event` for each turn
  - `set_cancellation()` - Signal cancellation to LLM/TTS
- [ ] Integrate with transcript buffer:
  - On new partial: Check for correction markers
  - On marker detected: Set cancel_event, transition to LISTENING
- [ ] Log all cancellations with reason (correction_marker / new_audio)

### 3.3 Turn Controller (Core Orchestration)
**Files to create:**
- `backend/app/orchestration/turn_controller.py` - Main orchestration logic

**Tasks:**
- [ ] Implement `TurnController` class (most complex component):
  - Manages state machine, transcript buffer, silence timer, cancellation
  - `async handle_audio_chunk(audio_bytes)`:
    - Forward to Deepgram
    - If in SPEAKING state: Trigger barge-in (cancel TTS, transition to LISTENING)
  - `async handle_partial_transcript(text)`:
    - Update transcript buffer
    - Check cancellation detector
    - If cancellation: Cancel LLM, reset to LISTENING
  - `async handle_final_transcript(text)`:
    - Add to buffer
    - Start silence timer (400ms)
  - `async on_silence_complete()`:
    - Transition LISTENING → SPECULATIVE
    - Get complete transcript from buffer
    - Start LLM call (with cancel_event)
    - Hold LLM output internally (not sent to client yet)
  - `async on_llm_token(token)`:
    - Accumulate tokens
    - Detect first punctuation mark (`.`, `?`, `!`)
    - On first punctuation AND in COMMITTED state: Start TTS
    - If in SPECULATIVE: Check if user interrupted
      - If no new audio after 200ms: Transition to COMMITTED
      - If new audio: Cancel LLM, transition to LISTENING
  - `async on_llm_complete(full_response)`:
    - Store turn in database
    - If TTS not started: Start now (fallback)
  - `async handle_interrupt()`:
    - Cancel LLM and TTS
    - Clear transcript buffer
    - Clear audio playback queue (signal frontend)
    - Transition to LISTENING
    - Log interrupted turn
- [ ] Add comprehensive state transition logging
- [ ] Track turn metrics (latency, tokens, etc.)

### 3.4 Speculative to Committed Transition
**Tasks:**
- [ ] Implement dual-check logic:
  - LLM starts in SPECULATIVE state
  - After 200ms of silence post-final-transcript: Transition to COMMITTED
  - Only after COMMITTED: Allow TTS to start and output to surface
- [ ] If user speaks during SPECULATIVE → LISTENING:
  - Cancel LLM silently
  - Mark turn as "speculative_canceled" in database
  - No audio played

---

## Phase 4: TTS Integration & Audio Playback (Days 7-8)

### 4.1 ElevenLabs Integration
**Files to create:**
- `backend/app/tts/__init__.py`
- `backend/app/tts/elevenlabs.py` - ElevenLabs streaming TTS

**Tasks:**
- [ ] Install `elevenlabs==0.2.26`
- [ ] Implement `ElevenLabsTTS` class:
  - `async stream_audio(text: str, cancel_event: asyncio.Event)`
  - Voice: "Bella" (or configurable voice ID)
  - Model: "eleven_turbo_v2" (fastest, lowest latency)
  - Stream audio chunks as generated
  - Check `cancel_event.is_set()` between chunks
  - On cancellation: Stop generation immediately
  - Yield base64-encoded audio chunks
- [ ] Add error handling:
  - On failure: Retry once
  - If both fail: Send text-only response to frontend, log error
- [ ] Track TTS latency (first chunk time)

### 4.2 TTS Orchestration
**Tasks:**
- [ ] Integrate TTS with turn controller:
  - Start only after COMMITTED state
  - Wait for first punctuation mark (`.`, `?`, `!`) in LLM output
  - Stream chunks to frontend via WebSocket (`agent_audio_chunk` messages)
  - Transition to SPEAKING state when first chunk sent
- [ ] Add chunk indexing for frontend reassembly
- [ ] Handle TTS completion:
  - Send `is_final=true` on last chunk
  - Transition SPEAKING → IDLE
  - Store turn completion in database

### 4.3 Frontend Audio Playback
**Files to create:**
- `frontend/src/audio/player.ts` - Audio queue and playback management

**Tasks:**
- [ ] Implement `AudioPlayer` class:
  - Audio context and source node setup
  - `queue: AudioBuffer[]` - Chunk queue
  - `enqueue(base64Audio: string)` - Decode and add to queue
  - `play()` - Start playback from queue
  - `stop()` - Immediate stop and clear queue (for barge-in)
  - Auto-play next chunk when previous completes
  - Handle audio format conversion (base64 → ArrayBuffer → AudioBuffer)
- [ ] Implement seamless chunk playback (no gaps)
- [ ] Add volume control (optional)
- [ ] Show playback progress indicator in UI

### 4.4 Barge-in (Interruption) Handling
**Tasks:**
- [ ] Frontend interruption detection:
  - On microphone audio detected while agent SPEAKING: Send `interrupt` message
  - Immediately call `AudioPlayer.stop()` to clear playback
  - Show "Interrupted" indicator in UI
- [ ] Backend interruption handling:
  - On `interrupt` message or audio during SPEAKING:
    - Cancel TTS stream
    - Cancel LLM if still generating
    - Mark turn as `was_interrupted=true`
    - Transition SPEAKING → LISTENING
    - Clear transcript buffer
- [ ] Test interruption at various points (early, mid-sentence, end)

---

## Phase 5: Telemetry & Adaptive Behavior (Days 9-10)

### 5.1 Telemetry System
**Files to create:**
- `backend/app/utils/__init__.py`
- `backend/app/utils/telemetry.py` - Metrics collection and calculation

**Tasks:**
- [ ] Implement `TelemetryTracker` class:
  - Track per-session metrics:
    - `cancellation_count: int`
    - `completed_turns: int`
    - `cancellation_rate: float` (cancellation_count / total_turns)
    - `avg_turn_latency_ms: float` (speech_end to first_audio)
    - `tokens_wasted: int` (from canceled LLM calls)
    - `avg_silence_debounce_ms: float`
  - `record_turn(turn_data)` - Log turn completion
  - `record_cancellation(reason)` - Log cancellation
  - `get_metrics() -> dict` - Return current metrics
  - `persist_to_db()` - Save to telemetry table
- [ ] Integrate with turn controller:
  - Record metrics on each turn complete/cancel
  - Calculate rolling averages (last 10 turns)
- [ ] Send telemetry updates to frontend via WebSocket (every 5 turns)

### 5.2 Adaptive Silence Debounce
**Tasks:**
- [ ] Implement adaptive logic in turn controller:
  - Monitor cancellation rate
  - **If cancellation_rate > 30%**: Increase debounce by 100ms (max 1200ms)
  - **If cancellation_rate < 15%**: Decrease debounce by 50ms (min 400ms)
  - Adjust after every 10 turns
  - Log debounce adjustments
- [ ] Add debounce value to telemetry metrics
- [ ] Create UI control to manually override debounce (settings panel)

### 5.3 Metrics UI
**Files to create:**
- `frontend/src/ui/MetricsPanel.tsx` - Real-time metrics display

**Tasks:**
- [ ] Create component showing:
  - Cancellation rate (% with color coding: green <20%, yellow 20-30%, red >30%)
  - Current silence debounce (ms)
  - Average turn latency (ms)
  - Total turns completed
  - Tokens wasted
- [ ] Update metrics on WebSocket `telemetry` message
- [ ] Add mini charts for metrics over time (optional, use lightweight library)
- [ ] Make panel collapsible

---

## Phase 6: UI Polish & User Experience (Days 11-12)

### 6.1 Connection Management UI
**Files to create:**
- `frontend/src/ui/ConnectionPanel.tsx` - Connection button and status

**Tasks:**
- [ ] Create component with:
  - "Connect" button (disabled when connected)
  - "Disconnect" button (disabled when disconnected)
  - Connection status indicator (dot: gray=disconnected, yellow=connecting, green=connected, orange=reconnecting)
  - Session ID display (once connected)
  - Auto-reconnect countdown timer
- [ ] Handle connection states:
  - On "Connect": Call `WebSocketClient.connect()`
  - On successful connection: Show session ID, enable microphone
  - On disconnect: Disable microphone, show reconnection status
- [ ] Add microphone permission request on connect

### 6.2 State Machine Visualization
**Files to create:**
- `frontend/src/ui/StateIndicator.tsx` - Visual state machine display

**Tasks:**
- [ ] Create component showing current state:
  - IDLE: Gray circle
  - LISTENING: Blue circle with pulse animation
  - SPECULATIVE: Yellow circle with spinner
  - COMMITTED: Green circle
  - SPEAKING: Purple circle with audio wave animation
- [ ] Update on WebSocket `state_change` message
- [ ] Show state name and timestamp
- [ ] Add state transition history (last 5 transitions)
- [ ] Make component prominent in UI

### 6.3 Turn History Panel
**Files to create:**
- `frontend/src/ui/HistoryPanel.tsx` - Conversation history display

**Tasks:**
- [ ] Create scrollable list showing:
  - Each turn with user transcript and agent response
  - Timestamp for each turn
  - Turn duration
  - Interrupted indicator (if applicable)
  - Confidence scores (optional)
- [ ] Update on WebSocket `turn_complete` message
- [ ] Add "Clear History" button
- [ ] Persist history in localStorage (optional)
- [ ] Auto-scroll to latest turn

### 6.4 Settings Panel (UI-Managed Configuration)
**Files to create:**
- `frontend/src/ui/SettingsPanel.tsx` - Configuration controls

**Tasks:**
- [ ] Create collapsible settings panel with controls for:
  - **Silence Debounce (ms)**: Slider (400-1200ms) + number input
  - **Cancellation Rate Threshold (%)**: Slider (10-50%) + number input
  - **Adaptive Debounce**: Toggle (enable/disable)
  - **Voice Selection**: Dropdown (ElevenLabs voice options)
  - **LLM Model**: Dropdown (GPT-4, GPT-3.5-turbo)
  - **Show Partial Transcripts**: Toggle
  - **Show Confidence Scores**: Toggle
  - **Audio Visualization**: Toggle
- [ ] Send settings updates to backend via WebSocket (`update_settings` message)
- [ ] Apply settings changes immediately (no page reload)
- [ ] Persist settings in localStorage
- [ ] Add "Reset to Defaults" button

### 6.5 Error Display & Notifications
**Files to create:**
- `frontend/src/ui/NotificationToast.tsx` - Error and info notifications

**Tasks:**
- [ ] Create toast notification system:
  - Show errors from WebSocket `error` messages
  - Display connection status changes
  - Show interruption notifications
  - Auto-dismiss after 5 seconds (configurable)
- [ ] Add notification types: error (red), warning (yellow), info (blue), success (green)
- [ ] Make notifications non-blocking (corner overlay)

### 6.6 Audio Visualization (Optional Enhancement)
**Files to create:**
- `frontend/src/ui/AudioWaveform.tsx` - Real-time waveform visualization

**Tasks:**
- [ ] Create waveform visualization for user microphone:
  - Use Web Audio API AnalyserNode
  - Draw frequency bars or oscilloscope view
  - Update in real-time during LISTENING state
- [ ] Create agent audio visualization during SPEAKING state
- [ ] Add volume level indicator

### 6.7 Main Layout Assembly
**Tasks:**
- [ ] In `app.tsx`, assemble all components:
  ```
  <App>
    <Header>
      <ConnectionPanel />
      <StateIndicator />
    </Header>
    <MainContent>
      <TranscriptDisplay />
      <AudioWaveform />
    </MainContent>
    <Sidebar>
      <HistoryPanel />
      <MetricsPanel />
      <SettingsPanel />
    </Sidebar>
    <NotificationToast />
  </App>
  ```
- [ ] Add responsive layout (mobile-friendly)
- [ ] Apply consistent styling (CSS/Tailwind)
- [ ] Add dark mode support (optional)

---

## Phase 7: Error Recovery & Resilience (Days 13-14)

### 7.1 Deepgram Error Recovery
**Tasks:**
- [ ] Implement exponential backoff reconnection:
  - Attempt 1: Immediate (0s delay)
  - Attempt 2: 1s delay
  - Attempt 3: 2s delay
  - Attempt 4: 4s delay
  - Attempt 5: 8s delay
  - After 5 failures: Notify user, transition to IDLE
- [ ] Buffer audio during outage (max 5 seconds)
- [ ] On reconnect: Send buffered audio if < 3s old, else discard
- [ ] Send `error` message to frontend with `recoverable=true`
- [ ] Add manual reconnect button in UI

### 7.2 OpenAI Error Recovery
**Tasks:**
- [ ] Handle API errors:
  - Rate limit (429): Wait and retry with exponential backoff
  - Timeout: Single retry with 5s timeout
  - Server error (500): Single retry
  - Authentication error (401): Notify user, don't retry
- [ ] On both retries failed:
  - Log error with turn context
  - Send `error` message to frontend
  - Display "LLM unavailable, please try again"
  - Transition to IDLE
- [ ] Mark turn as `llm_failed` in database

### 7.3 ElevenLabs Error Recovery
**Tasks:**
- [ ] Handle TTS errors:
  - Network error: Retry once immediately
  - API error: Retry once immediately
  - On both failures: Fall back to text-only response
- [ ] Text-only fallback:
  - Send agent response as text via WebSocket (`agent_text_fallback` message)
  - Display in UI with "Audio unavailable" indicator
  - Mark turn as `tts_failed` in database
- [ ] Continue session normally (don't crash)

### 7.4 Database Connection Resilience
**Tasks:**
- [ ] Use SQLAlchemy connection pool with:
  - `pool_pre_ping=True` (validate connections)
  - `pool_size=10` (concurrent connections)
  - `max_overflow=5` (overflow pool)
  - `pool_recycle=3600` (recycle after 1 hour)
- [ ] Handle connection failures:
  - On write failure: Log locally, queue for retry
  - On read failure: Use in-memory session data
  - Don't block voice pipeline on DB issues
- [ ] Implement write queue with retry logic
- [ ] Add health check endpoint (`/health`) checking DB connection

### 7.5 WebSocket Resilience
**Tasks:**
- [ ] Client-side auto-reconnect (already implemented in Phase 2.6)
- [ ] Backend session cleanup:
  - On disconnect: Mark session end timestamp
  - Keep session data for 5 minutes (allow reconnect)
  - After 5 minutes: Purge in-memory session state
- [ ] Add heartbeat/ping-pong:
  - Backend sends ping every 30s
  - Client responds with pong
  - Detect stale connections, close after 60s no pong
- [ ] Handle browser refresh: Attempt to resume session (optional enhancement)

### 7.6 Audio Buffer Overflow Protection
**Tasks:**
- [ ] Implement circular buffer for audio chunks:
  - Max buffer size: 10 seconds of audio (~320KB at 16kHz mono)
  - On overflow: Drop oldest chunks (keep most recent)
  - Log `buffer_overflow` warning
- [ ] Add buffer usage metric to telemetry
- [ ] Monitor for memory leaks in audio buffers

---

## Phase 8: Testing & Validation (Days 15-16)

### 8.1 Unit Tests (pytest)
**Files to create:**
- `backend/tests/__init__.py`
- `backend/tests/test_state_machine.py`
- `backend/tests/test_transcript_buffer.py`
- `backend/tests/test_cancellation.py`
- `backend/tests/test_turn_controller.py`
- `backend/tests/conftest.py` - Pytest fixtures

**Tasks:**
- [ ] State Machine Tests:
  - Test all valid transitions
  - Test invalid transition rejection
  - Test state hooks (on_enter, on_exit)
- [ ] Transcript Buffer Tests:
  - Test partial/final merge logic
  - Test buffer locking
  - Test clear/reset
- [ ] Cancellation Tests:
  - Test correction marker detection
  - Test audio activity detection
  - Test cancel_event propagation
- [ ] Turn Controller Tests (mock external services):
  - Test full turn lifecycle (IDLE → LISTENING → SPECULATIVE → COMMITTED → SPEAKING → IDLE)
  - Test interruption handling
  - Test speculative cancellation
  - Test error scenarios

### 8.2 Integration Tests
**Files to create:**
- `backend/tests/test_integration.py`
- `backend/tests/test_websocket.py`

**Tasks:**
- [ ] Mock Deepgram/OpenAI/ElevenLabs APIs using `pytest-mock`
- [ ] Test WebSocket message flow:
  - Connect → session_ready
  - Send audio → transcript_partial → transcript_final
  - Trigger LLM → agent_audio_chunk
  - Test interruption message
- [ ] Test complete conversation scenario
- [ ] Test error recovery flows

### 8.3 End-to-End Tests
**Files to create:**
- `backend/tests/test_e2e.py`

**Tasks:**
- [ ] Use real API keys in test environment
- [ ] Test with sample audio files
- [ ] Verify complete turn cycle with real services
- [ ] Test interruption with overlapping audio
- [ ] Measure end-to-end latency

### 8.4 Load Testing (Optional but Recommended)
**Tasks:**
- [ ] Use `locust` or `pytest-benchmark` for load testing
- [ ] Test concurrent sessions (target: 50+ simultaneous connections)
- [ ] Monitor memory usage under load
- [ ] Monitor WebSocket connection stability
- [ ] Identify bottlenecks (CPU, memory, network)

### 8.5 Manual Testing Checklist
**Test scenarios:**
- [ ] Happy path: Complete turn without interruption
- [ ] Interruption: User speaks during agent response
- [ ] Correction markers: User says "actually, wait, sorry, no"
- [ ] Silence timeout: Various pause lengths
- [ ] Connection drop: Disconnect during turn, verify reconnect
- [ ] API failures: Simulate Deepgram/OpenAI/ElevenLabs errors
- [ ] Long conversation: 20+ turns, verify memory stability
- [ ] Settings changes: Adjust debounce, verify adaptive behavior
- [ ] Browser compatibility: Test in Chrome, Firefox, Safari, Edge

---

## Phase 9: Documentation & Deployment Prep (Days 17-18)

### 9.1 Code Documentation
**Tasks:**
- [ ] Add docstrings to all classes and functions:
  - Use Google-style or NumPy-style docstrings
  - Document parameters, return types, exceptions
  - Add usage examples for complex components
- [ ] Add inline comments for complex logic (especially in turn_controller.py)
- [ ] Generate API documentation using Sphinx (optional)

### 9.2 README Files
**Files to update/create:**
- `README.md` (root) - Project overview and quickstart
- `backend/README.md` - Backend setup and development
- `frontend/README.md` - Frontend setup and development

**Content:**
- [ ] Project description and architecture diagram
- [ ] Prerequisites (Python 3.11+, Node 18+)
- [ ] Environment setup instructions
- [ ] API key configuration (Deepgram, OpenAI, ElevenLabs, Neon Postgres)
- [ ] Installation steps (backend and frontend)
- [ ] Running development servers
- [ ] Running tests
- [ ] Project structure overview
- [ ] Contributing guidelines (if open source)

### 9.3 Environment Configuration
**Files to update:**
- `backend/.env.example`
- `frontend/.env.example`

**Backend environment variables:**
```
DEEPGRAM_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
ELEVENLABS_API_KEY=your_key_here
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Frontend environment variables:**
```
VITE_WEBSOCKET_URL=ws://localhost:8000/ws/voice
VITE_API_BASE_URL=http://localhost:8000
```

### 9.4 Logging Configuration
**Tasks:**
- [ ] Set up structured logging with Python `logging` module
- [ ] Log levels by component:
  - INFO: State transitions, turn events, API calls
  - DEBUG: Transcript updates, token streaming, audio chunks
  - WARNING: Cancellations, retries, buffer overflows
  - ERROR: API failures, connection errors, exceptions
- [ ] Log to console (development) and file (production)
- [ ] Add request ID to all logs for tracing
- [ ] Implement log rotation (max size 100MB, keep 5 files)

### 9.5 Deployment Configuration
**Files to create:**
- `backend/Dockerfile` - Backend containerization
- `frontend/Dockerfile` - Frontend containerization
- `docker-compose.yml` - Local multi-container setup
- `.dockerignore` - Exclude unnecessary files

**Tasks:**
- [ ] Create production-ready Dockerfile for backend:
  - Multi-stage build (build + runtime)
  - Use Python 3.11 slim image
  - Install dependencies first (layer caching)
  - Run as non-root user
  - Health check endpoint
- [ ] Create production-ready Dockerfile for frontend:
  - Build optimized production bundle
  - Serve with nginx
  - Gzip compression enabled
- [ ] Docker Compose for local development (backend + frontend + postgres)
- [ ] Add deployment instructions for common platforms (Render, Railway, Heroku, AWS)

### 9.6 Performance Optimization
**Tasks:**
- [ ] Backend optimizations:
  - Use uvloop for faster asyncio (install `uvloop`)
  - Enable FastAPI response caching for static endpoints
  - Optimize database queries (add indexes)
  - Connection pooling for external APIs
- [ ] Frontend optimizations:
  - Code splitting (lazy load components)
  - Memoize expensive computations (React.memo)
  - Use Web Workers for audio processing (optional)
  - Minify and compress assets
- [ ] Network optimizations:
  - Use binary WebSocket frames for audio (instead of base64)
  - Compress WebSocket messages (if supported)
  - CDN for frontend assets (production)

---

## Phase 10: Final Testing & MVP Launch (Days 19-20)

### 10.1 User Acceptance Testing
**Tasks:**
- [ ] Recruit 3-5 test users for feedback
- [ ] Prepare test scenarios and instructions
- [ ] Observe users interacting with the system
- [ ] Collect feedback on:
  - Response latency (acceptable?)
  - Interruption handling (natural?)
  - Transcription accuracy
  - Audio quality
  - UI clarity and usability
- [ ] Document issues and prioritize fixes

### 10.2 Bug Fixes & Polish
**Tasks:**
- [ ] Fix critical bugs from UAT
- [ ] Address UI/UX feedback
- [ ] Improve error messages for clarity
- [ ] Add loading states and animations
- [ ] Optimize performance bottlenecks

### 10.3 Security Review
**Tasks:**
- [ ] Ensure API keys not exposed in frontend
- [ ] Validate all WebSocket messages (prevent injection)
- [ ] Add CORS whitelist for production
- [ ] Review database queries for SQL injection (use parameterized queries)
- [ ] Add input validation and sanitization
- [ ] Implement basic DOS protection (connection limits, message size limits)

### 10.4 Monitoring Setup (Production)
**Tasks:**
- [ ] Set up error tracking (Sentry, Rollbar, or similar)
- [ ] Add application performance monitoring (APM)
- [ ] Configure database monitoring
- [ ] Set up log aggregation (Datadog, Logtail, or similar)
- [ ] Create alerts for critical issues:
  - API failures
  - High error rates
  - Database connection issues
  - High latency

### 10.5 Launch Checklist
**Pre-launch:**
- [ ] All tests passing (unit, integration, E2E)
- [ ] Documentation complete and reviewed
- [ ] Environment variables configured for production
- [ ] Database migrations applied
- [ ] SSL certificates configured (HTTPS/WSS)
- [ ] Monitoring and alerting active
- [ ] Backup strategy in place (database)

**Launch:**
- [ ] Deploy backend to production server
- [ ] Deploy frontend to hosting platform
- [ ] Verify WebSocket connectivity
- [ ] Test with production API keys
- [ ] Smoke test all critical flows
- [ ] Monitor for errors in first hour

**Post-launch:**
- [ ] Monitor metrics (latency, cancellation rate, errors)
- [ ] Collect user feedback
- [ ] Plan iteration 1 features

---

## Success Criteria

### Functional Requirements
- ✅ User can speak and receive transcriptions in real-time
- ✅ Agent responds with one complete answer per user turn
- ✅ User can interrupt agent at any time (barge-in works)
- ✅ System never speaks incorrect intent out loud
- ✅ Speculative execution prevents false starts
- ✅ State machine enforces deterministic turn control
- ✅ All conversations persisted to database
- ✅ Telemetry tracked and displayed in UI
- ✅ Settings managed via UI (no code changes needed)

### Performance Requirements
- ✅ Turn latency < 1000ms (speech end to first audio)
- ✅ Interruption response < 200ms (audio stops immediately)
- ✅ Supports 50+ concurrent sessions
- ✅ 99.9% uptime (excluding external API downtime)
- ✅ Graceful error recovery for all external services

### Code Quality Requirements
- ✅ All core logic covered by unit tests (>80% coverage)
- ✅ Integration tests for critical paths
- ✅ Comprehensive docstrings and comments
- ✅ Clean code structure following PRD architecture
- ✅ No hardcoded credentials (all in environment variables)

---

## Timeline Summary

| Phase | Days | Description |
|-------|------|-------------|
| 1 | 1-2 | Core infrastructure & project setup |
| 2 | 3-4 | STT integration & transcript management |
| 3 | 5-6 | LLM integration & turn control |
| 4 | 7-8 | TTS integration & audio playback |
| 5 | 9-10 | Telemetry & adaptive behavior |
| 6 | 11-12 | UI polish & user experience |
| 7 | 13-14 | Error recovery & resilience |
| 8 | 15-16 | Testing & validation |
| 9 | 17-18 | Documentation & deployment prep |
| 10 | 19-20 | Final testing & MVP launch |

**Total: 20 working days (4 weeks)**

---

## Next Steps

1. **Set up development environment**
   - Install Python 3.11+, Node 18+
   - Create Neon Postgres database
   - Obtain API keys (Deepgram, OpenAI, ElevenLabs)

2. **Initialize repositories**
   - Create Git repository
   - Set up GitHub/GitLab (if applicable)
   - Create initial branch structure

3. **Start Phase 1**
   - Create project folders
   - Install dependencies
   - Build core infrastructure

4. **Daily progress tracking**
   - Complete tasks in order
   - Mark checkboxes as done
   - Update plan if blockers found

**Ready to begin implementation!**
