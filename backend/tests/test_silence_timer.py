"""
Unit tests for SilenceTimer.

Tests adaptive debounce adjustment and cancellation behavior.
"""

import pytest
import asyncio
from app.orchestration.silence_timer import SilenceTimer


class TestSilenceTimer:
    """Test silence timer functionality."""

    @pytest.mark.asyncio
    async def test_timer_completion(self):
        """Test timer fires callback after debounce period."""
        completed = False
        
        def on_complete():
            nonlocal completed
            completed = True
        
        timer = SilenceTimer(on_complete, initial_debounce_ms=50)
        timer.start()
        
        assert timer.is_running()
        await asyncio.sleep(0.1)  # Wait for timer to complete
        
        assert completed
        assert not timer.is_running()

    @pytest.mark.asyncio
    async def test_timer_cancellation(self):
        """Test timer can be cancelled before completion."""
        completed = False
        
        def on_complete():
            nonlocal completed
            completed = True
        
        timer = SilenceTimer(on_complete, initial_debounce_ms=100)
        timer.start()
        
        await asyncio.sleep(0.03)  # Wait a bit
        timer.cancel()
        
        await asyncio.sleep(0.1)  # Wait past completion time
        
        assert not completed  # Should not have fired
        assert not timer.is_running()

    @pytest.mark.asyncio
    async def test_timer_restart(self):
        """Test starting timer again restarts the countdown."""
        completed = []
        
        def on_complete():
            completed.append(True)
        
        timer = SilenceTimer(on_complete, initial_debounce_ms=100)
        timer.start()
        assert timer.is_running()
        
        await asyncio.sleep(0.05)  # Wait halfway
        timer.start()  # Restart - should cancel previous and start fresh
        assert timer.is_running()
        
        await asyncio.sleep(0.15)  # Wait for new timer to complete
        
        # Should have completed exactly once (the restarted timer)
        assert len(completed) == 1
        assert not timer.is_running()

    def test_initial_debounce(self):
        """Test timer initializes with correct debounce."""
        timer = SilenceTimer(lambda: None, initial_debounce_ms=500)
        assert timer.get_current_debounce_ms() == 500

    def test_manual_debounce_adjustment(self):
        """Test manually setting debounce duration."""
        timer = SilenceTimer(
            lambda: None,
            initial_debounce_ms=400,
            min_debounce_ms=300,
            max_debounce_ms=1000
        )
        
        timer.set_debounce_ms(600)
        assert timer.get_current_debounce_ms() == 600
        
        # Test clamping to max
        timer.set_debounce_ms(1500)
        assert timer.get_current_debounce_ms() == 1000
        
        # Test clamping to min
        timer.set_debounce_ms(100)
        assert timer.get_current_debounce_ms() == 300

    def test_adaptive_increase_on_high_cancellation(self):
        """Test debounce increases when cancellation rate is high."""
        timer = SilenceTimer(
            lambda: None,
            initial_debounce_ms=400,
            max_debounce_ms=1000
        )
        
        initial = timer.get_current_debounce_ms()
        timer.adjust_debounce(cancellation_rate=0.35, threshold=0.30)
        
        # Should increase by 50ms
        assert timer.get_current_debounce_ms() == initial + 50

    def test_adaptive_decrease_on_low_cancellation(self):
        """Test debounce decreases when cancellation rate is low."""
        timer = SilenceTimer(
            lambda: None,
            initial_debounce_ms=500,
            min_debounce_ms=300
        )
        
        initial = timer.get_current_debounce_ms()
        timer.adjust_debounce(cancellation_rate=0.10)
        
        # Should decrease by 25ms
        assert timer.get_current_debounce_ms() == initial - 25

    def test_adaptive_no_change_in_acceptable_range(self):
        """Test debounce unchanged when cancellation rate is acceptable."""
        timer = SilenceTimer(lambda: None, initial_debounce_ms=500)
        
        initial = timer.get_current_debounce_ms()
        timer.adjust_debounce(cancellation_rate=0.20, threshold=0.30)
        
        # Should stay the same
        assert timer.get_current_debounce_ms() == initial

    def test_adaptive_respects_max_limit(self):
        """Test debounce won't exceed max when increasing."""
        timer = SilenceTimer(
            lambda: None,
            initial_debounce_ms=980,
            max_debounce_ms=1000
        )
        
        timer.adjust_debounce(cancellation_rate=0.40, threshold=0.30)
        
        # Should clamp to max (1000)
        assert timer.get_current_debounce_ms() == 1000

    def test_adaptive_respects_min_limit(self):
        """Test debounce won't go below min when decreasing."""
        timer = SilenceTimer(
            lambda: None,
            initial_debounce_ms=320,
            min_debounce_ms=300
        )
        
        timer.adjust_debounce(cancellation_rate=0.10)
        
        # Should clamp to min (300)
        assert timer.get_current_debounce_ms() == 300

    @pytest.mark.asyncio
    async def test_multiple_adjustments(self):
        """Test multiple adaptive adjustments work correctly."""
        timer = SilenceTimer(
            lambda: None,
            initial_debounce_ms=500,
            min_debounce_ms=400,
            max_debounce_ms=800
        )
        
        # High cancellation -> increase
        timer.adjust_debounce(0.35, threshold=0.30)
        assert timer.get_current_debounce_ms() == 550
        
        # Still high -> increase again
        timer.adjust_debounce(0.32, threshold=0.30)
        assert timer.get_current_debounce_ms() == 600
        
        # Now low -> decrease
        timer.adjust_debounce(0.12)
        assert timer.get_current_debounce_ms() == 575
