"""
Document processor for chunking and embedding text content.
"""

import tiktoken
from typing import List, Dict, Optional
from openai import AsyncOpenAI
from .local_embedder import LocalEmbedder
import logging

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Process documents by chunking and generating embeddings."""
    
    def __init__(
        self,
        local_embedder: Optional[LocalEmbedder] = None,
        openai_client: Optional[AsyncOpenAI] = None,
        use_local: bool = True,
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ):
        """
        Initialize document processor.
        
        Args:
            local_embedder: Local sentence-transformers embedder (faster)
            openai_client: OpenAI async client for embeddings (fallback)
            use_local: Use local embeddings if available
            chunk_size: Target token size for chunks
            chunk_overlap: Token overlap between consecutive chunks
        """
        self.local_embedder = local_embedder
        self.openai_client = openai_client
        self.use_local = use_local and local_embedder is not None
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        
        embedding_source = "local (sentence-transformers)" if self.use_local else "OpenAI API"
        logger.info(
            f"Initialized DocumentProcessor: embedding={embedding_source}, "
            f"chunk_size={chunk_size}, overlap={chunk_overlap}"
        )
    
    def chunk_text(
        self,
        text: str,
        metadata: Dict = None
    ) -> List[Dict]:
        """
        Split text into overlapping chunks based on token count.
        
        Args:
            text: Full text content to chunk
            metadata: Additional metadata to attach to each chunk
            
        Returns:
            List of chunk dicts with text, metadata, token_count
        """
        if not text or not text.strip():
            logger.warning("Attempted to chunk empty text")
            return []
        
        # Tokenize full text
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        # Create overlapping chunks
        start_idx = 0
        chunk_id = 0
        
        while start_idx < len(tokens):
            # Get chunk tokens
            end_idx = start_idx + self.chunk_size
            chunk_tokens = tokens[start_idx:end_idx]
            
            # Decode back to text
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            # Create chunk metadata
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata.update({
                "chunk_id": chunk_id,
                "start_token": start_idx,
                "end_token": end_idx,
                "token_count": len(chunk_tokens)
            })
            
            chunks.append({
                "text": chunk_text,
                "metadata": chunk_metadata,
                "token_count": len(chunk_tokens)
            })
            
            chunk_id += 1
            
            # Move to next chunk with overlap
            start_idx += (self.chunk_size - self.chunk_overlap)
        
        logger.info(f"Created {len(chunks)} chunks from {len(tokens)} tokens")
        return chunks
    
    async def embed_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """
        Generate embeddings for text chunks.
        
        Args:
            chunks: List of chunk dicts from chunk_text()
            
        Returns:
            Same chunks with 'embedding' field added
            
        Raises:
            Exception if embedding generation fails
        """
        if not chunks:
            return []
        
        texts = [chunk["text"] for chunk in chunks]
        
        try:
            logger.info(f"Generating embeddings for {len(texts)} chunks")
            
            # Use local embedder if available (10x faster)
            if self.use_local and self.local_embedder:
                embeddings = await self.local_embedder.get_embeddings_batch(texts)
            # Fallback to OpenAI API
            elif self.openai_client:
                response = await self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=texts,
                    dimensions=1536
                )
                embeddings = [data.embedding for data in response.data]
            else:
                raise Exception("No embedding method available (local or OpenAI)")
            
            # Attach embeddings to chunks
            for i, chunk in enumerate(chunks):
                chunk["embedding"] = embeddings[i]
            
            logger.info(f"Successfully generated {len(chunks)} embeddings")
            return chunks
            
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise Exception(f"Failed to generate embeddings: {str(e)}")
    
    async def process_document(
        self,
        text: str,
        metadata: Dict
    ) -> List[Dict]:
        """
        Complete processing pipeline: chunk + embed.
        
        Args:
            text: Full document text
            metadata: Document metadata (filename, format, etc)
            
        Returns:
            List of chunks with embeddings ready for indexing
        """
        logger.info(f"Processing document: {metadata.get('filename', 'unknown')}")
        
        # Step 1: Chunk text
        chunks = self.chunk_text(text, metadata)
        
        if not chunks:
            raise ValueError("No chunks generated from document")
        
        # Step 2: Generate embeddings
        embedded_chunks = await self.embed_chunks(chunks)
        
        logger.info(
            f"Document processing complete: {len(embedded_chunks)} chunks "
            f"with embeddings"
        )
        
        return embedded_chunks
