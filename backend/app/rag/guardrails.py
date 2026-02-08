"""
RAG Guardrails - Content safety, prompt injection detection, and hallucination prevention.
"""

from typing import Optional, Dict, List, Tuple
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class GuardrailViolation(Enum):
    """Types of guardrail violations."""
    HARMFUL_CONTENT = "harmful_content"
    PROMPT_INJECTION = "prompt_injection"
    PII_DETECTED = "pii_detected"
    OFF_TOPIC = "off_topic"
    LOW_CONFIDENCE = "low_confidence"
    NO_CONTEXT = "no_context"


class GuardrailResult:
    """Result of a guardrail check."""
    
    def __init__(
        self,
        passed: bool,
        violation: Optional[GuardrailViolation] = None,
        reason: Optional[str] = None,
        sanitized_text: Optional[str] = None,
        confidence: float = 1.0
    ):
        self.passed = passed
        self.violation = violation
        self.reason = reason
        self.sanitized_text = sanitized_text
        self.confidence = confidence
    
    def __repr__(self):
        return f"GuardrailResult(passed={self.passed}, violation={self.violation}, confidence={self.confidence:.2f})"


class RAGGuardrails:
    """
    Comprehensive guardrail system for RAG pipeline.
    
    Responsibilities:
    1. Pre-retrieval: Validate user queries for safety and injection attempts
    2. Post-retrieval: Validate responses for hallucinations and PII
    3. Context validation: Ensure responses are grounded in retrieved documents
    """
    
    def __init__(
        self,
        enable_pii_detection: bool = True,
        enable_prompt_injection_detection: bool = True,
        enable_harmful_content_detection: bool = True,
        min_confidence_threshold: float = 0.3
    ):
        """
        Initialize guardrails.
        
        Args:
            enable_pii_detection: Detect and redact PII
            enable_prompt_injection_detection: Block prompt injection attempts
            enable_harmful_content_detection: Block harmful queries
            min_confidence_threshold: Minimum retrieval confidence to answer
        """
        self.enable_pii_detection = enable_pii_detection
        self.enable_prompt_injection_detection = enable_prompt_injection_detection
        self.enable_harmful_content_detection = enable_harmful_content_detection
        self.min_confidence_threshold = min_confidence_threshold
        
        # Harmful content patterns
        self._harmful_patterns = [
            r'\b(how to (make|build|create) (a )?(bomb|weapon|explosive))\b',
            r'\b(hack|crack|exploit|breach) (into|someone|system)\b',
            r'\b(illegal|unlawful) (activity|activities|drugs|substances)\b',
            r'\b(self[\s-]harm|suicide|kill (myself|yourself))\b',
        ]
        
        # Prompt injection patterns
        self._injection_patterns = [
            r'ignore (previous|all) (instructions?|prompts?|commands?)',
            r'disregard (your|the) (system prompt|instructions?|rules)',
            r'you are now (a |an )?(?!voice|assistant)',  # Role switching
            r'forget (everything|all|your) (you know|instructions?)',
            r'new (system prompt|instructions?|task):',
            r'<\|.*?\|>',  # Special tokens
            r'###\s+(system|user|assistant):',  # Fake chat formatting
            r'\[SYSTEM\]|\[INST\]|\[/INST\]',  # Instruction markers
        ]
        
        # PII patterns (basic detection)
        self._pii_patterns = {
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b(\+?1[\s-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b',
        }
        
        logger.info(
            f"Initialized RAGGuardrails: "
            f"PII={enable_pii_detection}, Injection={enable_prompt_injection_detection}, "
            f"Harmful={enable_harmful_content_detection}, MinConf={min_confidence_threshold}"
        )
    
    def validate_query(self, query: str) -> GuardrailResult:
        """
        Validate user query before RAG retrieval.
        
        Checks for:
        - Harmful content requests
        - Prompt injection attempts
        - PII in query (warn but allow)
        
        Args:
            query: User query text
            
        Returns:
            GuardrailResult with pass/fail and reason
        """
        query_lower = query.lower().strip()
        
        # Check 1: Harmful content
        if self.enable_harmful_content_detection:
            for pattern in self._harmful_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.warning(f"🚫 Harmful query blocked: {query[:50]}...")
                    return GuardrailResult(
                        passed=False,
                        violation=GuardrailViolation.HARMFUL_CONTENT,
                        reason="Query contains potentially harmful content"
                    )
        
        # Check 2: Prompt injection
        if self.enable_prompt_injection_detection:
            for pattern in self._injection_patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.warning(f"🚫 Prompt injection blocked: {query[:50]}...")
                    return GuardrailResult(
                        passed=False,
                        violation=GuardrailViolation.PROMPT_INJECTION,
                        reason="Query appears to contain prompt injection attempt"
                    )
        
        # Check 3: PII detection (warn only, don't block)
        if self.enable_pii_detection:
            detected_pii = []
            for pii_type, pattern in self._pii_patterns.items():
                if re.search(pattern, query):
                    detected_pii.append(pii_type)
            
            if detected_pii:
                logger.warning(f"⚠️ PII detected in query ({', '.join(detected_pii)}): {query[:30]}...")
                # Don't block, but log for audit
        
        logger.debug(f"✅ Query passed guardrails: {query[:50]}")
        return GuardrailResult(passed=True)
    
    def validate_retrieval(
        self,
        query: str,
        results: List[Dict],
        max_score: Optional[float] = None
    ) -> GuardrailResult:
        """
        Validate retrieval results before LLM generation.
        
        Checks for:
        - No results found
        - Low confidence scores
        - Insufficient context
        
        Args:
            query: Original user query
            results: Retrieved document chunks
            max_score: Highest similarity score
            
        Returns:
            GuardrailResult with confidence score
        """
        # Check 1: No results
        if not results:
            logger.warning(f"⚠️ No results for query: {query[:50]}")
            return GuardrailResult(
                passed=False,
                violation=GuardrailViolation.NO_CONTEXT,
                reason="No relevant documents found for this query",
                confidence=0.0
            )
        
        # Check 2: Low confidence
        if max_score is None:
            max_score = max([r.get('score', 0) for r in results], default=0)
        
        if max_score < self.min_confidence_threshold:
            logger.warning(
                f"⚠️ Low confidence retrieval: max_score={max_score:.3f} < {self.min_confidence_threshold}"
            )
            return GuardrailResult(
                passed=False,
                violation=GuardrailViolation.LOW_CONFIDENCE,
                reason=f"Retrieved context has low relevance (score: {max_score:.2f})",
                confidence=max_score
            )
        
        logger.debug(f"✅ Retrieval passed guardrails: {len(results)} results, max_score={max_score:.3f}")
        return GuardrailResult(passed=True, confidence=max_score)
    
    def validate_response(
        self,
        response: str,
        context: str,
        query: str
    ) -> GuardrailResult:
        """
        Validate LLM response before sending to user.
        
        Checks for:
        - PII in response (redact)
        - Hallucination detection (response grounding)
        - Harmful content generation
        
        Args:
            response: LLM generated response
            context: Retrieved context that was provided to LLM
            query: Original user query
            
        Returns:
            GuardrailResult with sanitized text if PII found
        """
        response_lower = response.lower().strip()
        sanitized = response
        
        # Check 1: Harmful content in response
        if self.enable_harmful_content_detection:
            for pattern in self._harmful_patterns:
                if re.search(pattern, response_lower, re.IGNORECASE):
                    logger.error(f"🚫 Harmful response blocked: {response[:50]}...")
                    return GuardrailResult(
                        passed=False,
                        violation=GuardrailViolation.HARMFUL_CONTENT,
                        reason="Response contains harmful content"
                    )
        
        # Check 2: PII redaction
        if self.enable_pii_detection:
            redacted_count = 0
            for pii_type, pattern in self._pii_patterns.items():
                matches = re.findall(pattern, sanitized)
                if matches:
                    # Redact PII
                    sanitized = re.sub(pattern, f'[{pii_type.upper()}_REDACTED]', sanitized)
                    redacted_count += len(matches)
                    logger.warning(f"🔒 Redacted {len(matches)} {pii_type} from response")
            
            if redacted_count > 0:
                return GuardrailResult(
                    passed=True,
                    violation=GuardrailViolation.PII_DETECTED,
                    reason=f"Redacted {redacted_count} PII instances",
                    sanitized_text=sanitized
                )
        
        # Check 3: Simple hallucination detection (check for common hallucination phrases)
        hallucination_markers = [
            r"i don'?t have (access to|information about)",
            r"i (can'?t|cannot) (access|see|read|view) (the |that )?document",
            r"based on (my knowledge|what i know)",  # Should be "based on the document"
            r"as of my (knowledge cutoff|last update)",
        ]
        
        for marker in hallucination_markers:
            if re.search(marker, response_lower, re.IGNORECASE):
                logger.warning(f"⚠️ Possible hallucination detected: {marker}")
                # Don't block, but log for monitoring
        
        logger.debug(f"✅ Response passed guardrails: {response[:50]}")
        return GuardrailResult(passed=True, sanitized_text=sanitized)
    
    def redact_pii(self, text: str) -> Tuple[str, Dict[str, int]]:
        """
        Redact all PII from text.
        
        Args:
            text: Input text
            
        Returns:
            Tuple of (redacted_text, pii_counts)
        """
        redacted = text
        pii_counts = {}
        
        for pii_type, pattern in self._pii_patterns.items():
            matches = re.findall(pattern, redacted)
            if matches:
                count = len(matches)
                redacted = re.sub(pattern, f'[{pii_type.upper()}_REDACTED]', redacted)
                pii_counts[pii_type] = count
        
        return redacted, pii_counts
    
    def check_context_grounding(
        self,
        response: str,
        context: str,
        threshold: float = 0.3
    ) -> Tuple[bool, float]:
        """
        Check if response is grounded in provided context.
        
        Simple implementation: Measure word overlap between response and context.
        More sophisticated: Use embedding similarity (future enhancement).
        
        Args:
            response: LLM response
            context: Retrieved context
            threshold: Minimum overlap ratio
            
        Returns:
            Tuple of (is_grounded, overlap_score)
        """
        # Extract content words (ignore stopwords)
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'is', 'are', 'was', 'were'}
        
        def extract_words(text: str) -> set:
            words = re.findall(r'\b\w+\b', text.lower())
            return {w for w in words if w not in stopwords and len(w) > 3}
        
        response_words = extract_words(response)
        context_words = extract_words(context)
        
        if not response_words:
            return True, 1.0  # Empty response is technically grounded
        
        # Calculate overlap
        overlap = response_words.intersection(context_words)
        overlap_score = len(overlap) / len(response_words)
        
        is_grounded = overlap_score >= threshold
        
        if not is_grounded:
            logger.warning(
                f"⚠️ Low context grounding: {overlap_score:.2f} < {threshold} "
                f"({len(overlap)}/{len(response_words)} words)"
            )
        
        return is_grounded, overlap_score
    
    def create_safe_fallback_response(self, violation: GuardrailViolation) -> str:
        """
        Create a safe fallback response for guardrail violations.
        
        Args:
            violation: Type of violation
            
        Returns:
            Safe fallback message
        """
        fallback_messages = {
            GuardrailViolation.HARMFUL_CONTENT: (
                "I can't help with that request. Let's talk about something else."
            ),
            GuardrailViolation.PROMPT_INJECTION: (
                "I detected an unusual query pattern. Please rephrase your question."
            ),
            GuardrailViolation.NO_CONTEXT: (
                "I don't have information about that in the uploaded documents. "
                "Try asking about topics covered in your files."
            ),
            GuardrailViolation.LOW_CONFIDENCE: (
                "I couldn't find relevant information for that query. "
                "Could you rephrase or ask about a different topic?"
            ),
            GuardrailViolation.OFF_TOPIC: (
                "That question seems outside the scope of your documents. "
                "Try asking about content in your uploaded files."
            ),
        }
        
        return fallback_messages.get(
            violation,
            "I encountered an issue processing your request. Please try again."
        )
