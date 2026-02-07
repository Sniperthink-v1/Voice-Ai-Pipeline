"""
SQLAlchemy models for Voice AI Pipeline database.
Defines schema for sessions, turns, LLM calls, and telemetry.
"""

from sqlalchemy import Column, String, Integer, Float, Boolean, Text, TIMESTAMP, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


class Session(Base):
    """
    Voice agent session.
    Represents a single WebSocket connection and conversation.
    """
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)
    total_turns = Column(Integer, default=0, nullable=False)
    
    # Session metadata
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(50), nullable=True)
    
    def __repr__(self):
        return f"<Session(id={self.id}, created_at={self.created_at}, total_turns={self.total_turns})>"


class Turn(Base):
    """
    Single conversation turn (user speaks → agent responds).
    Tracks transcripts, responses, state history, and metrics.
    """
    __tablename__ = "turns"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Turn content
    user_transcript = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    
    # State machine history (JSONB array of state transitions)
    state_history = Column(JSON, nullable=False, default=list)
    
    # Timestamps
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Turn metrics
    duration_ms = Column(Integer, nullable=True)  # Total turn duration in milliseconds
    was_interrupted = Column(Boolean, default=False, nullable=False)  # True if user barged in
    
    # Transcript confidence
    transcript_confidence = Column(Float, nullable=True)  # Average confidence from Deepgram
    
    def __repr__(self):
        return f"<Turn(id={self.id}, session_id={self.session_id}, was_interrupted={self.was_interrupted})>"


class LLMCall(Base):
    """
    OpenAI LLM API call.
    Tracks all LLM invocations including canceled speculative calls.
    """
    __tablename__ = "llm_calls"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    turn_id = Column(UUID(as_uuid=True), ForeignKey("turns.id", ondelete="CASCADE"), nullable=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Call status
    status = Column(
        String(50), 
        nullable=False
    )  # "completed", "canceled", "failed", "speculative_canceled"
    
    # Call metadata
    model = Column(String(100), nullable=False)  # e.g., "gpt-4-turbo-preview"
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    
    # Performance metrics
    latency_ms = Column(Integer, nullable=True)  # Time to first token
    total_duration_ms = Column(Integer, nullable=True)  # Total call duration
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<LLMCall(id={self.id}, status={self.status}, tokens={self.total_tokens})>"


class TelemetryMetric(Base):
    """
    Telemetry metrics for monitoring and adaptive behavior.
    Stores cancellation rate, latency, tokens wasted, etc.
    """
    __tablename__ = "telemetry"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Metric data
    metric_name = Column(String(100), nullable=False)  # e.g., "cancellation_rate", "turn_latency_ms"
    metric_value = Column(Float, nullable=False)
    
    # Additional context
    metric_metadata = Column(JSON, nullable=True)  # Additional context as JSON
    
    # Timestamp
    recorded_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<TelemetryMetric(metric_name={self.metric_name}, value={self.metric_value})>"


class Document(Base):
    """
    Uploaded document metadata for RAG knowledge base.
    Stores minimal info for UI display; actual content in Pinecone.
    """
    __tablename__ = "documents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    
    # File info
    filename = Column(String(255), nullable=False)
    file_format = Column(String(10), nullable=False)  # 'pdf', 'txt', 'md'
    file_size_bytes = Column(Integer, nullable=False)
    
    # Processing status
    status = Column(
        String(50),
        nullable=False,
        default="pending"
    )  # 'pending', 'processing', 'indexed', 'failed'
    
    # Document metrics
    word_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, nullable=True)
    
    # Timestamps
    uploaded_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    indexed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status}, chunks={self.chunk_count})>"
