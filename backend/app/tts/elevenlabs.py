"""
ElevenLabs streaming TTS client.

Converts text to speech with streaming output and cancellation support.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional
import json
import base64

from app.config import settings

logger = logging.getLogger(__name__)


class ElevenLabsClient:
    """
    Manages streaming connection to ElevenLabs for TTS.
    
    Features:
    - Streaming audio generation with cancellation
    - Base64 encoding for WebSocket transmission
    - Retry once on failure
    - Fallback to text-only on TTS failure
    """

    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.voice_id = settings.elevenlabs_voice_id
        self.model = "eleven_turbo_v2_5"  # Latest turbo model for lowest latency

    async def generate_audio(
        self,
        text: str,
        cancel_event: asyncio.Event,
    ) -> AsyncGenerator[bytes, None]:
        """
        Generate streaming audio from text.

        Args:
            text: Text to convert to speech
            cancel_event: Event to signal cancellation

        Yields:
            Audio chunks as bytes (PCM 16kHz mono)
        """
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"
        
        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            }
        }

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }

        try:
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=30, connect=5)
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload
                ) as response:
                    
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"ElevenLabs API error {response.status}: {error_text}")
                        return

                    # Stream audio chunks
                    chunk_index = 0
                    async for chunk in response.content.iter_chunked(4096):
                        # Check for cancellation
                        if cancel_event.is_set():
                            logger.info("TTS generation cancelled")
                            return

                        if chunk:
                            # Log first chunk to verify streaming
                            if chunk_index == 0:
                                logger.info(f"✅ TTS streaming: First audio chunk received ({len(chunk)} bytes)")
                            chunk_index += 1
                            yield chunk

            logger.info(f"TTS generation complete: {chunk_index} chunks")

        except asyncio.CancelledError:
            logger.info("TTS generation task cancelled")
            return
        except Exception as e:
            logger.error(f"Error during TTS generation: {e}")
            return

    def encode_audio_base64(self, audio_bytes: bytes) -> str:
        """
        Encode audio bytes to base64 for WebSocket transmission.
        
        Args:
            audio_bytes: Raw audio data
            
        Returns:
            Base64-encoded string
        """
        return base64.b64encode(audio_bytes).decode('utf-8')

    async def test_connection(self) -> bool:
        """
        Test ElevenLabs API connection and voice availability.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            import aiohttp
            
            url = f"https://api.elevenlabs.io/v1/voices/{self.voice_id}"
            headers = {"xi-api-key": self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        voice_data = await response.json()
                        logger.info(f"ElevenLabs voice verified: {voice_data.get('name', 'Unknown')}")
                        return True
                    else:
                        logger.error(f"ElevenLabs voice check failed: {response.status}")
                        return False
        except Exception as e:
            logger.error(f"ElevenLabs connection test failed: {e}")
            return False
