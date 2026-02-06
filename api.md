# API Documentation: Third-Party Services & WebSocket Protocol

## Overview

This document provides comprehensive documentation for all third-party APIs and custom WebSocket protocols used in the Voice AI Pipeline project. **Always refer to this document when integrating or working with external services.**

---

## Table of Contents

1. [WebSocket Protocol (Frontend ↔ Backend)](#websocket-protocol)
2. [Deepgram API (Speech-to-Text)](#deepgram-api)
3. [OpenAI API (Language Model)](#openai-api)
4. [ElevenLabs API (Text-to-Speech)](#elevenlabs-api)
5. [Error Codes Reference](#error-codes-reference)

---

## WebSocket Protocol

### Connection Endpoint

**URL:** `ws://localhost:8000/ws/voice` (development)  
**URL:** `wss://your-domain.com/ws/voice` (production)

### Connection Lifecycle

1. **Client connects** → Backend accepts and creates session
2. **Backend sends** `session_ready` message with session ID
3. **Bidirectional messaging** for audio, transcripts, state changes
4. **Client disconnects** → Backend cleans up session after 5 minutes

### Heartbeat (Ping-Pong)

- Backend sends `ping` every 30 seconds
- Client must respond with `pong` within 60 seconds
- Connection closed if no pong received

---

## Message Schemas

### Client → Server Messages

#### 1. Connect Message
**Sent on:** Initial connection  
**Purpose:** Handshake to establish session

```json
{
  "type": "connect",
  "data": {}
}
```

**Response:** `session_ready` message

---

#### 2. Audio Chunk Message
**Sent on:** Microphone audio captured  
**Purpose:** Stream user audio to backend for STT

```json
{
  "type": "audio_chunk",
  "data": {
    "audio": "base64_encoded_audio_data",
    "format": "wav",
    "sample_rate": 16000
  }
}
```

**Fields:**
- `audio` (string): Base64-encoded audio data
- `format` (string): Audio format - `"wav"`, `"webm"`, or `"pcm"`
- `sample_rate` (integer): Sample rate in Hz (recommended: 16000)

**Notes:**
- Send chunks frequently (every 100-250ms) for real-time processing
- Use 16kHz, mono, 16-bit PCM for best compatibility
- Maximum chunk size: 100KB

---

#### 3. Interrupt Message
**Sent on:** User wants to interrupt agent  
**Purpose:** Trigger barge-in, cancel agent speech

```json
{
  "type": "interrupt",
  "data": {
    "timestamp": 1707264000000
  }
}
```

**Fields:**
- `timestamp` (integer): Unix timestamp in milliseconds

**Effect:**
- Backend transitions SPEAKING → LISTENING
- Cancels active TTS and LLM streams
- Clears transcript buffer
- Logs interrupted turn

---

#### 4. Update Settings Message
**Sent on:** User changes settings in UI  
**Purpose:** Update backend configuration in real-time

```json
{
  "type": "update_settings",
  "data": {
    "silence_debounce_ms": 500,
    "cancellation_threshold": 0.28,
    "adaptive_debounce_enabled": true,
    "voice_id": "21m00Tcm4TlvDq8ikWAM",
    "llm_model": "gpt-4-turbo-preview"
  }
}
```

**Fields:**
- `silence_debounce_ms` (integer, optional): 400-1200
- `cancellation_threshold` (float, optional): 0.1-0.5
- `adaptive_debounce_enabled` (boolean, optional)
- `voice_id` (string, optional): ElevenLabs voice ID
- `llm_model` (string, optional): OpenAI model name

---

#### 5. Disconnect Message
**Sent on:** User closes connection  
**Purpose:** Clean disconnect

```json
{
  "type": "disconnect",
  "data": {}
}
```

**Effect:**
- Backend ends session
- Stores session end timestamp
- Cleans up resources

---

### Server → Client Messages

#### 1. Session Ready Message
**Sent on:** Successful connection  
**Purpose:** Confirm session created

```json
{
  "type": "session_ready",
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": 1707264000000
  }
}
```

**Fields:**
- `session_id` (string): UUID of created session
- `timestamp` (integer): Unix timestamp in milliseconds

---

#### 2. State Change Message
**Sent on:** State machine transition  
**Purpose:** Inform frontend of current state

```json
{
  "type": "state_change",
  "data": {
    "from_state": "LISTENING",
    "to_state": "SPECULATIVE",
    "timestamp": 1707264000000
  }
}
```

**Fields:**
- `from_state` (string): Previous state
- `to_state` (string): New state - `"IDLE"`, `"LISTENING"`, `"SPECULATIVE"`, `"COMMITTED"`, `"SPEAKING"`
- `timestamp` (integer): Unix timestamp

**States:**
- **IDLE**: No activity
- **LISTENING**: Receiving user audio
- **SPECULATIVE**: Silence detected, LLM may be running (hidden)
- **COMMITTED**: User intent confirmed, LLM output can surface
- **SPEAKING**: Agent is speaking

---

#### 3. Transcript Partial Message
**Sent on:** Deepgram sends interim transcript  
**Purpose:** Show real-time transcription (UI only)

```json
{
  "type": "transcript_partial",
  "data": {
    "text": "Book a flight to",
    "confidence": 0.92,
    "timestamp": 1707264000000
  }
}
```

**Fields:**
- `text` (string): Partial transcript text
- `confidence` (float): 0.0-1.0
- `timestamp` (integer): Unix timestamp

**Note:** Partial transcripts are NOT sent to LLM, display only.

---

#### 4. Transcript Final Message
**Sent on:** Deepgram sends final transcript  
**Purpose:** Confirm finalized user speech

```json
{
  "type": "transcript_final",
  "data": {
    "text": "Book a flight to Bangalore tomorrow morning",
    "confidence": 0.95,
    "timestamp": 1707264000000
  }
}
```

**Fields:**
- `text` (string): Final transcript text
- `confidence` (float): 0.0-1.0
- `timestamp` (integer): Unix timestamp

**Note:** Final transcript triggers silence debounce timer.

---

#### 5. Agent Audio Chunk Message
**Sent on:** TTS generates audio chunk  
**Purpose:** Stream agent audio to frontend for playback

```json
{
  "type": "agent_audio_chunk",
  "data": {
    "audio": "base64_encoded_audio_data",
    "chunk_index": 0,
    "is_final": false
  }
}
```

**Fields:**
- `audio` (string): Base64-encoded audio data
- `chunk_index` (integer): Sequential index for ordering
- `is_final` (boolean): True if last chunk

**Usage:**
- Decode base64 to ArrayBuffer
- Convert to AudioBuffer via AudioContext
- Play via Web Audio API

---

#### 6. Agent Text Fallback Message
**Sent on:** TTS fails, text-only response  
**Purpose:** Display agent response as text when audio unavailable

```json
{
  "type": "agent_text_fallback",
  "data": {
    "text": "I'll help you book a flight to Bangalore for tomorrow morning. Let me check available options.",
    "reason": "tts_failed"
  }
}
```

**Fields:**
- `text` (string): Agent response text
- `reason` (string): Failure reason

---

#### 7. Turn Complete Message
**Sent on:** Turn finished successfully  
**Purpose:** Log turn in history, update UI

```json
{
  "type": "turn_complete",
  "data": {
    "turn_id": "650e8400-e29b-41d4-a716-446655440001",
    "user_text": "Book a flight to Bangalore tomorrow morning",
    "agent_text": "I'll help you book a flight to Bangalore for tomorrow morning. Let me check available options.",
    "duration_ms": 1250,
    "was_interrupted": false,
    "timestamp": 1707264000000
  }
}
```

**Fields:**
- `turn_id` (string): UUID of turn
- `user_text` (string): User transcript
- `agent_text` (string): Agent response
- `duration_ms` (integer): Turn duration
- `was_interrupted` (boolean): True if user interrupted
- `timestamp` (integer): Unix timestamp

---

#### 8. Telemetry Message
**Sent on:** Every 5 turns or on request  
**Purpose:** Update metrics in UI

```json
{
  "type": "telemetry",
  "data": {
    "cancellation_rate": 0.28,
    "avg_debounce_ms": 450,
    "turn_latency_ms": 890,
    "total_turns": 12,
    "tokens_wasted": 145,
    "interruption_count": 3
  }
}
```

**Fields:**
- `cancellation_rate` (float): 0.0-1.0
- `avg_debounce_ms` (integer): Current average debounce
- `turn_latency_ms` (integer): Avg latency from speech end to first audio
- `total_turns` (integer): Total completed turns
- `tokens_wasted` (integer): Tokens from canceled LLM calls
- `interruption_count` (integer): Number of barge-ins

---

#### 9. Error Message
**Sent on:** Error occurs  
**Purpose:** Notify frontend of issues

```json
{
  "type": "error",
  "data": {
    "code": "STT_CONNECTION_FAILED",
    "message": "Deepgram connection lost. Attempting to reconnect...",
    "recoverable": true,
    "timestamp": 1707264000000
  }
}
```

**Fields:**
- `code` (string): Error code (see Error Codes section)
- `message` (string): Human-readable error message
- `recoverable` (boolean): True if system can recover automatically
- `timestamp` (integer): Unix timestamp

---

#### 10. Ping Message
**Sent on:** Every 30 seconds  
**Purpose:** Keep connection alive

```json
{
  "type": "ping",
  "data": {}
}
```

**Response:** Client should send `pong` message

---

## Deepgram API

### Overview

**Service:** Real-time speech-to-text  
**Docs:** https://developers.deepgram.com/docs  
**Pricing:** Pay-per-use, ~$0.0125 per minute

### Authentication

**Method:** API Key in Authorization header

```python
from deepgram import Deepgram

dg_client = Deepgram(api_key="YOUR_API_KEY")
```

### Streaming Connection

**Endpoint:** `wss://api.deepgram.com/v1/listen`

**Configuration:**
```python
connection = await dg_client.transcription.live({
    'punctuate': True,           # Add punctuation
    'interim_results': True,     # Send partial transcripts
    'endpointing': 400,          # Silence detection (ms)
    'language': 'en-US',         # Language
    'model': 'nova-2',           # Model (nova-2 = latest)
    'smart_format': True         # Auto-format numbers, dates
})
```

### Event Handlers

#### Transcript Received
```python
async def on_transcript(self, transcript):
    is_final = transcript['is_final']
    text = transcript['channel']['alternatives'][0]['transcript']
    confidence = transcript['channel']['alternatives'][0]['confidence']
    
    if is_final:
        # Handle final transcript
        await handle_final(text, confidence)
    else:
        # Handle partial transcript
        await handle_partial(text, confidence)
```

#### Connection Events
```python
async def on_open(self):
    print("Deepgram connection opened")

async def on_close(self):
    print("Deepgram connection closed")

async def on_error(self, error):
    print(f"Deepgram error: {error}")
```

### Sending Audio

**Format:** Raw audio bytes (PCM, WAV, etc.)

```python
await connection.send(audio_chunk)
```

**Recommended Settings:**
- Sample rate: 16kHz
- Channels: Mono (1 channel)
- Bit depth: 16-bit
- Chunk size: 100-250ms (~3200-8000 bytes at 16kHz)

### Error Handling

**Connection Failures:**
- Implement exponential backoff: 0s, 1s, 2s, 4s, 8s
- Max attempts: 5
- Buffer audio during outage (max 5s)
- Send buffered audio if < 3s old on reconnect

**Rate Limits:**
- Concurrent connection limit (check your plan)
- Audio data rate limit
- Handle `429 Too Many Requests`

### Best Practices

1. **Keep connection alive:** Send audio regularly (every 5s minimum)
2. **Close properly:** Call `connection.finish()` when done
3. **Monitor latency:** Deepgram latency typically 100-300ms
4. **Handle silence:** Use `endpointing` for automatic silence detection

---

## OpenAI API

### Overview

**Service:** Language model (GPT-4)  
**Docs:** https://platform.openai.com/docs  
**Pricing:** ~$0.03 per 1K tokens (GPT-4 Turbo)

### Authentication

**Method:** API Key in Authorization header

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="YOUR_API_KEY")
```

### Streaming Completion

**Endpoint:** POST `https://api.openai.com/v1/chat/completions`

**Request:**
```python
stream = await client.chat.completions.create(
    model="gpt-4-turbo-preview",
    messages=[
        {"role": "system", "content": "You are a helpful voice assistant."},
        {"role": "user", "content": "Book a flight to Bangalore tomorrow morning"}
    ],
    stream=True,
    max_tokens=500,
    temperature=0.7
)
```

**Streaming Tokens:**
```python
async for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        token = chunk.choices[0].delta.content
        print(token, end='', flush=True)
```

### Cancellation

**Method:** Use `asyncio.CancelledError` or close stream

```python
import asyncio

async def stream_with_cancellation(stream, cancel_event: asyncio.Event):
    try:
        async for chunk in stream:
            if cancel_event.is_set():
                await stream.close()
                return None
            
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except asyncio.CancelledError:
        await stream.close()
        raise
    finally:
        await stream.close()
```

### Context Management

**System Prompt:**
```python
system_prompt = """You are a helpful voice assistant. Provide concise, conversational responses.
- Keep responses under 3 sentences
- Be friendly and natural
- Assume voice interaction (no markdown formatting)
"""
```

**Conversation History:**
```python
messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "What's the weather?"},
    {"role": "assistant", "content": "It's sunny and 75°F today."},
    {"role": "user", "content": "Should I bring an umbrella?"}
]
```

**Context Window:**
- GPT-4 Turbo: 128K tokens
- Trim old messages if exceeding limit

### Error Handling

**Rate Limits (429):**
```python
from openai import RateLimitError
import asyncio

try:
    response = await client.chat.completions.create(...)
except RateLimitError as e:
    wait_time = int(e.response.headers.get('Retry-After', 1))
    await asyncio.sleep(wait_time)
    # Retry
```

**Timeouts:**
```python
try:
    async with asyncio.timeout(5.0):
        response = await client.chat.completions.create(...)
except asyncio.TimeoutError:
    # Handle timeout
```

**API Errors:**
- `401 Unauthorized`: Invalid API key
- `500 Server Error`: Retry once
- `503 Service Unavailable`: Retry with backoff

### Best Practices

1. **Stream responses:** Always use `stream=True` for voice applications
2. **Set max_tokens:** Prevent runaway responses (recommend 500)
3. **Temperature:** Use 0.7 for balanced creativity/consistency
4. **Track usage:** Monitor tokens for cost control
5. **Cancellation:** Always close streams properly to avoid charges

---

## ElevenLabs API

### Overview

**Service:** Text-to-speech synthesis  
**Docs:** https://docs.elevenlabs.io/  
**Pricing:** ~$0.30 per 1K characters

### Authentication

**Method:** API Key in header

```python
from elevenlabs import set_api_key, generate, stream

set_api_key("YOUR_API_KEY")
```

### Streaming TTS

**Method:** `generate()` with `stream=True`

```python
audio_stream = generate(
    text="Hello, how can I help you today?",
    voice="Bella",
    model="eleven_turbo_v2",
    stream=True
)
```

**Voice Options:**
- `"Bella"` - Friendly female
- `"Antoni"` - Professional male
- `"Elli"` - Young female
- Custom voice IDs (train your own)

**Models:**
- `"eleven_monolingual_v1"` - High quality, slower
- `"eleven_turbo_v2"` - Fastest, lowest latency (recommended)

### Streaming Audio Chunks

```python
async def stream_audio(text: str, cancel_event: asyncio.Event):
    audio_stream = generate(text=text, voice="Bella", model="eleven_turbo_v2", stream=True)
    
    for chunk in audio_stream:
        if cancel_event.is_set():
            break
        
        # chunk is raw audio bytes
        yield base64.b64encode(chunk).decode('utf-8')
```

### Audio Format

**Output:** MP3 (default) or PCM  
**Sample Rate:** 44.1kHz (MP3) or 22.05kHz (PCM)  
**Channels:** Mono

**Convert to PCM for Web Audio API:**
```python
from elevenlabs import generate

audio = generate(
    text="Hello",
    voice="Bella",
    model="eleven_turbo_v2",
    output_format="pcm_22050"  # PCM at 22.05kHz
)
```

### Voice Settings

**Customize voice characteristics:**
```python
from elevenlabs import Voice, VoiceSettings

audio = generate(
    text="Hello",
    voice=Voice(
        voice_id="21m00Tcm4TlvDq8ikWAM",  # Bella
        settings=VoiceSettings(
            stability=0.5,      # 0-1 (higher = more consistent)
            similarity_boost=0.75  # 0-1 (higher = closer to original)
        )
    ),
    model="eleven_turbo_v2"
)
```

### Error Handling

**API Errors:**
```python
from elevenlabs import APIError

try:
    audio = generate(text="Hello", voice="Bella")
except APIError as e:
    print(f"ElevenLabs error: {e}")
    # Fall back to text-only response
```

**Quota Exceeded:**
- `429 Too Many Requests`: Character quota exceeded
- Monitor usage in dashboard
- Implement fallback to text-only

### Best Practices

1. **Use Turbo V2:** Lowest latency for real-time applications (~300ms)
2. **Stream audio:** Always use `stream=True` for voice agents
3. **Split long text:** Break into sentences for faster first audio
4. **Cache common phrases:** Pre-generate frequently used responses
5. **Handle interruptions:** Stop generation immediately on user speech

---

## Error Codes Reference

### WebSocket Error Codes

| Code | Description | Recoverable |
|------|-------------|-------------|
| `WS_CONNECTION_FAILED` | WebSocket connection failed | Yes |
| `WS_CONNECTION_LOST` | Connection lost unexpectedly | Yes |
| `WS_AUTH_FAILED` | Authentication failed (if enabled) | No |
| `WS_INVALID_MESSAGE` | Invalid message format | No |
| `WS_RATE_LIMITED` | Too many messages sent | Yes |

### STT Error Codes (Deepgram)

| Code | Description | Recoverable |
|------|-------------|-------------|
| `STT_CONNECTION_FAILED` | Deepgram connection failed | Yes |
| `STT_CONNECTION_LOST` | Deepgram connection lost | Yes |
| `STT_AUTH_FAILED` | Invalid API key | No |
| `STT_RATE_LIMITED` | Deepgram rate limit exceeded | Yes |
| `STT_TIMEOUT` | Connection timeout | Yes |

### LLM Error Codes (OpenAI)

| Code | Description | Recoverable |
|------|-------------|-------------|
| `LLM_API_FAILED` | OpenAI API request failed | Yes |
| `LLM_AUTH_FAILED` | Invalid API key | No |
| `LLM_RATE_LIMITED` | OpenAI rate limit exceeded | Yes |
| `LLM_TIMEOUT` | Request timeout | Yes |
| `LLM_CONTEXT_LENGTH_EXCEEDED` | Context too long | No |

### TTS Error Codes (ElevenLabs)

| Code | Description | Recoverable |
|------|-------------|-------------|
| `TTS_API_FAILED` | ElevenLabs API request failed | Yes |
| `TTS_AUTH_FAILED` | Invalid API key | No |
| `TTS_RATE_LIMITED` | ElevenLabs rate limit exceeded | Yes |
| `TTS_QUOTA_EXCEEDED` | Character quota exceeded | No |
| `TTS_TIMEOUT` | Request timeout | Yes |

### Database Error Codes

| Code | Description | Recoverable |
|------|-------------|-------------|
| `DB_CONNECTION_FAILED` | Database connection failed | Yes |
| `DB_CONNECTION_LOST` | Database connection lost | Yes |
| `DB_WRITE_FAILED` | Write operation failed | Yes |
| `DB_READ_FAILED` | Read operation failed | Yes |

### System Error Codes

| Code | Description | Recoverable |
|------|-------------|-------------|
| `AUDIO_BUFFER_OVERFLOW` | Audio buffer full | Yes |
| `INVALID_STATE_TRANSITION` | Illegal state transition | No |
| `SESSION_EXPIRED` | Session expired | No |
| `UNKNOWN_ERROR` | Unhandled exception | Maybe |

---

## Testing APIs

### Test Deepgram Connection

```python
from deepgram import Deepgram

dg = Deepgram(api_key="YOUR_KEY")

async def test_deepgram():
    connection = await dg.transcription.live({
        'punctuate': True,
        'interim_results': True
    })
    
    # Send test audio file
    with open('test_audio.wav', 'rb') as audio:
        await connection.send(audio.read())
    
    await connection.finish()

# Run: asyncio.run(test_deepgram())
```

### Test OpenAI Streaming

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key="YOUR_KEY")

async def test_openai():
    stream = await client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[{"role": "user", "content": "Say hello"}],
        stream=True
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end='')

# Run: asyncio.run(test_openai())
```

### Test ElevenLabs TTS

```python
from elevenlabs import generate

def test_elevenlabs():
    audio = generate(
        text="This is a test.",
        voice="Bella",
        model="eleven_turbo_v2"
    )
    
    # Save to file
    with open('test_audio.mp3', 'wb') as f:
        f.write(audio)

# Run: test_elevenlabs()
```

---

## Rate Limits Summary

| Service | Free Tier | Paid Tier | Notes |
|---------|-----------|-----------|-------|
| Deepgram | 12,000 min/month | Pay-per-use | ~$0.0125/min |
| OpenAI | $5 credit | Pay-per-use | ~$0.03/1K tokens (GPT-4) |
| ElevenLabs | 10K char/month | Pay-per-use | ~$0.30/1K characters |
| Neon Postgres | 3 projects free | Pay-per-use | Free tier sufficient for MVP |

**Cost Estimate (per user per hour):**
- STT (Deepgram): $0.75 (60 min × $0.0125)
- LLM (OpenAI): $1.50 (~50K tokens × $0.03/1K)
- TTS (ElevenLabs): $1.80 (~6K characters × $0.30/1K)
- **Total: ~$4.05/hour per active user**

---

## API Best Practices Summary

1. **Always handle errors gracefully** - Don't crash on API failures
2. **Implement exponential backoff** - For retries on rate limits
3. **Monitor usage and costs** - Set up billing alerts
4. **Close connections properly** - Avoid dangling connections
5. **Use streaming** - For real-time responsiveness
6. **Cancel operations** - When user interrupts or changes intent
7. **Log API calls** - For debugging and analytics
8. **Validate API keys** - On startup to catch configuration errors
9. **Use environment variables** - Never hardcode API keys
10. **Test with mock APIs** - During development to save costs

---

**This document should be your primary reference when working with any external APIs or WebSocket communication in the Voice AI Pipeline project.**
