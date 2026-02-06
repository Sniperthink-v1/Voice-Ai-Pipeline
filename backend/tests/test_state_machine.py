"""
Unit tests for StateMachine.
Tests all valid transitions, invalid transitions, hooks, and edge cases.
"""

import pytest
from app.state_machine import StateMachine, TurnState


class TestStateMachineInitialization:
    """Test state machine initialization."""
    
    def test_default_initialization(self):
        """Test state machine starts in IDLE by default."""
        sm = StateMachine()
        assert sm.current_state == TurnState.IDLE
        assert sm.previous_state is None
        assert len(sm.state_history) == 1
    
    def test_custom_initialization(self):
        """Test state machine can start in custom state."""
        sm = StateMachine(initial_state=TurnState.LISTENING)
        assert sm.current_state == TurnState.LISTENING
        assert sm.previous_state is None


class TestValidTransitions:
    """Test all valid state transitions."""
    
    @pytest.mark.asyncio
    async def test_idle_to_listening(self):
        """Test IDLE → LISTENING (user starts speaking)."""
        sm = StateMachine(TurnState.IDLE)
        assert sm.can_transition(TurnState.LISTENING)
        success = await sm.transition(TurnState.LISTENING, reason="audio_received")
        assert success
        assert sm.current_state == TurnState.LISTENING
        assert sm.previous_state == TurnState.IDLE
    
    @pytest.mark.asyncio
    async def test_listening_to_speculative(self):
        """Test LISTENING → SPECULATIVE (silence detected)."""
        sm = StateMachine(TurnState.LISTENING)
        assert sm.can_transition(TurnState.SPECULATIVE)
        success = await sm.transition(TurnState.SPECULATIVE, reason="silence_detected")
        assert success
        assert sm.current_state == TurnState.SPECULATIVE
        assert sm.previous_state == TurnState.LISTENING
    
    @pytest.mark.asyncio
    async def test_listening_to_idle(self):
        """Test LISTENING → IDLE (reset/cancel)."""
        sm = StateMachine(TurnState.LISTENING)
        assert sm.can_transition(TurnState.IDLE)
        success = await sm.transition(TurnState.IDLE, reason="cancel")
        assert success
        assert sm.current_state == TurnState.IDLE
    
    @pytest.mark.asyncio
    async def test_speculative_to_committed(self):
        """Test SPECULATIVE → COMMITTED (silence window complete)."""
        sm = StateMachine(TurnState.SPECULATIVE)
        assert sm.can_transition(TurnState.COMMITTED)
        success = await sm.transition(TurnState.COMMITTED, reason="silence_confirmed")
        assert success
        assert sm.current_state == TurnState.COMMITTED
        assert sm.previous_state == TurnState.SPECULATIVE
    
    @pytest.mark.asyncio
    async def test_speculative_to_listening(self):
        """Test SPECULATIVE → LISTENING (user spoke again, cancel speculation)."""
        sm = StateMachine(TurnState.SPECULATIVE)
        assert sm.can_transition(TurnState.LISTENING)
        success = await sm.transition(TurnState.LISTENING, reason="new_audio")
        assert success
        assert sm.current_state == TurnState.LISTENING
    
    @pytest.mark.asyncio
    async def test_speculative_to_idle(self):
        """Test SPECULATIVE → IDLE (reset)."""
        sm = StateMachine(TurnState.SPECULATIVE)
        assert sm.can_transition(TurnState.IDLE)
        success = await sm.transition(TurnState.IDLE, reason="reset")
        assert success
        assert sm.current_state == TurnState.IDLE
    
    @pytest.mark.asyncio
    async def test_committed_to_speaking(self):
        """Test COMMITTED → SPEAKING (start TTS playback)."""
        sm = StateMachine(TurnState.COMMITTED)
        assert sm.can_transition(TurnState.SPEAKING)
        success = await sm.transition(TurnState.SPEAKING, reason="tts_started")
        assert success
        assert sm.current_state == TurnState.SPEAKING
        assert sm.previous_state == TurnState.COMMITTED
    
    @pytest.mark.asyncio
    async def test_committed_to_idle(self):
        """Test COMMITTED → IDLE (error/cancel)."""
        sm = StateMachine(TurnState.COMMITTED)
        assert sm.can_transition(TurnState.IDLE)
        success = await sm.transition(TurnState.IDLE, reason="error")
        assert success
        assert sm.current_state == TurnState.IDLE
    
    @pytest.mark.asyncio
    async def test_speaking_to_idle(self):
        """Test SPEAKING → IDLE (TTS complete)."""
        sm = StateMachine(TurnState.SPEAKING)
        assert sm.can_transition(TurnState.IDLE)
        success = await sm.transition(TurnState.IDLE, reason="tts_complete")
        assert success
        assert sm.current_state == TurnState.IDLE
        assert sm.previous_state == TurnState.SPEAKING
    
    @pytest.mark.asyncio
    async def test_speaking_to_listening(self):
        """Test SPEAKING → LISTENING (user interrupts, barge-in)."""
        sm = StateMachine(TurnState.SPEAKING)
        assert sm.can_transition(TurnState.LISTENING)
        success = await sm.transition(TurnState.LISTENING, reason="barge_in")
        assert success
        assert sm.current_state == TurnState.LISTENING


