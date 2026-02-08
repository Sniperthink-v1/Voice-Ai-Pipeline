"""
RAG retriever for query processing and context retrieval.
"""

from typing import List, Dict, Optional, Union
from openai import AsyncOpenAI
from .vector_store import PineconeVectorStore
from .local_embedder import LocalEmbedder
import logging
import asyncio
import re

logger = logging.getLogger(__name__)


class RAGRetriever:
    """Handle query embedding and document retrieval for RAG."""
    
    def __init__(
        self,
        vector_store: PineconeVectorStore,
        local_embedder: Optional[LocalEmbedder] = None,
        openai_client: Optional[AsyncOpenAI] = None,
        use_local: bool = True,
        top_k: int = 3,
        min_similarity: float = 0.7
    ):
        """
        Initialize RAG retriever.
        
        Args:
            vector_store: Pinecone vector store instance
            local_embedder: Local sentence-transformers embedder (faster)
            openai_client: OpenAI async client for embeddings (fallback)
            use_local: Use local embeddings if available
            top_k: Number of chunks to retrieve
            min_similarity: Minimum similarity score (0-1)
        """
        self.vector_store = vector_store
        self.local_embedder = local_embedder
        self.openai_client = openai_client
        self.use_local = use_local and local_embedder is not None
        self.top_k = top_k
        self.min_similarity = min_similarity
        
        # Simple in-memory cache for query embeddings
        self._embedding_cache: Dict[str, List[float]] = {}
        
        embedding_source = "local (sentence-transformers)" if self.use_local else "OpenAI API"
        logger.info(
            f"Initialized RAGRetriever: embedding={embedding_source}, "
            f"top_k={top_k}, min_similarity={min_similarity}"
        )
    
    async def retrieve(
        self,
        query: str,
        session_id: str,
        timeout_ms: int = 350
    ) -> List[Dict]:
        """
        Retrieve relevant document chunks for a query.
        
        Args:
            query: User query text
            session_id: User session identifier
            timeout_ms: Timeout in milliseconds
            
        Returns:
            List of relevant chunks with text, score, source info
            Returns empty list on timeout or error
        """
        from datetime import datetime
        start_time = datetime.now()
        logger.info(f"🔍 RAG retrieve starting: query='{query[:50]}', session={session_id[:8]}, timeout={timeout_ms}ms")
        
        try:
            # Wrap retrieval with timeout
            result = await asyncio.wait_for(
                self._retrieve_internal(query, session_id),
                timeout=timeout_ms / 1000
            )
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"✅ RAG retrieve completed in {elapsed:.0f}ms with {len(result)} results")
            return result
            
        except asyncio.TimeoutError:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.warning(
                f"RAG retrieval timeout after {timeout_ms}ms (actual: {elapsed:.0f}ms) for query: {query[:50]}"
            )
            return []
            
        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            return []
    
    async def _retrieve_internal(
        self,
        query: str,
        session_id: str
    ) -> List[Dict]:
        """Internal retrieval without timeout wrapper."""
        from datetime import datetime
        start_time = datetime.now()
        logger.info(f"📝 _retrieve_internal STARTED: query='{query}' (len={len(query)}), session={session_id[:8]}")
        
        # Step 0: Rewrite query if needed (commands → semantic queries)
        original_query = query
        rewritten_query, is_summary_query = self._rewrite_query_if_needed(query)
        if rewritten_query != original_query:
            logger.info(f"🔄 Query rewrite: '{original_query}' → '{rewritten_query}' (summary={is_summary_query})")
        else:
            logger.info(f"✓ Query unchanged: '{query}' (summary={is_summary_query})")
        
        # Adjust similarity threshold for summary queries
        adjusted_min_similarity = 0.05 if is_summary_query else self.min_similarity
        adjusted_top_k = self.top_k * 2 if is_summary_query else self.top_k
        logger.info(f"📊 Thresholds: min_sim={adjusted_min_similarity}, top_k={adjusted_top_k}")
        
        # Step 1: Generate query embedding (with caching)
        logger.info("🔄 Step 1: Generating query embedding...")
        query_embedding = await self._get_query_embedding(rewritten_query)
        embedding_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(f"✅ Embedding generated in {embedding_time:.0f}ms")
        
        if not query_embedding:
            logger.warning("Failed to generate query embedding")
            return []
        
        # Step 2: Search vector database
        logger.info(f"🔍 Step 2: Searching Pinecone (top_k={adjusted_top_k}, min_sim={adjusted_min_similarity})...")
        search_start = datetime.now()
        results = await self.vector_store.search(
            query_embedding=query_embedding,
            session_id=session_id,
            top_k=adjusted_top_k,
            min_score=adjusted_min_similarity
        )
        search_time = (datetime.now() - search_start).total_seconds() * 1000
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Trim results back to original top_k if we fetched more for summary
        if is_summary_query and len(results) > self.top_k:
            results = results[:self.top_k]
            logger.info(f"✂️ Trimmed summary results from {adjusted_top_k} to {self.top_k}")
        
        # Log detailed results for debugging
        if results:
            logger.info(f"📋 Retrieved {len(results)} chunks:")
            for i, r in enumerate(results[:3]):  # Log top 3
                score = r.get('score', 0)
                text_preview = r.get('text', '')[:80]
                logger.info(f"  [{i+1}] Score: {score:.3f} | {text_preview}...")
        else:
            logger.warning(f"⚠️ No results above threshold {adjusted_min_similarity:.2f} for query: {original_query}")
        
        # Attach is_summary_query metadata to results for guardrails
        for result in results:
            result['_is_summary_query'] = is_summary_query
            result['_min_threshold'] = adjusted_min_similarity
        
        logger.info(
            f"📊 RAG complete - Embedding: {embedding_time:.0f}ms, Search: {search_time:.0f}ms, "
            f"Total: {total_time:.0f}ms, Results: {len(results)}"
        )
        return results
    
    def _rewrite_query_if_needed(self, query: str) -> tuple[str, bool]:
        """
        Transform command-style queries into semantic queries.
        
        Args:
            query: Original user query
            
        Returns:
            Tuple of (rewritten_query, is_summary_query)
        """
        query_lower = query.lower().strip()
        
        # Pattern 1: Summary/Overview commands
        summary_patterns = [
            (r'^(give me |can you |please )?(a |an )?(summary|overview|brief)', 'main topics key points important information'),
            (r'^summarize (the |this )?(document|file|text|pdf|content)', 'main topics key points important information'),
            (r'^what (is|are) (the )?(main|key) (points?|topics?|ideas?)', 'main topics key points important information'),
            (r'^(tell me |show me )?what.s in (the |this )?(document|file)', 'main topics key points important information'),
        ]
        
        for pattern, replacement in summary_patterns:
            if re.search(pattern, query_lower):
                return replacement, True
        
        # Pattern 2: Remove filler phrases that add no semantic value
        filler_patterns = [
            (r'^(tell me about|show me|explain|describe)\s+', ''),
            (r'^(can you |could you |please |would you )+(tell|show|explain|describe)\s+', ''),
            (r'\s+(please|thanks|thank you)$', ''),
        ]
        
        rewritten = query_lower
        modified = False
        for pattern, replacement in filler_patterns:
            new_text = re.sub(pattern, replacement, rewritten).strip()
            if new_text != rewritten:
                rewritten = new_text
                modified = True
        
        # Pattern 3: Detect if it's a summary query even without rewriting
        is_summary = any(word in query_lower for word in [
            'summarize', 'summary', 'overview', 'brief', 'main points', 'key points',
            'what does it say', 'what is in', 'tell me about the document'
        ])
        
        # Return rewritten query or original if no changes
        final_query = rewritten if modified else query
        return final_query, is_summary
    
    async def _get_query_embedding(self, query: str) -> Optional[List[float]]:
        """
        Generate embedding for query with caching.
        
        Args:
            query: Query text
            
        Returns:
            Embedding vector or None on failure
        """
        # Normalize query for cache key
        cache_key = query.lower().strip()
        
        # Check cache
        if cache_key in self._embedding_cache:
            logger.debug("Cache hit for query embedding")
            return self._embedding_cache[cache_key]
        
        try:
            # Use local embedder if available (10x faster)
            if self.use_local and self.local_embedder:
                embedding = await self.local_embedder.get_embedding(query)
            # Fallback to OpenAI API
            elif self.openai_client:
                response = await self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=query,
                    dimensions=1536
                )
                embedding = response.data[0].embedding
            else:
                logger.error("No embedding method available (local or OpenAI)")
                return None
            
            if not embedding:
                return None
            
            # Cache for future queries (limit cache size)
            if len(self._embedding_cache) >= 100:
                # Remove oldest entry (simple FIFO)
                oldest_key = next(iter(self._embedding_cache))
                del self._embedding_cache[oldest_key]
            
            self._embedding_cache[cache_key] = embedding
            
            logger.debug("Generated and cached query embedding")
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return None
    
    def clear_cache(self):
        """Clear the embedding cache."""
        self._embedding_cache.clear()
        logger.info("Cleared embedding cache")
    
    @property
    def cache_size(self) -> int:
        """Get current cache size."""
        return len(self._embedding_cache)
