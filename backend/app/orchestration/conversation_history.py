"""
Conversation history buffer for maintaining turn-based context.

Stores all prior user/assistant turns and exposes them as chat messages.
"""

from typing import List, Dict


class ConversationHistory:
    """
    Tracks the full turn-based conversation history.

    This buffer is unbounded to preserve all turns, as requested.
    """

    def __init__(self) -> None:
        self._messages: List[Dict[str, str]] = []

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        """
        Add a completed turn to history.

        Args:
            user_text: User's final transcript text
            assistant_text: Assistant's response text
        """
        if user_text:
            self._messages.append({"role": "user", "content": user_text})
        if assistant_text:
            self._messages.append({"role": "assistant", "content": assistant_text})

    def get_messages(self) -> List[Dict[str, str]]:
        """
        Get the full message history.

        Returns:
            List of chat messages with roles and content
        """
        return list(self._messages)

    def clear(self) -> None:
        """Clear the conversation history."""
        self._messages.clear()