"""
WebSocket connection manager and message routing.
Handles WebSocket lifecycle, session management, and message distribution.
"""

import logging
import uuid
import time
from typing import Dict, Optional
from fastapi import WebSocket, WebSocketDisconnect

from app.models import (
    SessionReadyMessage, SessionReadyData,
    StateChangeMessage, StateChangeData,
    ErrorMessage, ErrorData,
    PingMessage,
)
from app.state_machine import TurnState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections and message routing.
    
    Responsibilities:
    - Track active connections (session_id → websocket)
    - Handle connection lifecycle (connect, disconnect, cleanup)
    - Send messages to specific sessions or broadcast
    - Heartbeat (ping/pong) management
    - Session cleanup after disconnect
    """
    
    def __init__(self):
        """Initialize connection manager."""
        # Active connections: session_id → WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Session metadata: session_id → metadata dict
        self.session_metadata: Dict[str, dict] = {}
        
        # Last heartbeat timestamp: session_id → timestamp
        self.last_heartbeat: Dict[str, int] = {}
        
        logger.info("ConnectionManager initialized")
    
    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept new WebSocket connection and create session.
        
        Args:
            websocket: WebSocket connection
            
        Returns:
            session_id: UUID of created session
        """
        # Accept WebSocket connection
        await websocket.accept()
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Store connection
        self.active_connections[session_id] = websocket
        
        # Initialize session metadata
        self.session_metadata[session_id] = {
            "connected_at": int(time.time() * 1000),
            "client_info": websocket.client,
            "total_messages": 0,
        }
        
        # Initialize heartbeat
        self.last_heartbeat[session_id] = int(time.time() * 1000)
        
        logger.info(
            f"WebSocket connected: session_id={session_id}, "
            f"client={websocket.client}, "
            f"total_connections={len(self.active_connections)}"
        )
        
        # Send session_ready message
        await self.send_session_ready(session_id)
        
        return session_id
    
    async def disconnect(self, session_id: str):
        """
        Handle WebSocket disconnection and cleanup.
        
        Args:
            session_id: Session ID to disconnect
        """
        if session_id not in self.active_connections:
            logger.warning(f"Attempted to disconnect non-existent session: {session_id}")
            return
        
        # Remove connection
        websocket = self.active_connections.pop(session_id, None)
        
        # Cleanup metadata
        metadata = self.session_metadata.pop(session_id, {})
        self.last_heartbeat.pop(session_id, None)
        
        # Log disconnection
        if metadata:
            connected_at = metadata.get("connected_at", 0)
            disconnected_at = int(time.time() * 1000)
            session_duration = disconnected_at - connected_at
            
            logger.info(
                f"WebSocket disconnected: session_id={session_id}, "
                f"duration_ms={session_duration}, "
                f"total_messages={metadata.get('total_messages', 0)}, "
                f"remaining_connections={len(self.active_connections)}"
            )
    
    async def send_message(self, session_id: str, message: dict) -> bool:
        """
        Send JSON message to specific session.
        
        Args:
            session_id: Target session ID
            message: Message dict to send
            
        Returns:
            True if sent successfully, False otherwise
        """
        if session_id not in self.active_connections:
            logger.warning(f"Attempted to send message to non-existent session: {session_id}")
            return False
        
        websocket = self.active_connections[session_id]
        
        try:
            await websocket.send_json(message)
            
            # Update message count
            if session_id in self.session_metadata:
                self.session_metadata[session_id]["total_messages"] += 1
            
            logger.debug(f"Message sent to session {session_id}: type={message.get('type', 'unknown')}")
            return True
            
        except WebSocketDisconnect:
            logger.warning(f"WebSocket disconnected while sending to session: {session_id}")
            await self.disconnect(session_id)
            return False
        except Exception as e:
            logger.error(f"Error sending message to session {session_id}: {e}", exc_info=True)
            return False
    
    async def broadcast(self, message: dict, exclude_session: Optional[str] = None):
        """
        Broadcast message to all active connections.
        
        Args:
            message: Message dict to broadcast
            exclude_session: Optional session ID to exclude from broadcast
        """
        disconnected_sessions = []
        
        for session_id, websocket in self.active_connections.items():
            if exclude_session and session_id == exclude_session:
                continue
            
            try:
                await websocket.send_json(message)
                
                # Update message count
                if session_id in self.session_metadata:
                    self.session_metadata[session_id]["total_messages"] += 1
                    
            except WebSocketDisconnect:
                logger.warning(f"WebSocket disconnected during broadcast: {session_id}")
                disconnected_sessions.append(session_id)
            except Exception as e:
                logger.error(f"Error broadcasting to session {session_id}: {e}", exc_info=True)
                disconnected_sessions.append(session_id)
        
        # Cleanup disconnected sessions
        for session_id in disconnected_sessions:
            await self.disconnect(session_id)
        
        logger.debug(f"Message broadcasted to {len(self.active_connections)} sessions")
    
    async def send_session_ready(self, session_id: str):
        """
        Send session_ready message to newly connected client.
        
        Args:
            session_id: Session ID
        """
        message = SessionReadyMessage(
            data=SessionReadyData(
                session_id=session_id,
                timestamp=int(time.time() * 1000)
            )
        )
        await self.send_message(session_id, message.model_dump())
    
    async def send_state_change(
        self, 
        session_id: str, 
        from_state: TurnState, 
        to_state: TurnState
    ):
        """
        Send state_change message to client.
        
        Args:
            session_id: Session ID
            from_state: Previous state
            to_state: New state
        """
        message = StateChangeMessage(
            data=StateChangeData(
                from_state=from_state,
                to_state=to_state,
                timestamp=int(time.time() * 1000)
            )
        )
        await self.send_message(session_id, message.model_dump())
    
    async def send_error(
        self, 
        session_id: str, 
        code: str, 
        message_text: str, 
        recoverable: bool = True
    ):
        """
        Send error message to client.
        
        Args:
            session_id: Session ID
            code: Error code
            message_text: Error message
            recoverable: Whether error is recoverable
        """
        message = ErrorMessage(
            data=ErrorData(
                code=code,
                message=message_text,
                recoverable=recoverable,
                timestamp=int(time.time() * 1000)
            )
        )
        await self.send_message(session_id, message.model_dump())
    
    async def send_ping(self, session_id: str):
        """
        Send ping message for heartbeat.
        
        Args:
            session_id: Session ID
        """
        message = PingMessage()
        await self.send_message(session_id, message.model_dump())
    
    def update_heartbeat(self, session_id: str):
        """
        Update last heartbeat timestamp for session.
        
        Args:
            session_id: Session ID
        """
        if session_id in self.last_heartbeat:
            self.last_heartbeat[session_id] = int(time.time() * 1000)
    
    def get_stale_sessions(self, timeout_ms: int = 60000) -> list[str]:
        """
        Get list of sessions with no heartbeat for timeout period.
        
        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
            
        Returns:
            List of stale session IDs
        """
        current_time = int(time.time() * 1000)
        stale_sessions = []
        
        for session_id, last_heartbeat in self.last_heartbeat.items():
            if current_time - last_heartbeat > timeout_ms:
                stale_sessions.append(session_id)
        
        return stale_sessions
    
    async def cleanup_stale_sessions(self, timeout_ms: int = 60000):
        """
        Disconnect and cleanup stale sessions.
        
        Args:
            timeout_ms: Timeout in milliseconds (default: 60 seconds)
        """
        stale_sessions = self.get_stale_sessions(timeout_ms)
        
        for session_id in stale_sessions:
            logger.warning(f"Disconnecting stale session: {session_id}")
            await self.disconnect(session_id)
    
    def get_session_count(self) -> int:
        """Get count of active sessions."""
        return len(self.active_connections)
    
    def get_session_metadata(self, session_id: str) -> Optional[dict]:
        """
        Get metadata for session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session metadata dict or None if not found
        """
        return self.session_metadata.get(session_id)
    
    def session_exists(self, session_id: str) -> bool:
        """
        Check if session exists.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session exists, False otherwise
        """
        return session_id in self.active_connections


# Global connection manager instance
connection_manager = ConnectionManager()
