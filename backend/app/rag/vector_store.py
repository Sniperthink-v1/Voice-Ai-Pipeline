"""
Pinecone vector store interface for RAG operations.
"""

from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Optional
import logging
import uuid

logger = logging.getLogger(__name__)


class PineconeVectorStore:
    """Interface for Pinecone vector database operations."""
    
    def __init__(
        self,
        api_key: str,
        environment: str,
        index_name: str,
        dimension: int = 1536
    ):
        """
        Initialize Pinecone vector store.
        
        Args:
            api_key: Pinecone API key
            environment: Pinecone environment (e.g., 'ap-southeast-1')
            index_name: Name of the index to use
            dimension: Embedding dimension (default 1536 for text-embedding-3-small)
        """
        self.api_key = api_key
        self.environment = environment
        self.index_name = index_name
        self.dimension = dimension
        
        # Initialize Pinecone client
        self.pc = Pinecone(api_key=api_key)
        
        # Initialize or connect to index
        self._ensure_index_exists()
        
        # Get index connection
        self.index = self.pc.Index(index_name)
        
        logger.info(
            f"Initialized Pinecone: index={index_name}, "
            f"environment={environment}, dimension={dimension}"
        )
    
    def _ensure_index_exists(self):
        """Create index if it doesn't exist."""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]
        
        if self.index_name not in existing_indexes:
            logger.info(f"Creating new Pinecone index: {self.index_name}")
            
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region=self.environment
                )
            )
            logger.info(f"Index {self.index_name} created successfully")
        else:
            logger.info(f"Using existing index: {self.index_name}")
    
    async def upsert_chunks(
        self,
        chunks: List[Dict],
        session_id: str,
        document_id: str
    ) -> int:
        """
        Upload document chunks to Pinecone.
        
        Args:
            chunks: List of chunks with 'embedding', 'text', 'metadata'
            session_id: User session identifier
            document_id: Unique document identifier
            
        Returns:
            Number of vectors upserted
            
        Raises:
            Exception if upsert fails
        """
        if not chunks:
            return 0
        
        try:
            vectors = []
            
            for i, chunk in enumerate(chunks):
                vector_id = f"{document_id}_{i}"
                
                # Prepare metadata (Pinecone has size limits)
                metadata = {
                    "session_id": session_id,
                    "document_id": document_id,
                    "chunk_id": chunk["metadata"].get("chunk_id", i),
                    "filename": chunk["metadata"].get("filename", "unknown"),
                    "format": chunk["metadata"].get("format", "unknown"),
                    "text": chunk["text"][:1000],  # Truncate text to 1000 chars
                    "token_count": chunk["token_count"]
                }
                
                vectors.append({
                    "id": vector_id,
                    "values": chunk["embedding"],
                    "metadata": metadata
                })
            
            # Upsert in batches of 100 (Pinecone limit)
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                self.index.upsert(vectors=batch)
                logger.debug(f"Upserted batch {i // batch_size + 1}")
            
            logger.info(f"Successfully upserted {len(vectors)} vectors for document {document_id}")
            return len(vectors)
            
        except Exception as e:
            logger.error(f"Pinecone upsert failed: {e}")
            raise Exception(f"Failed to upload to vector database: {str(e)}")
    
    async def search(
        self,
        query_embedding: List[float],
        session_id: str,
        top_k: int = 3,
        min_score: float = 0.7
    ) -> List[Dict]:
        """
        Search for similar vectors in Pinecone.
        
        Args:
            query_embedding: Query vector embedding
            session_id: Filter by user session
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            
        Returns:
            List of matches with text, score, metadata
        """
        try:
            # Query WITHOUT session filter for MVP (documents accessible across all sessions)
            # TODO: Add proper user authentication and filter by user_id instead
            logger.debug(f"Querying Pinecone (no session filter for MVP)")
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True,
                # filter={"session_id": session_id}  # Disabled - documents shared across sessions
            )
            
            logger.debug(f"Pinecone returned {len(results.matches)} total matches")
            
            # Log actual similarity scores for debugging
            if results.matches:
                top_scores = [f"{m.score:.3f}" for m in results.matches[:5]]
                logger.info(f"📊 Top similarity scores: {', '.join(top_scores)}")
                
                # Log first match details for debugging low scores
                if results.matches:
                    first_match = results.matches[0]
                    chunk_preview = first_match.metadata.get("text", "")[:150]
                    logger.info(
                        f"🔍 Top match (score={first_match.score:.3f}): "
                        f"'{chunk_preview}...'"
                    )
                    logger.info(
                        f"📄 From: {first_match.metadata.get('filename', 'unknown')} "
                        f"(chunk {first_match.metadata.get('chunk_id', 'N/A')})"
                    )
            
            # Filter by minimum score and extract data
            matches = []
            for match in results.matches:
                if match.score >= min_score:
                    matches.append({
                        "text": match.metadata.get("text", ""),
                        "score": match.score,
                        "filename": match.metadata.get("filename", "unknown"),
                        "chunk_id": match.metadata.get("chunk_id", 0),
                        "metadata": match.metadata
                    })
            
            logger.info(
                f"Search returned {len(matches)} results above score {min_score} "
                f"(total matches: {len(results.matches)})"
            )
            
            return matches
            
        except Exception as e:
            logger.error(f"Pinecone search failed: {e}")
            raise Exception(f"Vector search failed: {str(e)}")
    
    async def delete_by_session(self, session_id: str) -> None:
        """
        Delete all vectors for a session (replace document flow).
        
        Args:
            session_id: Session to delete documents for
        """
        try:
            # Delete with filter (serverless indexes support delete by metadata)
            self.index.delete(filter={"session_id": session_id})
            logger.info(f"Deleted all vectors for session {session_id}")
            
        except Exception as e:
            logger.error(f"Pinecone delete failed: {e}")
            # Non-fatal - log but don't raise
    
    async def delete_by_document(self, document_id: str) -> None:
        """
        Delete all vectors for a specific document.
        
        Args:
            document_id: Document identifier
        """
        try:
            self.index.delete(filter={"document_id": document_id})
            logger.info(f"Deleted all vectors for document {document_id}")
            
        except Exception as e:
            logger.error(f"Pinecone delete failed: {e}")
    
    def get_stats(self) -> Dict:
        """Get index statistics."""
        try:
            stats = self.index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}
