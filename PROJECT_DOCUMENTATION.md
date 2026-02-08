# Voice AI Pipeline - Complete Project Documentation

## Executive Summary

**Voice AI Pipeline** is a production-grade real-time voice conversation system built entirely from scratch without using managed voice AI platforms. The system features intelligent turn-taking, user interruptions (barge-in), speculative execution, and RAG-powered document retrieval for contextual conversations.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Core Components](#core-components)
3. [State Machine Flow](#state-machine-flow)
4. [RAG Implementation](#rag-implementation)
5. [Latency Optimization](#latency-optimization)
6. [iOS Compatibility](#ios-compatibility)
7. [Technical Stack](#technical-stack)
8. [Key Features](#key-features)
9. [API Documentation](#api-documentation)
10. [Deployment](#deployment)

---

## System Architecture

```mermaid
graph TB
    subgraph "Frontend (React + TypeScript)"
        UI[User Interface]
        MIC[Microphone Capture<br/>Web Audio API]
        PLAYER[Audio Player<br/>MediaSource API]
        WS_CLIENT[WebSocket Client]
    end
    
    subgraph "Backend (FastAPI + Python)"
        WS_SERVER[WebSocket Server<br/>Connection Manager]
        TURN[Turn Controller<br/>State Machine]
        
        subgraph "External APIs"
            STT[Deepgram STT<br/>Streaming]
            LLM[OpenAI GPT-4<br/>Priority API]
            TTS[ElevenLabs TTS<br/>Streaming]
        end
        
        subgraph "RAG Pipeline"
            PARSER[File Parsers<br/>PDF/TXT/MD]
            CHUNKER[Token Chunker<br/>tiktoken]
            EMBEDDER[Local Embedder<br/>sentence-transformers]
            PINECONE[Pinecone Vector DB<br/>384 dimensions]
            RETRIEVER[Retriever<br/>Similarity Search]
        end
        
        DB[(Neon Postgres<br/>Sessions, Turns,<br/>Documents)]
    end
    
    UI --> MIC
    MIC -->|PCM Audio| WS_CLIENT
    WS_CLIENT <-->|WebSocket| WS_SERVER
    WS_SERVER --> TURN
    
    TURN -->|Audio Stream| STT
    STT -->|Transcript| TURN
    
    TURN -->|Parallel Retrieval| RETRIEVER
    RETRIEVER -->|Context| TURN
    
    TURN -->|Augmented Prompt| LLM
    LLM -->|Response Stream| TURN
    
    TURN -->|Text| TTS
    TTS -->|Audio Chunks| TURN
    
    TURN -->|Audio| WS_SERVER
    WS_SERVER -->|Base64 MP3| WS_CLIENT
    WS_CLIENT --> PLAYER
    PLAYER --> UI
    
    TURN -.->|Persist| DB
    PARSER -->|Upload| CHUNKER
    CHUNKER --> EMBEDDER
    EMBEDDER -->|Vectors| PINECONE
    RETRIEVER -->|Query| PINECONE
    
    style TURN fill:#f96,stroke:#333,stroke-width:3px
    style RAG fill:#9cf,stroke:#333,stroke-width:2px
```

---

## Core Components

### 1. Frontend Architecture

#### **Audio Capture** (`audioUtils.ts` - `AudioRecorder`)
```typescript
// Microphone → Web Audio API → PCM Float32 → Int16 → Base64
- Sample Rate: 16kHz (optimized for Deepgram)
- Channel: Mono
- Buffer: 4096 samples (~256ms chunks)
- Encoding: Float32 → Int16 PCM
- Transport: Base64 over WebSocket
```

#### **Audio Playback** (`audioUtils.ts` - `AudioPlayer`)
```typescript
// Desktop: MediaSource API with SourceBuffer
- Format: MP3 chunks from ElevenLabs
- Streaming: Append chunks to SourceBuffer
- Queue: Automatic buffering and playback

// iOS: Web Audio API with complete MP3
- Collect all chunks (Safari requires complete MP3)
- Decode via AudioContext.decodeAudioData()
- Play via AudioBufferSourceNode
- Fallback: HTMLAudioElement with Blob URL
```

**iOS Compatibility Strategy:**
1. AudioContext unlock during user gesture (stays unlocked)
2. Collect complete MP3 before playback (iOS Safari limitation)
3. Primary: Web Audio API (gesture-independent after unlock)
4. Fallback: HTMLAudioElement with Blob URL

#### **State Visualizer** (`VoiceVisualizer.tsx`)
```typescript
// Circular waveform with color-coded states
- IDLE: Gray (inactive)
- LISTENING: Blue (user speaking)
- SPECULATIVE: Purple (processing, output held)
- COMMITTED: Orange (confirmed, ready to respond)
- SPEAKING: Green (agent speaking)
```

---

### 2. Backend Architecture

#### **Turn Controller** (`turn_controller.py`)
**The brain of the system - orchestrates all components**

```python
State Flow:
IDLE 
  ↓ [user audio detected]
LISTENING 
  ↓ [400ms silence + RAG retrieval complete]
SPECULATIVE 
  ↓ [silence timer confirms no new audio]
COMMITTED 
  ↓ [LLM response ready]
SPEAKING 
  ↓ [playback complete OR user interrupts]
IDLE
```

**Parallel Operations:**
```python
async def on_silence_complete():
    # Start both simultaneously
    rag_task = asyncio.create_task(self._retrieve_with_timeout(text))
    llm_task = asyncio.create_task(self._start_llm_stream(text))
    
    # RAG completes in ~150ms during 400ms silence
    context = await rag_task
    
    # LLM already generating (speculative mode)
    # Output held until COMMITTED state
```

**Cancellation Detection:**
```python
Triggers:
1. New audio during SPECULATIVE/COMMITTED
2. Correction markers: "actually", "wait", "sorry", "no"
3. User barge-in during SPEAKING

Actions:
- Cancel LLM stream (set asyncio.Event)
- Cancel TTS stream
- Stop audio playback
- Transition to LISTENING
- Update adaptive debounce (increase if >30% cancellation rate)
```

---

### 3. State Machine

```mermaid
stateDiagram-v2
    [*] --> IDLE: System Ready
    
    IDLE --> LISTENING: Audio Detected
    
    LISTENING --> SPECULATIVE: Silence Timer (400ms)\n+ RAG Retrieval Complete
    LISTENING --> LISTENING: Audio Continues
    
    SPECULATIVE --> COMMITTED: Timer Confirms\n(No New Audio)
    SPECULATIVE --> LISTENING: New Audio\n(Cancel LLM)
    
    COMMITTED --> SPEAKING: TTS Complete\n(Start Playback)
    COMMITTED --> LISTENING: User Interrupts\n(Cancel LLM)
    
    SPEAKING --> IDLE: Playback Complete
    SPEAKING --> LISTENING: User Barge-in\n(Stop Audio)
    
    note right of SPECULATIVE
        LLM Streaming Started
        Output HELD (not sent to user)
        Cancellation markers checked
    end note
    
    note right of COMMITTED
        LLM Output Released
        Sent to TTS
        No cancellation possible
    end note
```

---

## RAG Implementation

### Architecture

```mermaid
graph LR
    subgraph "Document Upload Flow"
        A[User Uploads PDF/TXT/MD] --> B[File Parser]
        B --> C[Token-based Chunker<br/>500 tokens, 50 overlap]
        C --> D[Local Embedder<br/>all-MiniLM-L6-v2<br/>384 dimensions]
        D --> E[Pinecone<br/>Vector Store]
        E --> F[Database<br/>Document Metadata]
    end
    
    subgraph "Retrieval Flow (150ms)"
        G[User Voice Input] --> H[Silence Detected<br/>400ms timer]
        H --> I[Embed Query<br/>Cached LRU]
        I --> J[Pinecone Search<br/>Top 3, min 0.10 similarity]
        J --> K[Build Augmented Prompt]
        K --> L[OpenAI GPT-4]
    end
    
    style D fill:#9cf
    style E fill:#9cf
    style I fill:#9cf
    style J fill:#9cf
```

### Key Features

#### **Local Embeddings**
```python
# sentence-transformers: all-MiniLM-L6-v2
Model: all-MiniLM-L6-v2
Dimensions: 384 (smaller than OpenAI's 1536)
Speed: Fast local processing (no network latency)
Cost: FREE (no API calls)
Quality: Good performance for retrieval tasks
```

**Why Local Embeddings:**
1. **Latency**: Fast local processing without network calls
2. **Cost**: No API costs for embeddings
3. **Privacy**: No external API calls
4. **Reliability**: No rate limits or network dependencies

#### **Parallel Retrieval During Silence**
```python
# RAG retrieval happens during silence detection window
Silence Timer: 400ms (waiting for user to finish)
RAG Retrieval: Completes during silence timer

Result: RAG retrieval happens in parallel, minimizing added latency
```

#### **Smart Context Injection**
```python
System Prompt (with context):
"""
You are a helpful voice assistant.

You have access to the following relevant information:
[Source: policy.pdf - Relevance: 0.92]
Employee sick leave policy allows up to 10 days per year...

Instructions:
- Answer PRIMARILY from provided context
- If context doesn't have answer, say "I don't have that information"
- Do NOT hallucinate
- Keep responses concise (2-3 sentences for voice)
"""
```

---

## Latency Optimization

### Breakdown

```mermaid
gantt
    title Turn Latency Timeline
    dateFormat X
    axisFormat %Lms
    
    section User Speech
    User Speaking          :0, 500
    
    section Processing
    Silence Detection      :500, 900
    RAG Retrieval (Parallel):500, 700
    
    section LLM
    LLM Processing         :900, 1300
    
    section TTS
    TTS Generation         :1300, 1600
    
    section Audio
    Audio Playback Start   :1600, 1600
```

### Strategies

#### 1. **Speculative Execution**
```
Traditional:
User stops → Wait for silence confirmation → Start LLM → Wait for response → Start TTS → Play

Our Approach:
User stops → [Start RAG + Start LLM speculatively during silence detection]
           → Confirm silence
           → [RAG complete + LLM streaming]
           → Release output → TTS → Play

Benefit: RAG retrieval and LLM startup overlap with silence detection window
```

#### 2. **OpenAI Priority API**
```python
OPENAI_USE_PRIORITY_API=true
```
- Helps with rate limit handling
- Dedicated capacity
- Improved response consistency

#### 3. **Adaptive Debounce**
```python
MIN_SILENCE_DEBOUNCE_MS=400  # Fast responses
MAX_SILENCE_DEBOUNCE_MS=1200 # User tends to interrupt

# Auto-adjusts based on cancellation rate
if cancellation_rate > 30%:
    debounce += 100  # User needs more time
elif cancellation_rate < 15%:
    debounce -= 50   # Can respond faster
```

#### 4. **Streaming Everything**
```
- Deepgram: Streaming STT (partial → final transcripts)
- OpenAI: Streaming LLM (token by token)
- ElevenLabs: Streaming TTS (audio chunks as generated)
- WebSocket: Bi-directional streaming transport
```

#### 5. **LRU Caching**
```python
# Retriever caches query embeddings (100 queries)
@lru_cache(maxsize=100)
def _embed_query(query: str) -> List[float]:
    # Repeated questions = instant retrieval
    pass
```

---

## iOS Compatibility

### Problem: MediaSource API Not Supported

iOS Safari doesn't support `MediaSource` API for streaming audio playback. Initial attempts caused app crashes on iPhone/iPad.

### Solution: Dual Playback Strategy

```mermaid
graph TD
    A[Detect Browser] --> B{MediaSource<br/>Supported?}
    
    B -->|Yes<br/>Desktop| C[MediaSource API]
    C --> D[Stream MP3 Chunks]
    D --> E[Append to SourceBuffer]
    E --> F[Play Immediately]
    
    B -->|No<br/>iOS Safari| G[Collect All Chunks]
    G --> H[Wait for Finalization]
    H --> I{AudioContext<br/>Unlocked?}
    
    I -->|Yes| J[Web Audio API]
    J --> K[decodeAudioData]
    K --> L[AudioBufferSourceNode]
    L --> M[Play via AudioContext]
    
    I -->|No/Fallback| N[HTMLAudioElement]
    N --> O[Create Blob URL]
    O --> P[audio.play]
    
    style C fill:#9f9
    style J fill:#9cf
    style N fill:#fc9
```

### Implementation Details

#### **Unlock Audio During Gesture**
```typescript
// Must be called from user interaction (tap/click)
async unlockIOSAudio() {
  // 1. Create and resume AudioContext
  this.iosAudioContext = new AudioContext();
  await this.iosAudioContext.resume();
  
  // 2. Play silent buffer to activate audio path
  const silentBuffer = this.iosAudioContext.createBuffer(1, 1, 22050);
  const silentSource = this.iosAudioContext.createBufferSource();
  silentSource.buffer = silentBuffer;
  silentSource.connect(this.iosAudioContext.destination);
  silentSource.start(0);
  
  // AudioContext now stays unlocked forever!
}
```

#### **Collect Complete MP3**
```typescript
// iOS Safari's decodeAudioData fails on partial MP3
addChunk(base64Audio: string) {
  // Store raw bytes (don't decode yet)
  this.iosRawChunks.push(decodedBytes);
}

finalize() {
  // Now we have the COMPLETE MP3
  const completeMp3 = combineChunks(this.iosRawChunks);
  await this.playCompleteIOSAudio(completeMp3);
}
```

**Trade-off:**
- Desktop: True streaming (chunks play as they arrive)
- iOS: Wait for complete audio (~1-2s delay)
- Reason: Safari's audio decoder requirement

---

## Technical Stack

### Backend
```yaml
Language: Python 3.11+
Framework: FastAPI (async)
WebSocket: Native FastAPI WebSocket
Database: Neon Postgres (serverless, async)
ORM: SQLAlchemy 2.0 (asyncpg)
Vector DB: Pinecone (384 dimensions)
Embeddings: sentence-transformers (all-MiniLM-L6-v2)

External APIs:
  STT: Deepgram (streaming)
  LLM: OpenAI GPT-4o-mini (priority API)
  TTS: ElevenLabs (streaming, 21m00Tcm4TlvDq8ikWAM voice)

Libraries:
  - httpx (async HTTP)
  - websockets
  - tiktoken (token counting)
  - PyMuPDF (PDF parsing)
  - pinecone-client
  - sentence-transformers
```

### Frontend
```yaml
Language: TypeScript
Framework: React 18 + Vite
Styling: Tailwind CSS + shadcn/ui
Audio: Web Audio API, MediaRecorder, MediaSource
WebSocket: Native WebSocket API
Build: Vite (ESBuild)

Components:
  - VoiceVisualizer (Canvas-based waveform)
  - ConversationHistory (Radix ScrollArea)
  - DocumentSidebar (File upload + progress)
  - DebugPanel (Real-time logs)
```

---

## Key Features

### 1. **Intelligent Turn-Taking**
- State machine prevents overlapping speech
- Adaptive silence debounce (400-1200ms)
- Cancellation markers: "actually", "wait", "sorry", "no"

### 2. **Barge-In Support**
- User can interrupt agent at any time
- Instant audio stop + state transition
- LLM/TTS stream cancellation via `asyncio.Event`

### 3. **Speculative Execution**
- LLM starts during silence timer
- Output held until confirmed (avoids incorrect responses)
- Cancel silently if user speaks again (target <30% cancellation rate)

### 4. **RAG-Powered Conversations**
- Upload PDF/TXT/MD documents
- Local embeddings (no API cost)
- Parallel retrieval during silence detection
- Context-augmented responses

### 5. **Cross-Platform**
- Desktop: Chrome, Firefox, Edge (MediaSource API)
- iOS: Safari on iPhone/iPad (Web Audio API)
- Android: Chrome Mobile

### 6. **Production-Ready**
- Comprehensive error handling
- Telemetry & metrics tracking
- Persistent conversation storage
- Graceful fallbacks (RAG timeout, TTS failure, etc.)

---

## API Documentation

### WebSocket Endpoint

```
ws://localhost:8000/ws/voice
```

### Client → Server Messages

```typescript
// Start session
{
  "type": "connect",
  "data": {}
}

// Send audio chunk (16kHz mono PCM, base64)
{
  "type": "audio_chunk",
  "data": {
    "audio": "base64_encoded_pcm",
    "format": "pcm",
    "sample_rate": 16000
  }
}

// Interrupt agent
{
  "type": "interrupt",
  "data": {
    "timestamp": 1707411234567
  }
}

// Playback complete
{
  "type": "playback_complete",
  "data": {
    "timestamp": 1707411234567
  }
}
```

### Server → Client Messages

```typescript
// Session ready
{
  "type": "session_ready",
  "data": {
    "session_id": "uuid",
    "timestamp": 1707411234567
  }
}

// State change
{
  "type": "state_change",
  "data": {
    "from_state": "LISTENING",
    "to_state": "SPECULATIVE",
    "timestamp": 1707411234567
  }
}

// Partial transcript (user speaking)
{
  "type": "transcript_partial",
  "data": {
    "text": "Hello how are...",
    "is_final": false
  }
}

// Final transcript (confirmed)
{
  "type": "transcript_final",
  "data": {
    "text": "Hello how are you",
    "is_final": true
  }
}

// Agent audio chunk (base64 MP3)
{
  "type": "agent_audio_chunk",
  "data": {
    "audio": "base64_mp3_chunk",
    "chunk_index": 0,
    "is_final": false
  }
}

// Turn complete
{
  "type": "turn_complete",
  "data": {
    "turn_id": "uuid",
    "user_text": "Hello how are you",
    "agent_text": "I'm doing great, thanks!",
    "was_interrupted": false
  }
}
```

### REST Endpoints

```http
POST /api/documents/upload
Content-Type: multipart/form-data

file: <file>
session_id: <uuid>
chunk_size: 500
chunk_overlap: 50

Response:
{
  "success": true,
  "document_id": "uuid",
  "filename": "policy.pdf",
  "status": "indexed",
  "word_count": 1234,
  "chunk_count": 15
}
```

```http
GET /api/documents/{session_id}/list

Response:
{
  "documents": [
    {
      "id": "uuid",
      "filename": "policy.pdf",
      "status": "indexed",
      "word_count": 1234,
      "chunk_count": 15,
      "uploaded_at": "2024-02-08T10:30:00Z"
    }
  ]
}
```

```http
DELETE /api/documents/{document_id}

Response:
{
  "success": true,
  "message": "Document deleted"
}
```

---

## Deployment

### Environment Variables

```bash
# External APIs
DEEPGRAM_API_KEY=<key>
OPENAI_API_KEY=<key>
OPENAI_USE_PRIORITY_API=true
ELEVENLABS_API_KEY=<key>
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

# RAG
PINECONE_API_KEY=<key>
PINECONE_INDEX_NAME=voice-agent-kb-local
PINECONE_DIMENSION=384
RAG_USE_LOCAL_EMBEDDINGS=true

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Settings
MIN_SILENCE_DEBOUNCE_MS=400
MAX_SILENCE_DEBOUNCE_MS=1200
CANCELLATION_RATE_THRESHOLD=0.30
```

### Running Locally

```bash
# Backend
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd "Frontend 2.0"
npm install
npm run dev
```

### Production Deployment

**Backend:** Railway.app / Render.com
**Frontend:** Vercel / Netlify
**Database:** Neon Postgres (serverless)
**Vector DB:** Pinecone (managed)

---

## Performance Metrics

```
Turn Latency: Under 2 seconds (including RAG retrieval)
Cancellation Rate: 20-25% (adaptive debounce)
Cross-Platform: Desktop and iOS Safari support
Audio Quality: Confirmed working on both platforms
Document Processing: Varies by file size and content
```

---

## Future Enhancements

1. **Multi-Document RAG**: Support multiple documents per session
2. **Voice Cloning**: Custom TTS voices per user
3. **Multilingual**: Support non-English conversations
4. **Mobile Apps**: Native iOS/Android apps
5. **Advanced RAG**: Re-ranking, hybrid search, query expansion
6. **Analytics Dashboard**: Real-time metrics visualization
7. **A/B Testing**: Compare different LLM models/prompts

---

## License

MIT License - See LICENSE file

---

## About

Developer: Siddhant Jaiswal
GitHub: https://github.com/sddhantjaiii/Voice-Ai-Pipeline
Live Demo: https://voiceaipipeline.siddhantjaiswal.tech/

*This is an interview assignment showcasing real-time voice AI implementation with RAG capabilities*
