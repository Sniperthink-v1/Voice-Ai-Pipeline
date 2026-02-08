# Deepgram Flux Migration Assessment

## Executive Summary

**Recommendation: ⚠️ CONDITIONALLY YES** - Flux can reduce latency by 300-800ms, but requires careful evaluation of trade-offs.

### Potential Latency Improvements

| Component | Current | With Flux | Savings | Notes |
|-----------|---------|-----------|---------|-------|
| Silence Detection | 400ms debounce | N/A (built-in) | -140ms | Flux handles natively |
| STT → LLM Gap | 700ms | 200-400ms | -300-500ms | EagerEndOfTurn triggers LLM early |
| **Combined with Your Planned Fixes** |  |  |  |
| ElevenLabs pooling | - | - | -200ms | Already planned |
| OpenAI pre-warming | - | - | -100ms | Verify working |
| **TOTAL REDUCTION** |  |  | **-600-800ms** | 33-44% improvement |

**Expected Final Latency:** 1,000-1,300ms (Currently: 1,822-2,213ms)

---

## How Flux Aligns With Your Architecture

### Perfect Match: Speculative Execution

Your state machine already implements speculative execution:

```
LISTENING → SPECULATIVE → COMMITTED → SPEAKING
              ↓ cancel        ↑
          (user continues) (confirmed)
```

**Flux events map perfectly:**

| Flux Event | Your State Transition | Action |
|------------|----------------------|--------|
| `EagerEndOfTurn` | LISTENING → SPECULATIVE | Start LLM, hold output |
| `TurnResumed` | SPECULATIVE → LISTENING | Cancel LLM (you already do this!) |
| `EndOfTurn` | SPECULATIVE → COMMITTED | Surface LLM output to TTS |

**This is exactly what Flux was designed for!** Your cancellation infrastructure (`_llm_cancel_event`) is already built.

---

## Trade-offs & Concerns

### ❌ CRITICAL: Loss of Multilingual Support

**Current Setup:**
```python
params = {
    "model": "nova-3",
    "language": "multi",  # English + Hindi code-switching
}
```

**Flux Limitation:**
```python
params = {
    "model": "flux-general-en",  # English ONLY
}
```

**Impact:**
- ❌ No Hindi support
- ❌ No Indian English (`en-IN`) optimization
- ❌ No code-switching between languages

**Questions to answer:**
1. What % of your users speak Hindi or require multilingual support?
2. Is English-only acceptable for MVP/beta?
3. Can you run A/B test (English users get Flux, others get nova-3)?

**Mitigation Strategy:**
```python
# Hybrid approach in turn_controller.py
async def _initialize_stt(self):
    if self.user_language == "en" or self.user_language == "en-US":
        # Use Flux for English-only users (optimize latency)
        self.stt = DeepgramFluxClient(...)
        logger.info("Using Flux for English user (optimized latency)")
    else:
        # Fall back to nova-3 for multilingual users
        self.stt = DeepgramClient(...)  # Your existing implementation
        logger.info(f"Using nova-3 for {self.user_language} (multilingual support)")
```

---

### ⚠️ CONCERN: Increased LLM Costs

**From Deepgram's documentation:**
> Cost Consideration: Using `EagerEndOfTurn` can increase LLM API calls by 50-70% due to speculative response generation.

**Your Current Behavior:**
- Already using speculative execution (SPECULATIVE state)
- Already cancelling LLM calls on user interruption
- TurnController has `_llm_cancel_event` infrastructure

**Impact Analysis:**

| Scenario | Current | With Flux | Cost Change |
|----------|---------|-----------|-------------|
| User speaks 10 words, no interruption | 1 LLM call | 1 LLM call | No change |
| User speaks 10 words, self-corrects | 1 LLM call (400ms debounce prevents early trigger) | 2 LLM calls (EagerEOT + final) | +100% for this turn |
| Conversational back-and-forth | Rare cancellations | 30-50% cancellation rate | +50-70% average |

