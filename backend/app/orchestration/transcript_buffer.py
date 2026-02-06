"""
Transcript buffer for managing partial and final transcripts.

Critical Rule: Partial transcripts are NEVER sent to LLM - UI display only.
Final transcripts are accumulated and locked during COMMITTED state.
"""

import logging
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TranscriptEntry:
    """Single transcript entry with metadata."""

    def __init__(self, text: str, confidence: float, is_final: bool):
        self.text = text
        self.confidence = confidence
        self.is_final = is_final
        self.timestamp = datetime.utcnow()

    def __repr__(self) -> str:
        return f"TranscriptEntry(text='{self.text[:30]}...', confidence={self.confidence:.2f}, is_final={self.is_final})"


class TranscriptBuffer:
    """
    Manages transcript accumulation with separate storage for partial vs final.
    
    Key Features:
    - Separate tracking of partial (UI only) and final (LLM input) transcripts
    - Buffer locking during COMMITTED state to prevent mutations
    - Confidence score tracking
    - Clear separation of concerns for speculative execution
    """

    def __init__(self):
        self._partial_transcripts: List[TranscriptEntry] = []
        self._final_transcripts: List[TranscriptEntry] = []
        self._is_locked = False
        self._current_partial_text = ""

    def add_partial(self, text: str, confidence: float):
        """
        Add a partial transcript (UI display only).
        
        Args:
            text: Partial transcript text
            confidence: STT confidence score (0.0-1.0)
        """
        if self._is_locked:
            logger.warning("Buffer is locked - ignoring partial transcript")
            return

        entry = TranscriptEntry(text, confidence, is_final=False)
        self._partial_transcripts.append(entry)
        self._current_partial_text = text
        logger.debug(f"Added partial transcript: {text[:50]}...")

    def add_final(self, text: str, confidence: float):
        """
        Add a final transcript (will be sent to LLM).
        
        Args:
            text: Final transcript text
            confidence: STT confidence score (0.0-1.0)
        """
        if self._is_locked:
            logger.warning("Buffer is locked - ignoring final transcript")
            return

        entry = TranscriptEntry(text, confidence, is_final=True)
        self._final_transcripts.append(entry)
        self._current_partial_text = ""  # Clear partial on final
        logger.info(f"Added final transcript: {text}")

    def get_final_text(self) -> str:
        """
        Get concatenated final transcript text for LLM input.
        
        Returns:
            All final transcripts joined with spaces
        """
        return " ".join(entry.text for entry in self._final_transcripts)

    def get_current_partial(self) -> str:
        """
        Get the most recent partial transcript for UI display.
        
        Returns:
            Current partial text (empty string if none)
        """
        return self._current_partial_text

    def get_avg_confidence(self) -> float:
        """
        Calculate average confidence across all final transcripts.
        
        Returns:
            Average confidence (0.0-1.0), or 0.0 if no finals
        """
        if not self._final_transcripts:
            return 0.0

        total = sum(entry.confidence for entry in self._final_transcripts)
        return total / len(self._final_transcripts)

    def lock(self):
        """
        Lock the buffer to prevent new transcripts during COMMITTED state.
        
        This ensures transcript consistency while LLM is processing.
        """
        self._is_locked = True
        logger.debug("Buffer locked")

    def unlock(self):
        """Unlock the buffer to allow new transcripts."""
        self._is_locked = False
        logger.debug("Buffer unlocked")

    def is_locked(self) -> bool:
        """Check if buffer is currently locked."""
        return self._is_locked

    def has_final_transcripts(self) -> bool:
        """Check if any final transcripts exist."""
        return len(self._final_transcripts) > 0

    def clear(self):
        """Clear all transcripts and reset state."""
        self._partial_transcripts.clear()
        self._final_transcripts.clear()
        self._current_partial_text = ""
        self._is_locked = False
        logger.debug("Buffer cleared")

    def get_transcript_count(self) -> dict:
        """
        Get counts of partial and final transcripts.
        
        Returns:
            Dict with 'partial' and 'final' counts
        """
        return {
            "partial": len(self._partial_transcripts),
            "final": len(self._final_transcripts),
        }

    def __repr__(self) -> str:
        counts = self.get_transcript_count()
        locked_status = "locked" if self._is_locked else "unlocked"
        return f"TranscriptBuffer(partial={counts['partial']}, final={counts['final']}, {locked_status})"
