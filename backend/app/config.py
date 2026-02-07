"""
Configuration management using Pydantic Settings.
Loads all environment variables with validation.
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses .env file in development, environment variables in production.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # API Keys
    deepgram_api_key: str = Field(
        ...,
        description="Deepgram API key for speech-to-text"
    )
    openai_api_key: str = Field(
        ...,
        description="OpenAI API key for language model"
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="OpenAI model to use (gpt-4o-mini for speed/cost, gpt-4o for accuracy)"
    )
    openai_organization_id: Optional[str] = Field(
        default=None,
        description="OpenAI organization ID for priority API access"
    )
    openai_project_id: Optional[str] = Field(
        default=None,
        description="OpenAI project ID for usage tracking"
    )
    openai_use_priority_api: bool = Field(
        default=True,
        description="Use OpenAI priority API tier for lower latency"
    )
    elevenlabs_api_key: str = Field(
        ...,
        description="ElevenLabs API key for text-to-speech"
    )
    elevenlabs_voice_id: str = Field(
        default="21m00Tcm4TlvDq8ikWAM",
        description="ElevenLabs voice ID (default: Rachel)"
    )

    # Pinecone (RAG)
    pinecone_api_key: str = Field(
        ...,
        description="Pinecone API key for vector database"
    )
    pinecone_environment: str = Field(
        default="ap-southeast-1",
        description="Pinecone environment/region (ap-southeast-1 for Singapore)"
    )
    pinecone_index_name: str = Field(
        default="voice-agent-kb",
        description="Pinecone index name for knowledge base"
    )
    pinecone_dimension: int = Field(
        default=1536,
        description="Embedding dimension (1536 for text-embedding-3-small)"
    )

    # RAG Settings
    rag_use_local_embeddings: bool = Field(
        True,
        description="Use local sentence-transformers (faster) vs OpenAI API"
    )
    rag_chunk_size: int = Field(
        ...,
        ge=100,
        le=2000,
        description="Token size for document chunks"
    )
    rag_chunk_overlap: int = Field(
        ...,
        ge=0,
        le=500,
        description="Token overlap between chunks"
    )
    rag_top_k: int = Field(
        ...,
        ge=1,
        le=10,
        description="Number of chunks to retrieve"
    )
    rag_min_similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score for retrieval"
    )
    rag_timeout_ms: int = Field(
        ...,
        ge=100,
        le=10000,
        description="RAG retrieval timeout in milliseconds"
    )

    # Database
    database_url: str = Field(
        ...,
        description="PostgreSQL connection URL with asyncpg driver"
    )

    # Environment
    environment: str = Field(
        default="development",
        description="Environment: development, staging, or production"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )

    # Voice Agent Settings
    min_silence_debounce_ms: int = Field(
        default=400,
        ge=200,
        le=1000,
        description="Minimum silence debounce in milliseconds"
    )
    max_silence_debounce_ms: int = Field(
        default=1200,
        ge=500,
        le=3000,
        description="Maximum silence debounce in milliseconds"
    )
    cancellation_rate_threshold: float = Field(
        default=0.30,
        ge=0.1,
        le=0.5,
        description="Cancellation rate threshold for adaptive debounce"
    )

    # Server Settings
    host: str = Field(
        default="0.0.0.0",
        description="Server host address"
    )
    port: int = Field(
        default=8000,
        ge=1000,
        le=65535,
        description="Server port"
    )

    # CORS
    frontend_url: str = Field(
        default="http://localhost:5173",
        description="Frontend URL for CORS"
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return v_upper

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate environment is one of the allowed values."""
        allowed = ["development", "staging", "production"]
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v_lower

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"


# Global settings instance
settings = Settings()
