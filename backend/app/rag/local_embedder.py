"""
Local embedding generation using sentence-transformers.

Provides 10x faster embeddings than OpenAI API with no network latency.
"""

import asyncio
import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class LocalEmbedder:
    """
    Local embedding model using sentence-transformers.
    
    Uses all-MiniLM-L6-v2: 384 dimensions, 80MB model size, ~50-200ms on CPU.
    Loads once at startup and kept in memory for fast inference.
    """
    
    MODEL_NAME = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION = 384
    
    def __init__(self):
        """Load the embedding model into memory."""
        logger.info(f"Loading local embedding model: {self.MODEL_NAME}")
        self.model = SentenceTransformer(self.MODEL_NAME)
        
        # Verify dimensions match expected
        actual_dim = self.model.get_sentence_embedding_dimension()
        if actual_dim != self.EMBEDDING_DIMENSION:
            raise ValueError(
                f"Model dimension mismatch: expected {self.EMBEDDING_DIMENSION}, "
                f"got {actual_dim}"
            )
        
        logger.info(
            f"✅ Local embedding model loaded: {self.MODEL_NAME} "
            f"({self.EMBEDDING_DIMENSION} dimensions)"
        )
    
    async def get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text using local model.
        
        Args:
            text: Input text to embed
            
        Returns:
            Embedding vector (384 dimensions) or None on failure
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return None
        
        try:
            # Run in thread pool to avoid blocking async event loop
            # sentence-transformers is CPU-bound and synchronous
            embedding = await asyncio.to_thread(
                self._encode_sync,
                text
            )
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Failed to generate local embedding: {e}", exc_info=True)
            return None
    
    def _encode_sync(self, text: str):
        """
        Synchronous encoding (called from thread pool).
        
        Args:
            text: Text to encode
            
        Returns:
            Numpy array with embedding
        """
        # normalize_embeddings=True ensures vectors are unit length
        # This is important for cosine similarity in vector search
        return self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False
        )
    
    async def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batch (more efficient).
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        try:
            # Batch encoding is faster than individual calls
            embeddings = await asyncio.to_thread(
                self._encode_batch_sync,
                texts
            )
            return [emb.tolist() for emb in embeddings]
            
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}", exc_info=True)
            return []
    
    def _encode_batch_sync(self, texts: List[str]):
        """Synchronous batch encoding."""
        return self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32
        )
