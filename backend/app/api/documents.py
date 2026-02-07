"""
Document upload and management API endpoints.
"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import uuid
import os
import tempfile
import logging
from datetime import datetime

from ..db.postgres import get_db_session
from ..db.models import Document
from ..rag.file_parsers import FileParser
from ..rag.document_processor import DocumentProcessor
from ..rag.vector_store import PineconeVectorStore
from ..config import settings
from openai import AsyncOpenAI
from ..rag.local_embedder import LocalEmbedder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

# Initialize embedding clients
local_embedder = None
openai_client = None

if settings.rag_use_local_embeddings:
    logger.info("Initializing local embedding model (sentence-transformers)...")
    local_embedder = LocalEmbedder()
else:
    logger.info("Using OpenAI API for embeddings")
    import httpx
    openai_client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=httpx.Timeout(30.0, read=60.0)
    )

# Initialize Pinecone vector store (singleton)
vector_store = None

def get_vector_store() -> PineconeVectorStore:
    """Get or initialize vector store."""
    global vector_store
    if vector_store is None:
        vector_store = PineconeVectorStore(
            api_key=settings.pinecone_api_key,
            environment=settings.pinecone_environment,
            index_name=settings.pinecone_index_name,
            dimension=settings.pinecone_dimension
        )
    return vector_store


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    chunk_size: int = Form(default=500),
    chunk_overlap: int = Form(default=50),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Upload and process a document for RAG.
    
    Synchronous processing - returns only after indexing complete.
    
    Args:
        file: Uploaded file (PDF, TXT, MD)
        session_id: User session identifier
        chunk_size: Token size for chunks (100-2000)
        chunk_overlap: Token overlap between chunks (0-500)
        db: Database session
        
    Returns:
        Document metadata with processing status
    """
    try:
        # Validate file format
        if not FileParser.is_supported(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format. Supported: PDF, TXT, MD"
            )
        
        # Validate file size
        file_content = await file.read()
        file_size = len(file_content)
        
        if not FileParser.validate_file_size(file_size):
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {FileParser.MAX_FILE_SIZE_MB}MB"
            )
        
        # Validate chunking parameters
        if not (100 <= chunk_size <= 2000):
            raise HTTPException(status_code=400, detail="chunk_size must be between 100-2000")
        if not (0 <= chunk_overlap <= 500):
            raise HTTPException(status_code=400, detail="chunk_overlap must be between 0-500")
        if chunk_overlap >= chunk_size:
            raise HTTPException(status_code=400, detail="chunk_overlap must be less than chunk_size")
        
        logger.info(
            f"Starting document upload: {file.filename}, "
            f"size={file_size}, session={session_id}"
        )
        
        # Step 1: Delete existing documents for this session (1 file per session)
        await delete_session_documents(session_id, db)
        
        # Step 2: Create database entry
        document_id = str(uuid.uuid4())
        doc_entry = Document(
            id=uuid.UUID(document_id),
            session_id=uuid.UUID(session_id),
            filename=file.filename,
            file_format=os.path.splitext(file.filename)[1][1:].lower(),
            file_size_bytes=file_size,
            status="processing"
        )
        db.add(doc_entry)
        await db.commit()
        
        # Step 3: Save file temporarily for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            tmp_file.write(file_content)
            tmp_path = tmp_file.name
        
        try:
            # Step 4: Parse file to extract text
            logger.info(f"Parsing file: {file.filename}")
            parsed_data = await FileParser.parse(tmp_path, file.filename)
            
            # Update word count
            await db.execute(
                update(Document)
                .where(Document.id == uuid.UUID(document_id))
                .values(word_count=parsed_data["word_count"])
            )
            await db.commit()
            
            logger.info(f"Extracted {parsed_data['word_count']} words from {file.filename}")
            
            # Step 5: Process document (chunk + embed)
            logger.info(f"Processing document with chunk_size={chunk_size}, overlap={chunk_overlap}")
            
            processor = DocumentProcessor(
                local_embedder=local_embedder,
                openai_client=openai_client,
                use_local=settings.rag_use_local_embeddings,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap
            )
            
            chunks = await processor.process_document(
                text=parsed_data["text"],
                metadata=parsed_data["metadata"]
            )
            
            logger.info(f"Generated {len(chunks)} chunks with embeddings")
            
            # Step 6: Upload to Pinecone
            logger.info(f"Uploading to Pinecone index: {settings.pinecone_index_name}")
            
            vs = get_vector_store()
            vector_count = await vs.upsert_chunks(
                chunks=chunks,
                session_id=session_id,
                document_id=document_id
            )
            
            # Step 7: Update database with success
            await db.execute(
                update(Document)
                .where(Document.id == uuid.UUID(document_id))
                .values(
                    status="indexed",
                    chunk_count=vector_count,
                    indexed_at=datetime.utcnow()
                )
            )
            await db.commit()
            
            logger.info(
                f"Document {file.filename} indexed successfully: "
                f"{vector_count} chunks"
            )
            
            # Step 8: Return success response
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "document_id": document_id,
                    "filename": file.filename,
                    "status": "indexed",
                    "word_count": parsed_data["word_count"],
                    "chunk_count": vector_count,
                    "message": f"Document indexed with {vector_count} chunks"
                }
            )
            
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Document upload failed: {e}", exc_info=True)
        
        # Update database with error
        try:
            await db.execute(
                update(Document)
                .where(Document.id == uuid.UUID(document_id))
                .values(
                    status="failed",
                    error_message=str(e)
                )
            )
            await db.commit()
        except:
            pass
        
        raise HTTPException(
            status_code=500,
            detail=f"Document processing failed: {str(e)}"
        )


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Delete a document and its vectors."""
    try:
        # Get document
        result = await db.execute(
            select(Document).where(Document.id == uuid.UUID(document_id))
        )
        doc = result.scalar_one_or_none()
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from Pinecone
        vs = get_vector_store()
        await vs.delete_by_document(document_id)
        
        # Delete from database
        await db.delete(doc)
        await db.commit()
        
        logger.info(f"Deleted document: {document_id}")
        
        return {"success": True, "message": "Document deleted"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/list")
async def list_documents(
    session_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """List all documents for a session."""
    try:
        result = await db.execute(
            select(Document)
            .where(Document.session_id == uuid.UUID(session_id))
            .order_by(Document.uploaded_at.desc())
        )
        docs = result.scalars().all()
        
        return {
            "documents": [
                {
                    "id": str(doc.id),
                    "filename": doc.filename,
                    "format": doc.file_format,
                    "status": doc.status,
                    "word_count": doc.word_count,
                    "chunk_count": doc.chunk_count,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "indexed_at": doc.indexed_at.isoformat() if doc.indexed_at else None,
                    "error": doc.error_message
                }
                for doc in docs
            ]
        }
    
    except Exception as e:
        logger.error(f"List documents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def delete_session_documents(session_id: str, db: AsyncSession):
    """Delete all documents for a session (called before new upload)."""
    try:
        # Get all documents
        result = await db.execute(
            select(Document).where(Document.session_id == uuid.UUID(session_id))
        )
        docs = result.scalars().all()
        
        if docs:
            # Delete from Pinecone
            vs = get_vector_store()
            await vs.delete_by_session(session_id)
            
            # Delete from database
            for doc in docs:
                await db.delete(doc)
            
            await db.commit()
            logger.info(f"Deleted {len(docs)} existing documents for session {session_id}")
    
    except Exception as e:
        logger.error(f"Failed to delete session documents: {e}")
        # Non-fatal - continue with upload