**Example Cost Calculation:**
```
Assumptions:
- 100 conversations/day
- 10 turns per conversation
- $0.01 per 1K tokens
- Average 500 tokens per LLM call

Current monthly cost:
100 conv × 10 turns × 30 days × 500 tokens × $0.01/1000 = $150/month

With Flux (1.6x multiplier):
$150 × 1.6 = $240/month

Cost increase: $90/month or ~$1,080/year
```

**But you gain:**
- 600-800ms latency reduction → Better UX → Higher retention
- Users more likely to complete conversations (lower frustration)

**ROI Calculation:**
If 5% more users complete conversations due to better responsiveness:
- Extra revenue/value likely exceeds $90/month

---

### ⚠️ CONCERN: API Migration Effort

**Changes Required:**

1. **Endpoint Migration:**
   - `/v1/listen` → `/v2/listen`
   - Verify your Deepgram Python SDK version supports v2

2. **SDK Update:**
   ```bash
   pip install --upgrade deepgram-sdk
   # Check version: >= 3.x required for /v2/listen
   ```

3. **Parameter Changes:**
   ```python
   # REMOVE (not supported in Flux):
   - "language": "multi"
   - "diarize": "false"
   - "utterance_end_ms": 1000
   - "vad_events": "true"
   - "endpointing": 300

   # ADD (Flux-specific):
   + "eot_threshold": 0.7
   + "eager_eot_threshold": 0.5
   + "eot_timeout_ms": 5000
   ```

4. **Event Handler Changes:**
   ```python
   # ADD new callbacks in turn_controller.py:
   - on_eager_end_of_turn()  # Trigger SPECULATIVE state
   - on_turn_resumed()        # Cancel speculative LLM
   - on_end_of_turn()         # Transition to COMMITTED
   ```

5. **Remove Custom Silence Timer:**
   - `SilenceTimer` class becomes redundant
   - Flux handles turn detection natively
   - ~100 lines of code can be removed