class TestInvalidTransitions:
    """Test that invalid state transitions are rejected."""
    
    @pytest.mark.asyncio
    async def test_idle_to_speculative_invalid(self):
        """Test IDLE cannot go directly to SPECULATIVE."""
        sm = StateMachine(TurnState.IDLE)
        assert not sm.can_transition(TurnState.SPECULATIVE)
        success = await sm.transition(TurnState.SPECULATIVE)
        assert not success
        assert sm.current_state == TurnState.IDLE  # Should stay in IDLE
    
    @pytest.mark.asyncio
    async def test_idle_to_committed_invalid(self):
        """Test IDLE cannot go directly to COMMITTED."""
        sm = StateMachine(TurnState.IDLE)
        assert not sm.can_transition(TurnState.COMMITTED)
        success = await sm.transition(TurnState.COMMITTED)
        assert not success
        assert sm.current_state == TurnState.IDLE
    
    @pytest.mark.asyncio
    async def test_idle_to_speaking_invalid(self):
        """Test IDLE cannot go directly to SPEAKING."""
        sm = StateMachine(TurnState.IDLE)
        assert not sm.can_transition(TurnState.SPEAKING)
        success = await sm.transition(TurnState.SPEAKING)
        assert not success
        assert sm.current_state == TurnState.IDLE
    
    @pytest.mark.asyncio
    async def test_listening_to_committed_invalid(self):
        """Test LISTENING cannot skip SPECULATIVE and go to COMMITTED."""
        sm = StateMachine(TurnState.LISTENING)
        assert not sm.can_transition(TurnState.COMMITTED)
        success = await sm.transition(TurnState.COMMITTED)
        assert not success
        assert sm.current_state == TurnState.LISTENING
    
    @pytest.mark.asyncio
    async def test_listening_to_speaking_invalid(self):
        """Test LISTENING cannot go directly to SPEAKING."""
        sm = StateMachine(TurnState.LISTENING)
        assert not sm.can_transition(TurnState.SPEAKING)
        success = await sm.transition(TurnState.SPEAKING)
        assert not success
        assert sm.current_state == TurnState.LISTENING
    
    @pytest.mark.asyncio
    async def test_speculative_to_speaking_invalid(self):
        """Test SPECULATIVE cannot skip COMMITTED and go to SPEAKING."""
        sm = StateMachine(TurnState.SPECULATIVE)
        assert not sm.can_transition(TurnState.SPEAKING)
        success = await sm.transition(TurnState.SPEAKING)
        assert not success
        assert sm.current_state == TurnState.SPECULATIVE
    
    @pytest.mark.asyncio
    async def test_committed_to_listening_invalid(self):
        """Test COMMITTED cannot go back to LISTENING."""
        sm = StateMachine(TurnState.COMMITTED)
        assert not sm.can_transition(TurnState.LISTENING)
        success = await sm.transition(TurnState.LISTENING)
        assert not success
        assert sm.current_state == TurnState.COMMITTED
    
    @pytest.mark.asyncio
    async def test_speaking_to_speculative_invalid(self):
        """Test SPEAKING cannot go to SPECULATIVE."""
        sm = StateMachine(TurnState.SPEAKING)
        assert not sm.can_transition(TurnState.SPECULATIVE)
        success = await sm.transition(TurnState.SPECULATIVE)
        assert not success
        assert sm.current_state == TurnState.SPEAKING
    
    @pytest.mark.asyncio
    async def test_speaking_to_committed_invalid(self):
        """Test SPEAKING cannot go back to COMMITTED."""
        sm = StateMachine(TurnState.SPEAKING)
        assert not sm.can_transition(TurnState.COMMITTED)
        success = await sm.transition(TurnState.COMMITTED)
        assert not success
        assert sm.current_state == TurnState.SPEAKING


