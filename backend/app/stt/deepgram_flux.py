"""
Deepgram Flux streaming STT client with EagerEndOfTurn support.

Flux is a conversational speech recognition model built specifically for voice agents
with built-in turn detection and ultra-low latency (~260ms end-of-turn detection).

Key changes from standard Deepgram:
- Uses /v2/listen endpoint (not /v1/listen)
- Model: flux-general-en (not nova-3)
- Built-in EagerEndOfTurn events for speculative LLM execution
- 80ms audio chunks recommended (2560 bytes at 16kHz)
- No separate silence timer needed
"""

import asyncio
import json
import logging
from typing import Callable, Optional, Awaitable
from websockets import connect, WebSocketClientProtocol
from websockets.exceptions import WebSocketException

from app.config import settings

logger = logging.getLogger(__name__)


class DeepgramFluxClient:
    """
    Manages streaming connection to Deepgram Flux for real-time conversational transcription.
    
    Features:
    - EagerEndOfTurn events for early LLM response generation
    - TurnResumed events for cancelling speculative responses
    - EndOfTurn events for confirmed turn completion
    - Automatic reconnection with exponential backoff
    - ~260ms end-of-turn detection latency
    """

    def __init__(
        self,
        on_partial_transcript: Callable[[str, float], Awaitable[None]],
        on_final_transcript: Callable[[str, float], Awaitable[None]],
        on_eager_end_of_turn: Callable[[str, float], Awaitable[None]],  # Early trigger for SPECULATIVE state
        on_turn_resumed: Callable[[], Awaitable[None]],  # User continued - cancel speculative LLM
        on_end_of_turn: Callable[[str, float], Awaitable[None]],  # Confirmed end - transition to COMMITTED
        on_error: Optional[Callable[[str], Awaitable[None]]] = None,
    ):
        """
        Initialize Deepgram Flux client.

        Args:
            on_partial_transcript: Callback for interim results (text, confidence)
            on_final_transcript: Callback for final transcripts (text, confidence)
            on_eager_end_of_turn: Early signal to start LLM speculatively (SPECULATIVE state)
            on_turn_resumed: User continued speaking - cancel speculative processing
            on_end_of_turn: Confirmed turn end - commit LLM response (COMMITTED state)
            on_error: Optional callback for error handling
        """
        self.api_key = settings.deepgram_api_key
        self.on_partial_transcript = on_partial_transcript
        self.on_final_transcript = on_final_transcript
        self.on_eager_end_of_turn = on_eager_end_of_turn
        self.on_turn_resumed = on_turn_resumed
        self.on_end_of_turn = on_end_of_turn
        self.on_error = on_error

        self.ws: Optional[WebSocketClientProtocol] = None
        self.is_connected = False
        self.is_closing = False
        self._receive_task: Optional[asyncio.Task] = None
        self._send_task: Optional[asyncio.Task] = None
        self._audio_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

    async def connect(
        self,
        eager_eot_threshold: float = 0.5,  # Lower = earlier triggers, more false starts
        eot_threshold: float = 0.7,  # Higher = more reliable turn detection
        eot_timeout_ms: int = 5000,  # Max silence before forcing turn end
    ) -> bool:
        """
        Establish WebSocket connection to Deepgram Flux.

        Args:
            eager_eot_threshold: Confidence for EagerEndOfTurn (0.3-0.9). 
                                 Lower values trigger earlier but increase LLM costs.
                                 Recommended: 0.5 for balanced performance.
            eot_threshold: Confidence for final EndOfTurn (0.5-0.9).
                          Higher = more reliable, slightly higher latency.
            eot_timeout_ms: Max silence before forcing EndOfTurn (500-10000ms).

        Returns:
            True if connection successful, False otherwise
        """
        if self.is_connected:
            logger.warning("Already connected to Deepgram Flux")
            return True

        # Deepgram Flux configuration
        # CRITICAL: Must use /v2/listen endpoint and flux-general-en model
        params = {
            "model": "flux-general-en",  # NOT nova-3!
            "encoding": "linear16",
            "sample_rate": 16000,
            "channels": 1,
            "interim_results": "true",
            "punctuate": "true",
            "smart_format": "true",
            # Flux-specific parameters
            "eot_threshold": eot_threshold,
            "eager_eot_threshold": eager_eot_threshold,  # Enables EagerEndOfTurn + TurnResumed events
            "eot_timeout_ms": eot_timeout_ms,
        }
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        
        # MUST use /v2/listen for Flux (not /v1/listen)
        url = f"wss://api.deepgram.com/v2/listen?{query_string}"

        try:
            self.ws = await connect(
                url,
                extra_headers={"Authorization": f"Token {self.api_key}"},
                ping_interval=10,
                ping_timeout=5,
            )
            self.is_connected = True
            self._reconnect_attempts = 0
            logger.info(
                f"Connected to Deepgram Flux (eager_eot={eager_eot_threshold}, "
                f"eot={eot_threshold}, timeout={eot_timeout_ms}ms)"
            )

            # Start receiving messages
            self._receive_task = asyncio.create_task(self._receive_loop())
            # Start audio send loop
            self._send_task = asyncio.create_task(self._send_loop())
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Deepgram Flux: {e}")
            if self.on_error:
                await self.on_error(f"Connection failed: {str(e)}")
            return False

    async def disconnect(self):
        """Gracefully close the Deepgram Flux connection."""
        if not self.is_connected:
            return

        self.is_closing = True
        self.is_connected = False

        # Send close frame to Deepgram
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception as e:
                logger.warning(f"Error during Deepgram Flux disconnect: {e}")

        # Cancel receive task
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        # Cancel send task
        if self._send_task and not self._send_task.done():
            self._send_task.cancel()
            try:
                await self._send_task
            except asyncio.CancelledError:
                pass

        logger.info("Disconnected from Deepgram Flux")

    async def send_audio(self, audio_data: bytes):
        """
        Queue audio chunk for sending to Deepgram Flux.

        Args:
            audio_data: Raw PCM audio bytes (16kHz mono)
                       Recommended: 2560 bytes (~80ms at 16kHz) for optimal Flux performance
        """
        if not self.is_connected:
            logger.warning("Cannot send audio: not connected to Deepgram Flux")
            return

        try:
            # Non-blocking put with timeout
            await asyncio.wait_for(self._audio_queue.put(audio_data), timeout=0.1)
        except asyncio.TimeoutError:
            logger.warning("Audio queue full - dropping chunk to prevent blocking")
        except Exception as e:
            logger.error(f"Error queuing audio: {e}")

    async def finish_utterance(self):
        """
        Send FinishUtterance control message to force Flux to finalize any pending transcripts.
        
        Use this after interruptions or when resetting to ensure clean transcript boundaries.
        """
        if not self.is_connected or not self.ws:
            return
            
        try:
            await self.ws.send(json.dumps({"type": "FinishUtterance"}))
            logger.info("Sent FinishUtterance to Deepgram Flux")
        except Exception as e:
            logger.error(f"Error sending FinishUtterance: {e}")

    async def _send_loop(self):
        """
        Continuously send audio from queue to Deepgram Flux.
        
        Note: Flux recommends 80ms chunks (2560 bytes at 16kHz) for optimal performance.
        """
        try:
            while not self.is_closing:
                try:
                    # Get audio chunk from queue (blocks until available)
                    audio_data = await asyncio.wait_for(
                        self._audio_queue.get(),
                        timeout=5.0
                    )
                    
                    if self.ws and self.is_connected:
                        await self.ws.send(audio_data)
                        
                except asyncio.TimeoutError:
                    # No audio for 5 seconds - this is normal during silence
                    continue
                except Exception as e:
                    if not self.is_closing:
                        logger.error(f"Error sending audio to Flux: {e}")
                        await self._handle_connection_error(e)
                    break
                    
        except asyncio.CancelledError:
            logger.info("Audio send loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in send loop: {e}")

    async def _receive_loop(self):
        """
        Continuously receive and process messages from Deepgram Flux.
        
        Flux Event Types:
        - Results: Partial and final transcripts
        - EagerEndOfTurn: Early signal to start LLM speculatively
        - TurnResumed: User continued - cancel speculative processing
        - EndOfTurn: Confirmed turn end - commit response
        """
        try:
            while not self.is_closing and self.ws:
                try:
                    message = await asyncio.wait_for(self.ws.recv(), timeout=30.0)
                    await self._process_message(message)
                    
                except asyncio.TimeoutError:
                    # No message for 30 seconds - connection might be dead
                    logger.warning("Flux receive timeout - checking connection health")
                    if self.is_connected:
                        # Send keepalive
                        await self.ws.send(json.dumps({"type": "KeepAlive"}))
                except WebSocketException as e:
                    logger.error(f"Flux WebSocket error: {e}")
                    await self._handle_connection_error(e)
                    break
                    
        except asyncio.CancelledError:
            logger.info("Flux receive loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in Flux receive loop: {e}")
            if not self.is_closing:
                await self._handle_connection_error(e)

    async def _process_message(self, message: str):
        """Process incoming message from Deepgram Flux."""
        try:
            data = json.loads(message)
            msg_type = data.get("type", "")

            if msg_type == "Results":
                await self._handle_results(data)
            elif msg_type == "EagerEndOfTurn":
                await self._handle_eager_end_of_turn(data)
            elif msg_type == "TurnResumed":
                await self._handle_turn_resumed(data)
            elif msg_type == "EndOfTurn":
                await self._handle_end_of_turn(data)
            elif msg_type == "Metadata":
                logger.debug(f"Flux metadata: {data}")
            elif msg_type == "Error":
                error_msg = data.get("message", "Unknown error")
                logger.error(f"Flux error: {error_msg}")
                if self.on_error:
                    await self.on_error(error_msg)
            else:
                logger.debug(f"Unhandled Flux message type: {msg_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Flux message: {e}")
        except Exception as e:
            logger.error(f"Error processing Flux message: {e}")

    async def _handle_results(self, data: dict):
        """
        Handle transcription results from Flux.
        
        Results contain partial and final transcripts with word-level confidence.
        """
        channel = data.get("channel", {})
        alternatives = channel.get("alternatives", [])
        
        if not alternatives:
            return

        alternative = alternatives[0]
        transcript = alternative.get("transcript", "").strip()
        confidence = alternative.get("confidence", 0.0)
        is_final = data.get("is_final", False)

        if not transcript:
            return

        # Dispatch to appropriate callback
        if is_final:
            logger.debug(f"Flux final: '{transcript}' (confidence: {confidence:.2f})")
            await self.on_final_transcript(transcript, confidence)
        else:
            logger.debug(f"Flux partial: '{transcript}' (confidence: {confidence:.2f})")
            await self.on_partial_transcript(transcript, confidence)

    async def _handle_eager_end_of_turn(self, data: dict):
        """
        Handle EagerEndOfTurn event from Flux.
        
        This signals that the user is LIKELY finishing their turn, but may continue.
        Perfect for triggering SPECULATIVE state - start LLM generation but hold output.
        
        If user continues speaking, TurnResumed event will follow.
        """
        # Get the transcript that triggered the eager event
        channel = data.get("channel", {})
        alternatives = channel.get("alternatives", [])
        
        if alternatives:
            alternative = alternatives[0]
            transcript = alternative.get("transcript", "").strip()
            confidence = alternative.get("confidence", 0.0)
            
            logger.info(
                f"🚀 Flux EagerEndOfTurn: '{transcript}' "
                f"(confidence: {confidence:.2f}) - Starting speculative LLM"
            )
            await self.on_eager_end_of_turn(transcript, confidence)
        else:
            logger.warning("EagerEndOfTurn received without transcript")

    async def _handle_turn_resumed(self, data: dict):
        """
        Handle TurnResumed event from Flux.
        
        This means user continued speaking after EagerEndOfTurn was fired.
        Cancel any speculative LLM processing immediately.
        
        This is EXPECTED behavior and should happen 30-50% of the time with
        balanced eager_eot_threshold settings.
        """
        logger.info("🔄 Flux TurnResumed: User continued speaking - cancelling speculative LLM")
        await self.on_turn_resumed()

    async def _handle_end_of_turn(self, data: dict):
        """
        Handle EndOfTurn event from Flux.
        
        This is the CONFIRMED end of user's turn. User has stopped speaking
        according to eot_threshold confidence or eot_timeout_ms elapsed.
        
        Transition SPECULATIVE → COMMITTED (if LLM response ready)
        """
        channel = data.get("channel", {})
        alternatives = channel.get("alternatives", [])
        
        if alternatives:
            alternative = alternatives[0]
            transcript = alternative.get("transcript", "").strip()
            confidence = alternative.get("confidence", 0.0)
            
            logger.info(
                f"✅ Flux EndOfTurn: '{transcript}' "
                f"(confidence: {confidence:.2f}) - Confirming turn completion"
            )
            await self.on_end_of_turn(transcript, confidence)
        else:
            logger.warning("EndOfTurn received without transcript")

    async def _handle_connection_error(self, error: Exception):
        """Handle connection errors with exponential backoff retry."""
        if self.is_closing:
            return

        self.is_connected = False
        self._reconnect_attempts += 1

        if self._reconnect_attempts > self._max_reconnect_attempts:
            error_msg = f"Flux max reconnection attempts ({self._max_reconnect_attempts}) exceeded"
            logger.error(error_msg)
            if self.on_error:
                await self.on_error(error_msg)
            return

        # Exponential backoff: 0s, 1s, 2s, 4s, 8s
        delay = 2 ** (self._reconnect_attempts - 1)
        logger.info(f"Flux reconnecting in {delay}s (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")
        await asyncio.sleep(delay)

        await self.connect()
