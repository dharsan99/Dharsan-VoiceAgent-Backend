"""
V3 Services Module
Contains service classes for V3 voice agent, reusing V2 services with WebRTC support.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from fastapi import WebSocket

from core.base import ConnectionStatus, ProcessingStatus, SessionInfo, logger
from ..v2.services import VoiceService, AIService, STTService
from ..v2.config import VoiceConfig, AIConfig, STTConfig

class SessionManager:
    """Manages voice agent sessions for V3"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.voice_service = VoiceService()
        self.ai_service = AIService()
        self.stt_service = STTService()
    
    def create_session(self, session_id: str) -> SessionInfo:
        """Create a new session"""
        session = SessionInfo(
            session_id=session_id,
            start_time=datetime.utcnow(),
            connection_status=ConnectionStatus.CONNECTING,
            processing_status=ProcessingStatus.IDLE
        )
        self.sessions[session_id] = session
        logger.info(f"Created V3 session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session by ID"""
        return self.sessions.get(session_id)
    
    def update_session_status(self, session_id: str, connection_status: ConnectionStatus = None, 
                            processing_status: ProcessingStatus = None):
        """Update session status"""
        session = self.get_session(session_id)
        if session:
            if connection_status:
                session.connection_status = connection_status
            if processing_status:
                session.processing_status = processing_status
    
    def close_session(self, session_id: str):
        """Close a session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.connection_status = ConnectionStatus.DISCONNECTED
            session.total_duration = (datetime.utcnow() - session.start_time).total_seconds()
            logger.info(f"Closed V3 session: {session_id}")
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        return len([s for s in self.sessions.values() 
                   if s.connection_status == ConnectionStatus.CONNECTED])
    
    def get_all_sessions(self) -> List[SessionInfo]:
        """Get all sessions"""
        return list(self.sessions.values()) 