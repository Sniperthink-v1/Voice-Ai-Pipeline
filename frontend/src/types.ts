/**
 * Global TypeScript type definitions.
 * Matches WebSocket message schemas from backend.
 */

// ============================================================================
// State Types
// ============================================================================

export type TurnState = "IDLE" | "LISTENING" | "SPECULATIVE" | "COMMITTED" | "SPEAKING";

export type AudioFormat = "wav" | "webm" | "pcm";

// ============================================================================
// Client -> Server Messages
// ============================================================================

export interface ConnectMessage {
  type: "connect";
  data: Record<string, never>;
}

export interface AudioChunkMessage {
  type: "audio_chunk";
  data: {
    audio: string; // Base64-encoded audio
    format: AudioFormat;
    sample_rate: number;
  };
}

export interface InterruptMessage {
  type: "interrupt";
  data: {
    timestamp: number; // Unix timestamp in milliseconds
  };
}

export interface UpdateSettingsMessage {
  type: "update_settings";
  data: {
    silence_debounce_ms?: number;
    cancellation_threshold?: number;
    adaptive_debounce_enabled?: boolean;
    voice_id?: string;
    llm_model?: string;
  };
}

export interface DisconnectMessage {
  type: "disconnect";
  data: Record<string, never>;
}

export interface PingMessage {
  type: "ping";
  data: Record<string, never>;
}

export interface PongMessage {
  type: "pong";
  data: Record<string, never>;
}

export type ClientMessage =
  | ConnectMessage
  | AudioChunkMessage
  | InterruptMessage
  | UpdateSettingsMessage
  | DisconnectMessage
  | PingMessage
  | PongMessage;

// ============================================================================
// Server -> Client Messages
// ============================================================================

export interface SessionReadyMessage {
  type: "session_ready";
  data: {
    session_id: string;
    timestamp: number;
  };
}

export interface StateChangeMessage {
  type: "state_change";
  data: {
    from_state: TurnState;
    to_state: TurnState;
    timestamp: number;
  };
}

export interface TranscriptPartialMessage {
  type: "transcript_partial";
  data: {
    text: string;
    confidence: number;
    timestamp: number;
  };
}

export interface TranscriptFinalMessage {
  type: "transcript_final";
  data: {
    text: string;
    confidence: number;
    timestamp: number;
  };
}

export interface AgentAudioChunkMessage {
  type: "agent_audio_chunk";
  data: {
    audio: string; // Base64-encoded audio
    chunk_index: number;
    is_final: boolean;
  };
}

export interface AgentTextFallbackMessage {
  type: "agent_text_fallback";
  data: {
    text: string;
    reason: string;
  };
}

export interface TurnCompleteMessage {
  type: "turn_complete";
  data: {
    turn_id: string;
    user_text: string;
    agent_text: string;
    duration_ms: number;
    was_interrupted: boolean;
    timestamp: number;
  };
}

export interface TelemetryMessage {
  type: "telemetry";
  data: {
    cancellation_rate: number;
    avg_debounce_ms: number;
    turn_latency_ms: number;
    total_turns: number;
    tokens_wasted: number;
    interruption_count: number;
  };
}

export interface ErrorMessage {
  type: "error";
  data: {
    code: string;
    message: string;
    recoverable: boolean;
    timestamp: number;
  };
}

export type ServerMessage =
  | SessionReadyMessage
  | StateChangeMessage
  | TranscriptPartialMessage
  | TranscriptFinalMessage
  | AgentAudioChunkMessage
  | AgentTextFallbackMessage
  | TurnCompleteMessage
  | TelemetryMessage
  | ErrorMessage
  | PingMessage;

// ============================================================================
// UI State Types
// ============================================================================

export interface Turn {
  id: string;
  userText: string;
  agentText: string;
  timestamp: number;
  wasInterrupted: boolean;
  duration: number;
}

export interface TelemetryData {
  cancellationRate: number;
  avgDebounceMs: number;
  turnLatencyMs: number;
  totalTurns: number;
  tokensWasted: number;
  interruptionCount: number;
}

export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "reconnecting";
