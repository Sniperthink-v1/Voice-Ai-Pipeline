"""
Silence detection timer with adaptive debounce.

Triggers transition from LISTENING -> SPECULATIVE after configured silence period.
Adjusts debounce duration based on cancellation rate to optimize for accuracy.
"""

import asyncio
import logging
from typing import Callable, Optional, Awaitable

logger = logging.getLogger(__name__)


class SilenceTimer:
    """
    Manages silence detection with adaptive debounce adjustment.
    
    Key Features:
    - Configurable debounce duration (400-1200ms typical)
    - Adaptive adjustment based on cancellation rate
    - Cancellable timer for user barge-in scenarios
    - Callback on timer completion
    """

    def __init__(
        self,
        on_silence_complete: Callable[[], Awaitable[None]],
        initial_debounce_ms: int = 400,
        min_debounce_ms: int = 400,
        max_debounce_ms: int = 1200,
    ):
        """
        Initialize silence timer.

        Args:
            on_silence_complete: Callback to invoke when silence period completes
            initial_debounce_ms: Starting debounce duration
            min_debounce_ms: Minimum allowed debounce (more aggressive)
            max_debounce_ms: Maximum allowed debounce (more conservative)
        """
        self.on_silence_complete = on_silence_complete
        self.current_debounce_ms = initial_debounce_ms
        self.min_debounce_ms = min_debounce_ms
        self.max_debounce_ms = max_debounce_ms

        self._timer_task: Optional[asyncio.Task] = None
        self._is_running = False
        self._override_ms: Optional[int] = None

    def start(self, override_ms: Optional[int] = None):
        """
        Start the silence timer.
        
        If timer is already running, this restarts it (resets the countdown).
        
        Args:
            override_ms: If provided, use this duration instead of current_debounce_ms.
                Used for speech_final events where Deepgram already confirmed silence.
        """
        # Cancel existing timer if running
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()

        self._is_running = True
        self._override_ms = override_ms
        self._timer_task = asyncio.create_task(self._run_timer())
        duration = override_ms if override_ms is not None else self.current_debounce_ms
        logger.debug(f"Silence timer started: {duration}ms{' (override)' if override_ms else ''}")

    def cancel(self):
        """
        Cancel the running timer.
        
        Used when user speaks again before silence period completes.
        """
        if not self._is_running:
            return

        self._is_running = False

        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            logger.debug("Silence timer cancelled")

    def is_running(self) -> bool:
        """Check if timer is currently active."""
        return self._is_running

    def adjust_debounce(self, cancellation_rate: float, threshold: float = 0.30):
        """
        Adjust debounce duration based on cancellation rate.
        
        Strategy:
        - High cancellation rate (>threshold) -> Increase debounce (more conservative)
        - Low cancellation rate (<15%) -> Decrease debounce (more aggressive)
        - Within acceptable range -> No change
        
        Args:
            cancellation_rate: Fraction of turns that were cancelled (0.0-1.0)
            threshold: Upper threshold for acceptable cancellation rate
        """
        old_debounce = self.current_debounce_ms

        if cancellation_rate > threshold:
            # Too many cancellations - increase debounce by 50ms
            self.current_debounce_ms = min(
                self.current_debounce_ms + 50,
                self.max_debounce_ms
            )
            logger.info(
                f"Cancellation rate {cancellation_rate:.1%} > {threshold:.1%} - "
                f"increasing debounce: {old_debounce}ms -> {self.current_debounce_ms}ms"
            )

        elif cancellation_rate < 0.15:
            # Low cancellations - can be more aggressive, decrease by 25ms
            self.current_debounce_ms = max(
                self.current_debounce_ms - 25,
                self.min_debounce_ms
            )
            logger.info(
                f"Cancellation rate {cancellation_rate:.1%} < 15% - "
                f"decreasing debounce: {old_debounce}ms -> {self.current_debounce_ms}ms"
            )
        else:
            logger.debug(f"Cancellation rate {cancellation_rate:.1%} within acceptable range")

    def get_current_debounce_ms(self) -> int:
        """Get current debounce duration in milliseconds."""
        return self.current_debounce_ms

    def set_debounce_ms(self, debounce_ms: int):
        """
        Manually set debounce duration (used by settings updates).
        
        Args:
            debounce_ms: New debounce duration, will be clamped to min/max
        """
        old_value = self.current_debounce_ms
        self.current_debounce_ms = max(
            self.min_debounce_ms,
            min(debounce_ms, self.max_debounce_ms)
        )
        logger.info(f"Debounce manually set: {old_value}ms -> {self.current_debounce_ms}ms")

    async def _run_timer(self):
        """
        Internal timer coroutine.
        
        Waits for debounce period, then invokes callback if not cancelled.
        """
        try:
            duration_ms = self._override_ms if self._override_ms is not None else self.current_debounce_ms
            await asyncio.sleep(duration_ms / 1000.0)
            
            # Timer completed without cancellation
            # Check if still running (not cancelled during sleep)
            if self._is_running:
                logger.debug("Silence period complete - triggering callback")
                self._is_running = False
                await self.on_silence_complete()

        except asyncio.CancelledError:
            # Timer was cancelled (user spoke again or restarted)
            logger.debug("Timer task cancelled")
            # Don't set _is_running to False here - let the caller manage it

    def __repr__(self) -> str:
        status = "running" if self._is_running else "idle"
        return f"SilenceTimer(debounce={self.current_debounce_ms}ms, status={status})"
