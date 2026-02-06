"""
Database connection and session management.
Provides async SQLAlchemy engine and session factory.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    AsyncEngine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.config import settings
from app.db.models import Base

logger = logging.getLogger(__name__)


class Database:
    """
    Database connection manager.
    Handles engine creation, session management, and connection pooling.
    """
    
    def __init__(self):
        """Initialize database connection."""
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
    
    def init_engine(self) -> AsyncEngine:
        """
        Create async SQLAlchemy engine with connection pooling.
        
        Returns:
            Configured async engine
        """
        if self.engine is not None:
            return self.engine
        
        logger.info(f"Initializing database connection...")
        
        # Create async engine with connection pooling
        # Note: asyncpg doesn't use pool_size/max_overflow, uses poolclass instead
        self.engine = create_async_engine(
            settings.database_url,
            echo=settings.is_development,  # Log SQL in development
            pool_pre_ping=True,  # Validate connections before use
            pool_recycle=3600,  # Recycle connections after 1 hour
        )
        
        # Create session factory
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        logger.info("Database engine initialized successfully")
        return self.engine
    
    async def create_tables(self):
        """
        Create all database tables.
        Use only for testing - production should use Alembic migrations.
        """
        if self.engine is None:
            self.init_engine()
        
        logger.info("Creating database tables...")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created successfully")
    
    async def drop_tables(self):
        """
        Drop all database tables.
        Use only for testing.
        """
        if self.engine is None:
            self.init_engine()
        
        logger.warning("Dropping all database tables...")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("Database tables dropped")
    
    async def health_check(self) -> bool:
        """
        Check database connection health.
        
        Returns:
            True if database is accessible, False otherwise
        """
        if self.engine is None:
            return False
        
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get async database session.
        Use as context manager to ensure proper cleanup.
        
        Example:
            async with db.get_session() as session:
                result = await session.execute(query)
        
        Yields:
            Async database session
        """
        if self.session_factory is None:
            self.init_engine()
        
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}", exc_info=True)
            raise
        finally:
            await session.close()
    
    async def close(self):
        """Close database engine and cleanup connections."""
        if self.engine is not None:
            logger.info("Closing database connections...")
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            logger.info("Database connections closed")


# Global database instance
db = Database()


# Helper function for getting session
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function for FastAPI to inject database sessions.
    
    Usage in FastAPI route:
        @app.get("/endpoint")
        async def endpoint(session: AsyncSession = Depends(get_db_session)):
            ...
    
    Yields:
        Async database session
    """
    async with db.get_session() as session:
        yield session