class TestCompleteFlow:
    """Test complete turn flow sequences."""
    
    @pytest.mark.asyncio
    async def test_happy_path_flow(self):
        """Test complete happy path: IDLE → LISTENING → SPECULATIVE → COMMITTED → SPEAKING → IDLE."""
        sm = StateMachine(TurnState.IDLE)
        
        # User starts speaking
        await sm.transition(TurnState.LISTENING, reason="user_audio")
        assert sm.current_state == TurnState.LISTENING
        
        # Silence detected
        await sm.transition(TurnState.SPECULATIVE, reason="silence")
        assert sm.current_state == TurnState.SPECULATIVE
        
        # Silence confirmed
        await sm.transition(TurnState.COMMITTED, reason="silence_confirmed")
        assert sm.current_state == TurnState.COMMITTED
        
        # TTS starts
        await sm.transition(TurnState.SPEAKING, reason="tts_start")
        assert sm.current_state == TurnState.SPEAKING
        
        # TTS completes
        await sm.transition(TurnState.IDLE, reason="tts_complete")
        assert sm.current_state == TurnState.IDLE
        
        # Should have 6 state history entries (init + 5 transitions)
        assert len(sm.state_history) == 6
    
    @pytest.mark.asyncio
    async def test_speculative_cancellation_flow(self):
        """Test speculative cancellation: LISTENING → SPECULATIVE → LISTENING (user spoke again)."""
        sm = StateMachine(TurnState.IDLE)
        
        await sm.transition(TurnState.LISTENING, reason="user_audio")
        await sm.transition(TurnState.SPECULATIVE, reason="silence")
        
        # User speaks again - cancel speculation
        await sm.transition(TurnState.LISTENING, reason="new_audio")
        assert sm.current_state == TurnState.LISTENING
        assert sm.previous_state == TurnState.SPECULATIVE
    
    @pytest.mark.asyncio
    async def test_barge_in_flow(self):
        """Test barge-in: SPEAKING → LISTENING (user interrupts)."""
        sm = StateMachine(TurnState.SPEAKING)
        
        # User interrupts during agent speech
        await sm.transition(TurnState.LISTENING, reason="barge_in")
        assert sm.current_state == TurnState.LISTENING
        assert sm.previous_state == TurnState.SPEAKING
    
    @pytest.mark.asyncio
    async def test_reset_from_any_state(self):
        """Test reset to IDLE from various states."""
        # From LISTENING
        sm = StateMachine(TurnState.LISTENING)
        await sm.reset()
        assert sm.current_state == TurnState.IDLE
        
        # From SPECULATIVE
        sm = StateMachine(TurnState.SPECULATIVE)
        await sm.reset()
        assert sm.current_state == TurnState.IDLE
        
        # From COMMITTED
        sm = StateMachine(TurnState.COMMITTED)
        await sm.reset()
        assert sm.current_state == TurnState.IDLE


