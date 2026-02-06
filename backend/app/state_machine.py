"""
State Machine for Voice Agent Turn Control.
Implements deterministic state transitions with validation and hooks.

States: IDLE → LISTENING → SPECULATIVE → COMMITTED → SPEAKING → IDLE
"""

import logging
from enum import Enum
from typing import Optional, Callable, Awaitable, Dict, Set
import time

logger = logging.getLogger(__name__)


class TurnState(str, Enum):
    """
    Voice agent turn states.
    
    State flow:
    IDLE: No activity, waiting for user input
    LISTENING: Receiving user audio, transcribing
    SPECULATIVE: Silence detected, LLM may start (output hidden)
    COMMITTED: User intent confirmed, LLM output can surface
    SPEAKING: Agent is speaking (interruptible)
    """
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    SPECULATIVE = "SPECULATIVE"
    COMMITTED = "COMMITTED"
    SPEAKING = "SPEAKING"


class StateMachine:
    """
    Deterministic state machine for voice agent turn control.
    
    Enforces valid state transitions and provides hooks for state changes.
    Critical for ensuring "never speak incorrect intent out loud" guarantee.
    """
    
    # Define all valid state transitions
    ALLOWED_TRANSITIONS: Dict[TurnState, Set[TurnState]] = {
        TurnState.IDLE: {
            TurnState.LISTENING,  # User starts speaking
        },
        TurnState.LISTENING: {
            TurnState.SPECULATIVE,  # Silence detected, start debounce
            TurnState.IDLE,  # Reset/cancel
        },
        TurnState.SPECULATIVE: {
            TurnState.COMMITTED,  # Silence window complete, commit intent
            TurnState.LISTENING,  # User spoke again, cancel speculation
            TurnState.IDLE,  # Reset/cancel
        },
        TurnState.COMMITTED: {
            TurnState.SPEAKING,  # Start TTS playback
            TurnState.IDLE,  # Error/cancel
        },
        TurnState.SPEAKING: {
            TurnState.IDLE,  # TTS complete
            TurnState.LISTENING,  # User interrupts (barge-in)
        },
    }
    
    def __init__(self, initial_state: TurnState = TurnState.IDLE):
        """
        Initialize state machine.
        
        Args:
            initial_state: Starting state (default: IDLE)
        """
        self._current_state: TurnState = initial_state
        self._previous_state: Optional[TurnState] = None
        self._state_history: list[dict] = []
        
        # Hooks for state lifecycle events
        self._on_enter_hooks: Dict[TurnState, list[Callable]] = {
            state: [] for state in TurnState
        }
        self._on_exit_hooks: Dict[TurnState, list[Callable]] = {
            state: [] for state in TurnState
        }
        self._on_transition_hooks: list[Callable] = []
        
        logger.info(f"State machine initialized in state: {initial_state}")
        self._record_state_change(None, initial_state, "initialization")
    
    @property
    def current_state(self) -> TurnState:
        """Get current state."""
        return self._current_state
    
    @property
    def previous_state(self) -> Optional[TurnState]:
        """Get previous state."""
        return self._previous_state
    
    @property
    def state_history(self) -> list[dict]:
        """Get state history for debugging/telemetry."""
        return self._state_history.copy()
    
    def can_transition(self, to_state: TurnState) -> bool:
        """
        Check if transition to target state is allowed.
        
        Args:
            to_state: Target state
            
        Returns:
            True if transition is allowed, False otherwise
        """
        allowed = to_state in self.ALLOWED_TRANSITIONS.get(self._current_state, set())
        
        if not allowed:
            logger.warning(
                f"Invalid transition attempted: {self._current_state} → {to_state}"
            )
        
        return allowed
    
    async def transition(self, to_state: TurnState, reason: str = "") -> bool:
        """
        Transition to new state with validation and hooks.
        
        Args:
            to_state: Target state
            reason: Optional reason for transition (for logging)
            
        Returns:
            True if transition succeeded, False if not allowed
            
        Raises:
            ValueError: If transition is not allowed (only in strict mode)
        """
        if not self.can_transition(to_state):
            error_msg = (
                f"Invalid state transition: {self._current_state} → {to_state}. "
                f"Allowed transitions: {self.ALLOWED_TRANSITIONS.get(self._current_state, set())}"
            )
            logger.error(error_msg)
            return False
        
        from_state = self._current_state
        
        # Execute exit hooks for current state
        await self._execute_exit_hooks(from_state)
        
        # Update state
        self._previous_state = self._current_state
        self._current_state = to_state
        
        # Record transition
        self._record_state_change(from_state, to_state, reason)
        
        # Log transition
        log_msg = f"State transition: {from_state} → {to_state}"
        if reason:
            log_msg += f" (reason: {reason})"
        logger.info(log_msg)
        
        # Execute enter hooks for new state
        await self._execute_enter_hooks(to_state)
        
        # Execute transition hooks
        await self._execute_transition_hooks(from_state, to_state)
        
        return True
    
    def register_on_enter(
        self, 
        state: TurnState, 
        callback: Callable[[], Awaitable[None]]
    ) -> None:
        """
        Register callback to execute when entering a state.
        
        Args:
            state: State to hook into
            callback: Async callback function
        """
        self._on_enter_hooks[state].append(callback)
        logger.debug(f"Registered on_enter hook for state: {state}")
    
    def register_on_exit(
        self, 
        state: TurnState, 
        callback: Callable[[], Awaitable[None]]
    ) -> None:
        """
        Register callback to execute when exiting a state.
        
        Args:
            state: State to hook into
            callback: Async callback function
        """
        self._on_exit_hooks[state].append(callback)
        logger.debug(f"Registered on_exit hook for state: {state}")
    
    def register_on_transition(
        self, 
        callback: Callable[[TurnState, TurnState], Awaitable[None]]
    ) -> None:
        """
        Register callback to execute on any state transition.
        
        Args:
            callback: Async callback function receiving (from_state, to_state)
        """
        self._on_transition_hooks.append(callback)
        logger.debug("Registered on_transition hook")
    
    async def reset(self) -> None:
        """Reset state machine to IDLE."""
        logger.info("Resetting state machine to IDLE")
        await self.transition(TurnState.IDLE, reason="reset")
    
    def _record_state_change(
        self, 
        from_state: Optional[TurnState], 
        to_state: TurnState,
        reason: str
    ) -> None:
        """Record state change in history."""
        record = {
            "from_state": from_state.value if from_state else None,
            "to_state": to_state.value,
            "reason": reason,
            "timestamp": int(time.time() * 1000),  # Unix timestamp in milliseconds
        }
        self._state_history.append(record)
    
    async def _execute_enter_hooks(self, state: TurnState) -> None:
        """Execute all on_enter hooks for a state."""
        for callback in self._on_enter_hooks[state]:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in on_enter hook for {state}: {e}", exc_info=True)
    
    async def _execute_exit_hooks(self, state: TurnState) -> None:
        """Execute all on_exit hooks for a state."""
        for callback in self._on_exit_hooks[state]:
            try:
                await callback()
            except Exception as e:
                logger.error(f"Error in on_exit hook for {state}: {e}", exc_info=True)
    
    async def _execute_transition_hooks(
        self, 
        from_state: TurnState, 
        to_state: TurnState
    ) -> None:
        """Execute all on_transition hooks."""
        for callback in self._on_transition_hooks:
            try:
                await callback(from_state, to_state)
            except Exception as e:
                logger.error(f"Error in on_transition hook: {e}", exc_info=True)
    
    def get_allowed_transitions(self) -> Set[TurnState]:
        """Get all allowed transitions from current state."""
        return self.ALLOWED_TRANSITIONS.get(self._current_state, set()).copy()
    
    def __repr__(self) -> str:
        """String representation of state machine."""
        return (
            f"StateMachine(current={self._current_state}, "
            f"previous={self._previous_state})"
        )
