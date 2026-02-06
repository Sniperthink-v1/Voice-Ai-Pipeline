"""
Pydantic models for WebSocket messages.
All message schemas are defined here as per api.md specification.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class StateEnum(str, Enum):
    """Voice agent states."""
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    SPECULATIVE = "SPECULATIVE"
    COMMITTED = "COMMITTED"
    SPEAKING = "SPEAKING"


class AudioFormat(str, Enum):
    """Audio format types."""
    WAV = "wav"
    WEBM = "webm"
    PCM = "pcm"


# ============================================================================
# Client → Server Messages
# ============================================================================

class ConnectMessage(BaseModel):
    """
    Sent on initial connection to establish session.
    """
    type: Literal["connect"] = "connect"
    data: dict = Field(default_factory=dict)


class AudioChunkData(BaseModel):
    """Audio chunk data payload."""
    audio: str = Field(
        ...,
        description="Base64-encoded audio data"
    )
    format: AudioFormat = Field(
        ...,
        description="Audio format: wav, webm, or pcm"
    )
    sample_rate: int = Field(
        ...,
        ge=8000,
        le=48000,
        description="Sample rate in Hz (recommended: 16000)"
    )


class AudioChunkMessage(BaseModel):
    """
    Sent when microphone audio is captured.
    Streams user audio to backend for STT.
    """
    type: Literal["audio_chunk"] = "audio_chunk"
    data: AudioChunkData


class InterruptData(BaseModel):
    """Interrupt data payload."""
    timestamp: int = Field(
        ...,
        description="Unix timestamp in milliseconds"
    )


class InterruptMessage(BaseModel):
    """
    Sent when user wants to interrupt agent.
    Triggers barge-in, cancels agent speech.
    """
    type: Literal["interrupt"] = "interrupt"
    data: InterruptData


class UpdateSettingsData(BaseModel):
    """Settings update data payload."""
    silence_debounce_ms: Optional[int] = Field(
        None,
        ge=400,
        le=1200,
        description="Silence debounce in milliseconds"
    )
    cancellation_threshold: Optional[float] = Field(
        None,
        ge=0.1,
        le=0.5,
        description="Cancellation rate threshold"
    )
    adaptive_debounce_enabled: Optional[bool] = Field(
        None,
        description="Enable adaptive debounce"
    )
    voice_id: Optional[str] = Field(
        None,
        description="ElevenLabs voice ID"
    )
    llm_model: Optional[str] = Field(
        None,
        description="OpenAI model name"
    )


class UpdateSettingsMessage(BaseModel):
    """
    Sent when user changes settings in UI.
    Updates backend configuration in real-time.
    """
    type: Literal["update_settings"] = "update_settings"
    data: UpdateSettingsData


class DisconnectMessage(BaseModel):
    """
    Sent when user closes connection.
    Clean disconnect.
    """
    type: Literal["disconnect"] = "disconnect"
    data: dict = Field(default_factory=dict)


class PingMessage(BaseModel):
    """
    Heartbeat ping message.
    """
    type: Literal["ping"] = "ping"
    data: dict = Field(default_factory=dict)


class PongMessage(BaseModel):
    """
    Heartbeat pong response.
    """
    type: Literal["pong"] = "pong"
    data: dict = Field(default_factory=dict)


class GetHistoryMessage(BaseModel):
    """
    Request conversation history.
    """
    type: Literal["get_history"] = "get_history"
    data: dict = Field(default_factory=dict)


# ============================================================================
# Server → Client Messages
# ============================================================================

class SessionReadyData(BaseModel):
    """Session ready data payload."""
    session_id: str = Field(
        ...,
        description="UUID of created session"
    )
    timestamp: int = Field(
        ...,
        description="Unix timestamp in milliseconds"
    )


class SessionReadyMessage(BaseModel):
    """
    Sent on successful connection.
    Confirms session created.
    """
    type: Literal["session_ready"] = "session_ready"
    data: SessionReadyData


class StateChangeData(BaseModel):
    """State change data payload."""
    from_state: StateEnum = Field(
        ...,
        description="Previous state"
    )
    to_state: StateEnum = Field(
        ...,
        description="New state"
    )
    timestamp: int = Field(
        ...,
        description="Unix timestamp in milliseconds"
    )


class StateChangeMessage(BaseModel):
    """
    Sent on state machine transition.
    Informs frontend of current state.
    """
    type: Literal["state_change"] = "state_change"
    data: StateChangeData


class TranscriptPartialData(BaseModel):
    """Partial transcript data payload."""
    text: str = Field(
        ...,
        description="Partial transcript text"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0"
    )
    timestamp: int = Field(
        ...,
        description="Unix timestamp in milliseconds"
    )


class TranscriptPartialMessage(BaseModel):
    """
    Sent when Deepgram sends interim transcript.
    For UI display only, NOT sent to LLM.
    """
    type: Literal["transcript_partial"] = "transcript_partial"
    data: TranscriptPartialData


class TranscriptFinalData(BaseModel):
    """Final transcript data payload."""
    text: str = Field(
        ...,
        description="Final transcript text"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0"
    )
    timestamp: int = Field(
        ...,
        description="Unix timestamp in milliseconds"
    )


class TranscriptFinalMessage(BaseModel):
    """
    Sent when Deepgram sends final transcript.
    Triggers silence debounce timer.
    """
    type: Literal["transcript_final"] = "transcript_final"
    data: TranscriptFinalData


class AgentAudioChunkData(BaseModel):
    """Agent audio chunk data payload."""
    audio: str = Field(
        ...,
        description="Base64-encoded audio data"
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="Sequential index for ordering"
    )
    is_final: bool = Field(
        ...,
        description="True if last chunk"
    )


class AgentAudioChunkMessage(BaseModel):
    """
    Sent when TTS generates audio chunk.
    Streams agent audio to frontend for playback.
    """
    type: Literal["agent_audio_chunk"] = "agent_audio_chunk"
    data: AgentAudioChunkData


class AgentTextFallbackData(BaseModel):
    """Agent text fallback data payload."""
    text: str = Field(
        ...,
        description="Agent response text"
    )
    reason: str = Field(
        ...,
        description="Failure reason"
    )


class AgentTextFallbackMessage(BaseModel):
    """
    Sent when TTS fails.
    Display agent response as text when audio unavailable.
    """
    type: Literal["agent_text_fallback"] = "agent_text_fallback"
    data: AgentTextFallbackData


class TurnCompleteData(BaseModel):
    """Turn complete data payload."""
    turn_id: str = Field(
        ...,
        description="UUID of turn"
    )
    user_text: str = Field(
        ...,
        description="User transcript"
    )
    agent_text: str = Field(
        ...,
        description="Agent response"
    )
    duration_ms: int = Field(
        ...,
        ge=0,
        description="Turn duration in milliseconds"
    )
    was_interrupted: bool = Field(
        ...,
        description="True if user interrupted"
    )
    timestamp: int = Field(
        ...,
        description="Unix timestamp in milliseconds"
    )


class TurnCompleteMessage(BaseModel):
    """
    Sent when turn finished successfully.
    Logs turn in history, updates UI.
    """
    type: Literal["turn_complete"] = "turn_complete"
    data: TurnCompleteData


class TelemetryData(BaseModel):
    """Telemetry data payload."""
    cancellation_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Cancellation rate 0.0-1.0"
    )
    avg_debounce_ms: int = Field(
        ...,
        ge=0,
        description="Current average debounce in milliseconds"
    )
    turn_latency_ms: int = Field(
        ...,
        ge=0,
        description="Average latency from speech end to first audio"
    )
    total_turns: int = Field(
        ...,
        ge=0,
        description="Total completed turns"
    )
    tokens_wasted: int = Field(
        ...,
        ge=0,
        description="Tokens from canceled LLM calls"
    )
    interruption_count: int = Field(
        ...,
        ge=0,
        description="Number of barge-ins"
    )


class TelemetryMessage(BaseModel):
    """
    Sent every 5 turns or on request.
    Updates metrics in UI.
    """
    type: Literal["telemetry"] = "telemetry"
    data: TelemetryData


class ErrorData(BaseModel):
    """Error data payload."""
    code: str = Field(
        ...,
        description="Error code"
    )
    message: str = Field(
        ...,
        description="Human-readable error message"
    )
    recoverable: bool = Field(
        ...,
        description="True if system can recover automatically"
    )
    timestamp: int = Field(
        ...,
        description="Unix timestamp in milliseconds"
    )


class ErrorMessage(BaseModel):
    """
    Sent when error occurs.
    Notifies frontend of issues.
    """
    type: Literal["error"] = "error"
    data: ErrorData


# ============================================================================
# Union Types for Message Routing
# ============================================================================

# All possible client messages
ClientMessage = (
    ConnectMessage |
    AudioChunkMessage |
    InterruptMessage |
    UpdateSettingsMessage |
    DisconnectMessage |
    PingMessage |
    PongMessage |
    GetHistoryMessage
)

# All possible server messages
ServerMessage = (
    SessionReadyMessage |
    StateChangeMessage |
    TranscriptPartialMessage |
    TranscriptFinalMessage |
    AgentAudioChunkMessage |
    AgentTextFallbackMessage |
    TurnCompleteMessage |
    TelemetryMessage |
    ErrorMessage |
    PingMessage
)