**Estimated Development Time:** 4-8 hours
- 2 hours: Integrate Flux client (I've provided starter code)
- 2 hours: Update turn_controller callbacks
- 2 hours: Test and tune `eager_eot_threshold`
- 2 hours: Handle edge cases and logging

---

## Implementation Strategy

### Phase 1: Proof of Concept (2-4 hours)

1. **Install latest Deepgram SDK:**
   ```bash
   cd backend
   pip install --upgrade deepgram-sdk
   python -c "from deepgram import AsyncDeepgramClient; print('v2 SDK ready')"
   ```

2. **Test Flux connection:**
   ```python
   # Create test script: backend/test_flux.py
   from app.stt.deepgram_flux import DeepgramFluxClient
   
   async def test():
       async def on_eager(text, conf):
           print(f"🚀 EAGER: {text}")
       
       async def on_resumed():
           print("🔄 RESUMED")
       
       async def on_eot(text, conf):
           print(f"✅ EOT: {text}")
       
       client = DeepgramFluxClient(
           on_partial_transcript=lambda t, c: None,
           on_final_transcript=lambda t, c: None,
           on_eager_end_of_turn=on_eager,
           on_turn_resumed=on_resumed,
           on_end_of_turn=on_eot,
       )
       
       await client.connect(eager_eot_threshold=0.5)
       # Test with real microphone input...
   ```

3. **Measure eager_eot_threshold sweet spot:**
   ```
   Try different values:
   - 0.3: Very aggressive (more false starts, lower latency)
   - 0.5: Balanced (recommended starting point)
   - 0.7: Conservative (fewer false starts, higher latency)
   
   Goal: 30-40% cancellation rate (not 50-70% - costs matter!)
   ```

### Phase 2: Integration (4-6 hours)

1. **Update TurnController callbacks:**
   ```python
   # In turn_controller.py __init__:
   self.deepgram_flux = DeepgramFluxClient(
       on_partial_transcript=self._handle_partial_transcript,
       on_final_transcript=self._handle_final_transcript,
       on_eager_end_of_turn=self._on_eager_end_of_turn,
       on_turn_resumed=self._on_turn_resumed,
       on_end_of_turn=self._on_end_of_turn_confirmed,
   )
   ```

2. **New event handlers:**
   ```python
   async def _on_eager_end_of_turn(self, transcript: str, confidence: float):
       """
       Flux signaled likely end-of-turn - start LLM speculatively.
       
       This replaces your current silence timer logic!
       """
       if self.state_machine.current_state != TurnState.LISTENING:
           return
       
       logger.info(f"🚀 Eager EOT detected: '{transcript}' - starting speculative LLM")
       
       # Transition LISTENING → SPECULATIVE
       await self._transition_state(TurnState.SPECULATIVE)
       
       # Start LLM generation (already have this!)
       self._llm_cancel_event.clear()
       await self._start_llm_generation(transcript)
   
   async def _on_turn_resumed(self):
       """
       User continued speaking - cancel speculative LLM.
       
       This is NORMAL behavior! Expected 30-40% of the time.
       """
       if self.state_machine.current_state != TurnState.SPECULATIVE:
           return
       
       logger.info("🔄 Turn resumed - cancelling speculative LLM (cost saved!)")
       
       # Cancel LLM (you already have this infrastructure!)
       self._llm_cancel_event.set()
       
       # Transition SPECULATIVE → LISTENING
       await self._transition_state(TurnState.LISTENING)
   
   async def _on_end_of_turn_confirmed(self, transcript: str, confidence: float):
       """
       Flux confirmed end-of-turn - commit LLM response.
       """
       if self.state_machine.current_state == TurnState.SPECULATIVE:
           logger.info("✅ Turn confirmed - transitioning to COMMITTED")
           await self._transition_state(TurnState.COMMITTED)
           
           # Your existing code handles COMMITTED → SPEAKING transition
       elif self.state_machine.current_state == TurnState.LISTENING:
           # No eager trigger happened - start LLM now
           logger.info("✅ Turn ended without eager trigger - starting LLM")
           await self._start_llm_generation(transcript)
   ```

3. **Remove SilenceTimer (optional cleanup):**
   - Flux makes `silence_timer.py` redundant
   - Can remove after confirming Flux works

### Phase 3: Testing & Tuning (2-4 hours)

1. **Test cancellation behavior:**
   ```
   Test scenarios:
   - "I want to... wait, no, I need to..." (should see TurnResumed)
   - "Hello there" (should see EagerEOT → EOT without resume)
   - Long pause mid-sentence (should NOT trigger eager too early)
   ```

2. **Tune eager_eot_threshold:**
   ```
   Monitor metrics:
   - Cancellation rate: Target 30-40% (not 50-70%!)
   - User-perceived latency: Should feel <1s response
   - False starts: Users shouldn't hear cut-off responses
   
   Adjustment strategy:
   - If cancellation rate >50%: Increase threshold (0.5 → 0.6)
   - If latency still high: Decrease threshold (0.5 → 0.4)
   - If users hear cut-offs: Increase threshold + tune sentence buffering
   ```

3. **Compare metrics:**
   ```
   Measure 50 conversations each:
   
   Without Flux:
   - Avg latency: 1,822ms
   - Cancellation rate: ~15% (from your conservative debounce)
   - LLM calls: 1.0x baseline
   
   With Flux:
   - Avg latency: Target <1,300ms (-29%)
   - Cancellation rate: Target 30-40%
   - LLM calls: ~1.3x baseline
   
   ROI validation:
   - User satisfaction up?
   - Conversation completion rate up?
   - Cost increase justified?
   ```

### Phase 4: Hybrid Deployment (Optional)

**If you need multilingual support:**

```python
# In websocket.py or turn_controller.py
FLUX_ENABLED_LANGUAGES = {"en", "en-US", "en-GB"}

async def create_stt_client(user_language: str):
    if user_language in FLUX_ENABLED_LANGUAGES:
        logger.info(f"Using Flux for {user_language} (optimized latency)")
        return DeepgramFluxClient(...)
    else:
        logger.info(f"Using nova-3 for {user_language} (multilingual support)")
        return DeepgramClient(...)
```

**Rollout Strategy:**
1. Week 1: English users only (80% of traffic?)
2. Week 2: Expand to en-GB, en-AU if metrics good
3. Week 3: Keep multilingual users on nova-3
4. Monitor: Latency, costs, user satisfaction by cohort

---

## Decision Matrix

| Factor | Weight | Score (1-5) | Weighted | Notes |
|--------|--------|-------------|----------|-------|
| **Latency Improvement** | 35% | 5 | 1.75 | -600-800ms is huge (33-44%) |
| **Architecture Fit** | 25% | 5 | 1.25 | Perfect match for your speculative design |
| **Implementation Effort** | 15% | 3 | 0.45 | 8-12 hours, but well-documented |
| **Cost Impact** | 15% | 2 | 0.30 | +$90/month LLM costs |
| **Multilingual Loss** | 10% | 1 | 0.10 | **CRITICAL BLOCKER if Hindi required** |
| **Total Score** |  |  | **3.85/5** | **APPROVE if English-only acceptable** |

---

## Recommendation

### ✅ Implement Flux IF:

1. **80%+ of your users speak English only**
   - Hybrid approach possible for multilingual
   
2. **Latency is top priority over cost**
   - $90/month is acceptable for 600-800ms improvement
   
3. **You can dedicate 8-12 hours to integration**
   - I've provided starter code to accelerate
   
4. **You're okay with 30-40% speculative LLM calls**
   - Your architecture already supports this!

### ❌ Skip Flux IF:

1. **Hindi/multilingual support is critical**
   - Flux is English-only (`flux-general-en`)
   - Wait for Flux multilingual release
   
2. **Budget is extremely tight**
   - +$90/month might matter for early-stage MVP
   
3. **Current 1,822ms latency is acceptable**
   - Focus on ElevenLabs pooling first (-200ms, no downside)

---

## Next Steps

### Option A: Full Commitment (Recommended)

1. **Today:** Answer the multilingual question (hard blocker!)
2. **Tomorrow:** Run Phase 1 POC (2-4 hours)
3. **Next week:** Integrate Phase 2 (4-6 hours) + test Phase 3
4. **Following week:** Monitor production metrics, tune threshold

### Option B: Conservative Approach

1. **This week:** Implement ElevenLabs connection pooling (-200ms, no risk)
2. **Next week:** Verify OpenAI pre-warming (-100ms)
3. **Measure:** Are you at 1,500ms now?
4. **Decide:** If still too slow, revisit Flux

### Option C: Hybrid Test

1. **Detect user language** from first utterance or preference
2. **English users:** Route to Flux (optimize latency)
3. **Other users:** Route to nova-3 (maintain multilingual)
4. **Compare:** Latency, satisfaction, retention by cohort

---

## Questions to Answer Before Proceeding

1. **What % of users need Hindi or multilingual support?**
   - If >20%, consider hybrid approach
   - If <5%, Flux is clear win

2. **What's your target latency?**
   - If <1,500ms required: You NEED Flux
   - If <2,000ms acceptable: Optimize existing first

3. **Can you A/B test?**
   - 50% users get Flux, 50% get nova-3
   - Measure latency, completion rates, satisfaction

4. **Monthly budget for LLM costs?**
   - +$90/month acceptable?
   - Or need to optimize `eager_eot_threshold` aggressively?

---

## Files I've Created

1. **`backend/app/stt/deepgram_flux.py`** - Full Flux client implementation
   - EagerEndOfTurn, TurnResumed, EndOfTurn handlers
   - Drop-in replacement for your existing DeepgramClient
   - Extensive logging and error handling

2. **This document** - Complete migration assessment

**Ready to implement when you decide to proceed!**

## References

- [Deepgram Flux Documentation](https://developers.deepgram.com/docs/flux/quickstart)
- [Flux Voice Agent Guide](https://developers.deepgram.com/docs/flux/agent)
- [Your Latency Analysis](./LATENCY_ANALYSIS_FEB8.md)
- [Your Architecture Docs](./instruction.md)
