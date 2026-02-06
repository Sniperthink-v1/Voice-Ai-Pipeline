"""
Unit tests for TranscriptBuffer.

Tests the critical rule: partial transcripts never sent to LLM.
"""

import pytest
from app.orchestration.transcript_buffer import TranscriptBuffer


class TestTranscriptBuffer:
    """Test transcript buffer functionality."""

    def test_initialization(self):
        """Test buffer starts empty and unlocked."""
        buffer = TranscriptBuffer()
        assert buffer.get_final_text() == ""
        assert buffer.get_current_partial() == ""
        assert not buffer.is_locked()
        assert not buffer.has_final_transcripts()

    def test_add_partial_transcript(self):
        """Test adding partial transcripts (UI only)."""
        buffer = TranscriptBuffer()
        buffer.add_partial("Hello", 0.95)
        
        # Partial should be retrievable
        assert buffer.get_current_partial() == "Hello"
        
        # But NOT in final text (critical rule)
        assert buffer.get_final_text() == ""
        assert not buffer.has_final_transcripts()

    def test_add_final_transcript(self):
        """Test adding final transcripts (LLM input)."""
        buffer = TranscriptBuffer()
        buffer.add_final("Hello world", 0.92)
        
        # Final should be in final text
        assert buffer.get_final_text() == "Hello world"
        assert buffer.has_final_transcripts()
        
        # Current partial should be cleared
        assert buffer.get_current_partial() == ""

    def test_multiple_final_transcripts(self):
        """Test concatenation of multiple final transcripts."""
        buffer = TranscriptBuffer()
        buffer.add_final("Hello", 0.95)
        buffer.add_final("world", 0.90)
        buffer.add_final("today", 0.88)
        
        assert buffer.get_final_text() == "Hello world today"

    def test_partial_cleared_on_final(self):
        """Test that partial is cleared when final arrives."""
        buffer = TranscriptBuffer()
        buffer.add_partial("Hello wor", 0.85)
        assert buffer.get_current_partial() == "Hello wor"
        
        buffer.add_final("Hello world", 0.92)
        assert buffer.get_current_partial() == ""

    def test_buffer_locking(self):
        """Test buffer lock prevents new transcripts."""
        buffer = TranscriptBuffer()
        buffer.add_final("First", 0.90)
        
        buffer.lock()
        assert buffer.is_locked()
        
        # These should be ignored
        buffer.add_partial("Should be ignored", 0.85)
        buffer.add_final("Also ignored", 0.88)
        
        assert buffer.get_final_text() == "First"
        assert buffer.get_current_partial() == ""

    def test_buffer_unlocking(self):
        """Test unlocking allows transcripts again."""
        buffer = TranscriptBuffer()
        buffer.lock()
        buffer.add_final("Ignored", 0.90)
        
        buffer.unlock()
        assert not buffer.is_locked()
        
        buffer.add_final("Accepted", 0.92)
        assert buffer.get_final_text() == "Accepted"

    def test_average_confidence(self):
        """Test confidence score averaging."""
        buffer = TranscriptBuffer()
        
        # No transcripts
        assert buffer.get_avg_confidence() == 0.0
        
        # Add finals with different confidences
        buffer.add_final("First", 1.0)
        buffer.add_final("Second", 0.8)
        buffer.add_final("Third", 0.9)
        
        expected_avg = (1.0 + 0.8 + 0.9) / 3
        assert abs(buffer.get_avg_confidence() - expected_avg) < 0.01

    def test_clear_buffer(self):
        """Test clearing resets all state."""
        buffer = TranscriptBuffer()
        buffer.add_partial("Partial", 0.85)
        buffer.add_final("Final", 0.90)
        buffer.lock()
        
        buffer.clear()
        
        assert buffer.get_final_text() == ""
        assert buffer.get_current_partial() == ""
        assert not buffer.is_locked()
        assert not buffer.has_final_transcripts()

    def test_transcript_counts(self):
        """Test counting partial and final transcripts."""
        buffer = TranscriptBuffer()
        buffer.add_partial("P1", 0.85)
        buffer.add_partial("P2", 0.87)
        buffer.add_final("F1", 0.92)
        
        counts = buffer.get_transcript_count()
        assert counts["partial"] == 2
        assert counts["final"] == 1

    def test_partial_overwrite(self):
        """Test that new partials overwrite previous ones."""
        buffer = TranscriptBuffer()
        buffer.add_partial("Hello", 0.85)
        buffer.add_partial("Hello wo", 0.87)
        buffer.add_partial("Hello world", 0.90)
        
        # Only the latest partial is retrievable
        assert buffer.get_current_partial() == "Hello world"
        
        # Still no finals
        assert buffer.get_final_text() == ""
