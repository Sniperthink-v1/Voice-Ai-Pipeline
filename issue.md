# Issue: LLM-to-TTS Pipeline Not Streaming at Sentence Boundaries

## Problem Summary

The LLM response generation is streaming tokens correctly from OpenAI, but the **turn controller waits for the entire LLM response to complete** before starting TTS. This violates the core design principle of "aggressive output streaming" and adds significant unnecessary latency.

## Current Behavior

1. OpenAI streams tokens one-by-one ✅
2. Turn controller buffers all tokens internally ❌
3. After **entire LLM response completes**, transition to COMMITTED
4. Send **full text** to ElevenLabs TTS in one shot ❌
5. ElevenLabs streams audio chunks ✅

**Result:** Total latency = silence debounce + **full LLM generation** + TTS first chunk

Example: 200-token response @ 50 tokens/sec = **~4 seconds waiting** before first audio

## Expected Behavior (Per PRD)

1. OpenAI streams tokens ✅
2. Turn controller detects **first sentence boundary** (`.`, `?`, `!`)
3. **Immediately start TTS** for first sentence while LLM continues
4. Stream subsequent sentences to TTS as they complete
5. User hears audio ~1 second after speech end

**Result:** Total latency = silence debounce + **first sentence generation** + TTS first chunk

## Code Locations

### 1. `backend/app/orchestration/turn_controller.py`

**Lines 300-327** - `_run_llm()` method:
```python
# Buffer LLM output
llm_buffer = []
first_sentence_ready = False

def on_token(token: str):
    nonlocal first_sentence_ready
    llm_buffer.append(token)
    
    # Check for sentence boundary
    if not first_sentence_ready:
        accumulated = ''.join(llm_buffer)
        if any(p in accumulated for p in ['.', '?', '!']):
            first_sentence_ready = True  # ❌ Sets flag but NEVER acts on it

# Generate response
result = await self.openai.generate_response(...)  # ❌ Blocks until complete

if result is None:
    return

full_response, prompt_tokens, completion_tokens = result  # ❌ Gets full response
```

**Line 352** - TTS triggered only after LLM complete:
```python
await self._run_tts()  # ❌ Called after full LLM generation
```

**Lines 385-387** - `_run_tts()` receives entire text:
```python
async for audio_chunk in self.elevenlabs.generate_audio(
    text=self._llm_response,  # ❌ Full LLM output sent at once
    cancel_event=self._tts_cancel_event,
):
```

### 2. `backend/app/llm/openai_client.py`

**Lines 36-56** - `generate_response()` signature:
```python
async def generate_response(
    self,
    messages: list[dict],
    cancel_event: asyncio.Event,
    on_token: Optional[Callable[[str], None]] = None,
) -> Optional[tuple[str, int, int]]:  # ❌ Returns full response, not generator
```

**Lines 87-137** - Accumulates full response before returning:
```python
async for line in response.content:  # ✅ Streams from API
    # ... token processing ...
    full_response += content  # ❌ Buffers internally
    if on_token:
        on_token(content)  # ✅ Callback fires but nothing acts on it

return (full_response, prompt_tokens, completion_tokens)  # ❌ Returns after complete
```

### 3. `backend/app/tts/elevenlabs.py`

**Lines 43-64** - `generate_audio()` expects full text:
```python
async def generate_audio(
    self,
    text: str,  # ❌ Takes complete text, not streaming input
    cancel_event: asyncio.Event,
) -> AsyncGenerator[bytes, None]:
```

## Impact

- **Latency increase:** 2-5 seconds depending on response length
- **User experience:** Long silent pauses before agent starts speaking
- **Does not match PRD:** "Output is streamed/interruptible (aggressive)" violated
- **Competitive disadvantage:** Other voice agents (Vapi, Retell) stream sentence-by-sentence

## Proposed Solution

### Option A: Sentence-Level Streaming (Recommended)

1. **Convert `OpenAIClient.generate_response()` to async generator:**
   ```python
   async def stream_sentences(
       self,
       messages: list[dict],
       cancel_event: asyncio.Event,
   ) -> AsyncGenerator[str, None]:  # Yields complete sentences
       buffer = []
       async for line in response.content:
           # ... extract token ...
           buffer.append(token)
           
           # Check for sentence boundary
           text = ''.join(buffer)
           if any(p in text for p in ['.', '?', '!']):
               yield text  # Emit sentence immediately
               buffer = []
   ```

2. **Update `TurnController._run_llm()` to consume sentences:**
   ```python
   async for sentence in self.openai.stream_sentences(...):
       if not first_sentence_started:
           # Transition to COMMITTED on first sentence
           await self._transition_to_committed()
           first_sentence_started = True
       
       # Queue sentence for TTS (or send to existing TTS stream)
       await self._send_to_tts(sentence)
   ```

3. **Update TTS to accept streaming text input:**
   - Option 3a: Call ElevenLabs REST API once per sentence (simpler)
   - Option 3b: Use ElevenLabs WebSocket API with text input streaming (optimal)

### Option B: WebSocket Input Streaming (Optimal but Complex)

ElevenLabs supports WebSocket input streaming where you can send text chunks incrementally:
- Open WebSocket connection to `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`
- Send text chunks as they arrive from LLM
- Receive audio chunks as they're generated
- Lower latency, more complex error handling

**Recommendation:** Start with Option A (sentence-level) for MVP, migrate to Option B if needed.

## Testing Requirements

1. **Unit test:** Verify `stream_sentences()` yields on punctuation
2. **Integration test:** Mock OpenAI, verify TTS starts before LLM completes
3. **Timing test:** Measure latency improvement (expect 2-4s reduction)
4. **Cancellation test:** Ensure sentence-level cancellation works correctly

## Acceptance Criteria

- [ ] First TTS audio chunk arrives within 1.5s of speech end (target <1000ms)
- [ ] LLM tokens stream to TTS as sentences complete, not after full response
- [ ] Cancellation still works correctly (cancel mid-sentence generation)
- [ ] `first_sentence_ready` flag actually triggers TTS start
- [ ] Timing logs show: "TTS started before LLM complete"

## Priority

**HIGH** - This is a core architectural issue blocking MVP performance targets.

## Estimated Effort

- Option A (sentence-level): 4-6 hours
- Option B (WebSocket streaming): 8-12 hours

## Additional Notes

- Current code already tracks `first_sentence_ready` but never uses it
- The `on_token` callback infrastructure exists but needs to trigger TTS
- May need to handle TTS queueing if multiple sentences arrive rapidly
- Consider buffering 2-3 words after punctuation to avoid cutting off speech