class TestStateHooks:
    """Test state lifecycle hooks."""
    
    @pytest.mark.asyncio
    async def test_on_enter_hook(self):
        """Test on_enter hooks are called."""
        sm = StateMachine(TurnState.IDLE)
        hook_called = []
        
        async def enter_listening_hook():
            hook_called.append("entered_listening")
        
        sm.register_on_enter(TurnState.LISTENING, enter_listening_hook)
        await sm.transition(TurnState.LISTENING)
        
        assert "entered_listening" in hook_called
    
    @pytest.mark.asyncio
    async def test_on_exit_hook(self):
        """Test on_exit hooks are called."""
        sm = StateMachine(TurnState.LISTENING)
        hook_called = []
        
        async def exit_listening_hook():
            hook_called.append("exited_listening")
        
        sm.register_on_exit(TurnState.LISTENING, exit_listening_hook)
        await sm.transition(TurnState.SPECULATIVE)
        
        assert "exited_listening" in hook_called
    
    @pytest.mark.asyncio
    async def test_on_transition_hook(self):
        """Test on_transition hooks are called."""
        sm = StateMachine(TurnState.IDLE)
        transitions = []
        
        async def transition_hook(from_state, to_state):
            transitions.append((from_state, to_state))
        
        sm.register_on_transition(transition_hook)
        await sm.transition(TurnState.LISTENING)
        
        assert (TurnState.IDLE, TurnState.LISTENING) in transitions
    
    @pytest.mark.asyncio
    async def test_multiple_hooks(self):
        """Test multiple hooks can be registered and all are called."""
        sm = StateMachine(TurnState.IDLE)
        hook_calls = []
        
        async def hook1():
            hook_calls.append("hook1")
        
        async def hook2():
            hook_calls.append("hook2")
        
        sm.register_on_enter(TurnState.LISTENING, hook1)
        sm.register_on_enter(TurnState.LISTENING, hook2)
        await sm.transition(TurnState.LISTENING)
        
        assert "hook1" in hook_calls
        assert "hook2" in hook_calls
    
    @pytest.mark.asyncio
    async def test_hook_error_handling(self):
        """Test that hook errors don't break state machine."""
        sm = StateMachine(TurnState.IDLE)
        
        async def broken_hook():
            raise ValueError("Hook error")
        
        sm.register_on_enter(TurnState.LISTENING, broken_hook)
        
        # Should still transition successfully despite hook error
        success = await sm.transition(TurnState.LISTENING)
        assert success
        assert sm.current_state == TurnState.LISTENING


class TestStateHistory:
    """Test state history tracking."""
    
    @pytest.mark.asyncio
    async def test_state_history_records_transitions(self):
        """Test state history records all transitions."""
        sm = StateMachine(TurnState.IDLE)
        
        await sm.transition(TurnState.LISTENING, reason="test1")
        await sm.transition(TurnState.SPECULATIVE, reason="test2")
        
        history = sm.state_history
        assert len(history) == 3  # Init + 2 transitions
        
        # Check last transition
        assert history[-1]["from_state"] == TurnState.LISTENING.value
        assert history[-1]["to_state"] == TurnState.SPECULATIVE.value
        assert history[-1]["reason"] == "test2"
        assert "timestamp" in history[-1]
    
    @pytest.mark.asyncio
    async def test_state_history_includes_reasons(self):
        """Test state history includes transition reasons."""
        sm = StateMachine(TurnState.IDLE)
        
        await sm.transition(TurnState.LISTENING, reason="user_started_speaking")
        
        history = sm.state_history
        assert history[-1]["reason"] == "user_started_speaking"


class TestUtilityMethods:
    """Test utility methods."""
    
    def test_get_allowed_transitions(self):
        """Test get_allowed_transitions returns correct states."""
        sm = StateMachine(TurnState.IDLE)
        allowed = sm.get_allowed_transitions()
        
        assert TurnState.LISTENING in allowed
        assert TurnState.SPECULATIVE not in allowed
        assert TurnState.COMMITTED not in allowed
        assert TurnState.SPEAKING not in allowed
    
    def test_repr(self):
        """Test string representation."""
        sm = StateMachine(TurnState.LISTENING)
        repr_str = repr(sm)
        
        assert "StateMachine" in repr_str
        assert "LISTENING" in repr_str
