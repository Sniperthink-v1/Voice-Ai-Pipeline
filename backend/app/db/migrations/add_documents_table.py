"""
Database migration: Add documents table for RAG.

Run with: python -m backend.app.db.migrations.add_documents_table
"""

import asyncio
from sqlalchemy import text
from app.db.postgres import db
from app.db.models import Base, Document
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate():
    """Create documents table."""
    try:
        db.init_engine()
        
        async with db.engine.begin() as conn:
            # Create documents table
            await conn.run_sync(Base.metadata.create_all)
            
            logger.info("✅ Documents table created successfully")
            
            # Verify table exists
            result = await conn.execute(
                text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'documents'
                """)
            )
            
            if result.fetchone():
                logger.info("✅ Verified documents table exists")
            else:
                logger.error("❌ Documents table not found after creation")
        
        await db.close()
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(migrate())
