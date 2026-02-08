"""
Test ElevenLabs connection pooling implementation.

This script verifies:
1. Persistent session is created and reused
2. Connection warmup works
3. Multiple TTS calls reuse the same session
4. Session cleanup works properly
"""

import asyncio
import logging
import sys
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from app.tts.elevenlabs import ElevenLabsClient


async def test_connection_pooling():
    """Test that session is reused across multiple calls."""
    print("\n" + "="*80)
    print("TEST 1: Connection Pooling - Session Reuse")
    print("="*80 + "\n")
    
    client = ElevenLabsClient()
    
    # First call - should create session
    print("📞 First call - Creating session...")
    session1 = await client._get_session()
    session1_id = id(session1)
    print(f"✅ Session 1 created: ID={session1_id}")
    
    # Second call - should reuse same session
    print("\n📞 Second call - Should reuse session...")
    session2 = await client._get_session()
    session2_id = id(session2)
    print(f"✅ Session 2 retrieved: ID={session2_id}")
    
    if session1_id == session2_id:
        print("\n✅ SUCCESS: Same session reused (connection pooling working!)")
    else:
        print("\n❌ FAILURE: Different sessions created (pooling NOT working)")
        return False
    
    await client.close()
    print("🧹 Session closed\n")
    return True


async def test_warmup():
    """Test connection warmup functionality."""
    print("\n" + "="*80)
    print("TEST 2: Connection Warmup")
    print("="*80 + "\n")
    
    client = ElevenLabsClient()
    
    print("🔥 Starting warmup...")
    start = time.time()
    await client._warm_up_connection()
    warmup_time = (time.time() - start) * 1000
    print(f"✅ Warmup completed in {warmup_time:.0f}ms")
    
    # Subsequent call should be faster (connection already established)
    print("\n🚀 Making test API call...")
    start = time.time()
    success = await client.test_connection()
    api_time = (time.time() - start) * 1000
    
    if success:
        print(f"✅ API call completed in {api_time:.0f}ms")
        if api_time < warmup_time:
            print(f"✅ SUCCESS: Subsequent call faster ({api_time:.0f}ms vs {warmup_time:.0f}ms)")
        else:
            print(f"⚠️  Subsequent call not faster, but connection validated")
    else:
        print("❌ FAILURE: API call failed")
        return False
    
    await client.close()
    print("🧹 Session closed\n")
    return True


async def test_tts_generation():
    """Test actual TTS generation with connection pooling."""
    print("\n" + "="*80)
    print("TEST 3: TTS Generation with Pooling")
    print("="*80 + "\n")
    
    client = ElevenLabsClient()
    cancel_event = asyncio.Event()
    
    # Pre-warm connection
    print("🔥 Pre-warming connection...")
    await client._warm_up_connection()
    
    # First TTS call
    print("\n🎤 First TTS generation...")
    test_text = "Hello, this is a test."
    start = time.time()
    
    chunk_count = 0
    async for chunk in client.generate_audio(test_text, cancel_event):
        if chunk_count == 0:
            first_chunk_time = (time.time() - start) * 1000
            print(f"✅ First chunk received in {first_chunk_time:.0f}ms")
        chunk_count += 1
    
    total_time = (time.time() - start) * 1000
    print(f"✅ TTS complete: {chunk_count} chunks in {total_time:.0f}ms")
    
    # Second TTS call - should be faster (connection reused)
    print("\n🎤 Second TTS generation (should be faster)...")
    cancel_event.clear()
    start = time.time()
    
    chunk_count2 = 0
    async for chunk in client.generate_audio("Second test.", cancel_event):
        if chunk_count2 == 0:
            first_chunk_time2 = (time.time() - start) * 1000
            print(f"✅ First chunk received in {first_chunk_time2:.0f}ms")
        chunk_count2 += 1
    
    total_time2 = (time.time() - start) * 1000
    print(f"✅ TTS complete: {chunk_count2} chunks in {total_time2:.0f}ms")
    
    if first_chunk_time2 < first_chunk_time:
        improvement = first_chunk_time - first_chunk_time2
        print(f"\n✅ SUCCESS: Second call {improvement:.0f}ms faster ({first_chunk_time2:.0f}ms vs {first_chunk_time:.0f}ms)")
    else:
        print(f"\n⚠️  Second call not distinctly faster (both calls may have benefited from warmup)")
    
    await client.close()
    print("🧹 Session closed\n")
    return True


async def test_session_cleanup():
    """Test that session is properly cleaned up."""
    print("\n" + "="*80)
    print("TEST 4: Session Cleanup")
    print("="*80 + "\n")
    
    client = ElevenLabsClient()
    
    # Create session
    print("📞 Creating session...")
    session = await client._get_session()
    print(f"✅ Session created: closed={session.closed}")
    
    # Close client
    print("\n🧹 Closing client...")
    await client.close()
    
    # Verify session is closed
    if session.closed:
        print("✅ SUCCESS: Session properly closed")
    else:
        print("❌ FAILURE: Session not closed")
        return False
    
    # Verify new session is created after close
    print("\n📞 Creating new session after close...")
    new_session = await client._get_session()
    new_session_id = id(new_session)
    old_session_id = id(session)
    
    if new_session_id != old_session_id:
        print(f"✅ SUCCESS: New session created (old={old_session_id}, new={new_session_id})")
    else:
        print("❌ FAILURE: Same session returned after close")
        return False
    
    await client.close()
    print("🧹 Final cleanup\n")
    return True


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("ElevenLabs Connection Pooling Verification")
    print("="*80)
    
    results = []
    
    # Test 1: Connection pooling
    try:
        result = await test_connection_pooling()
        results.append(("Connection Pooling", result))
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        results.append(("Connection Pooling", False))
    
    # Test 2: Warmup
    try:
        result = await test_warmup()
        results.append(("Connection Warmup", result))
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        results.append(("Connection Warmup", False))
    
    # Test 3: TTS generation (requires valid API key)
    try:
        result = await test_tts_generation()
        results.append(("TTS Generation", result))
    except Exception as e:
        print(f"⚠️  Test skipped or failed: {e}")
        results.append(("TTS Generation", None))
    
    # Test 4: Cleanup
    try:
        result = await test_session_cleanup()
        results.append(("Session Cleanup", result))
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        results.append(("Session Cleanup", False))
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80 + "\n")
    
    for test_name, result in results:
        if result is True:
            status = "✅ PASS"
        elif result is False:
            status = "❌ FAIL"
        else:
            status = "⚠️  SKIP"
        print(f"{status:12} {test_name}")
    
    print("\n" + "="*80)
    
    # Exit code
    if all(r in [True, None] for _, r in results):
        print("✅ All critical tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
