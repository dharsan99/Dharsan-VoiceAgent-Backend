#!/usr/bin/env python3
"""
Standalone unified backend for Modal deployment
Includes all version implementations in a single file
"""

import os
import logging
import uuid
import time
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import modal

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CORE COMPONENTS
# ============================================================================

class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorType(Enum):
    NETWORK = "network"
    API = "api"
    AUDIO = "audio"
    SYSTEM = "system"

class RecoveryAction(Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    RESTART = "restart"
    IGNORE = "ignore"

class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

class ProcessingStatus(Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"

@dataclass
class SessionInfo:
    session_id: str
    start_time: float
    status: ConnectionStatus
    version: str
    user_agent: Optional[str] = None

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.sessions: Dict[str, SessionInfo] = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        session_id = str(uuid.uuid4())
        self.active_connections[session_id] = websocket
        self.sessions[session_id] = SessionInfo(
            session_id=session_id,
            start_time=time.time(),
            status=ConnectionStatus.CONNECTED,
            version="unknown"
        )
        logger.info(f"New connection: {session_id}")
        return session_id
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        if session_id in self.sessions:
            self.sessions[session_id].status = ConnectionStatus.DISCONNECTED
        logger.info(f"Connection closed: {session_id}")
    
    async def send_message(self, session_id: str, message: str):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to {session_id}: {e}")
                self.disconnect(session_id)

class ErrorRecoveryManager:
    def __init__(self):
        self.error_counts: Dict[ErrorType, int] = {}
        self.circuit_breaker_threshold = 5
    
    def record_error(self, error_type: ErrorType):
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
    
    def should_retry(self, error_type: ErrorType) -> bool:
        return self.error_counts.get(error_type, 0) < self.circuit_breaker_threshold
    
    def get_recovery_action(self, error_type: ErrorType) -> RecoveryAction:
        count = self.error_counts.get(error_type, 0)
        if count < 3:
            return RecoveryAction.RETRY
        elif count < 5:
            return RecoveryAction.FALLBACK
        else:
            return RecoveryAction.RESTART

class AudioEnhancer:
    def __init__(self, sample_rate: int = 44100, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
    
    def enhance_audio(self, audio_data: bytes) -> bytes:
        # Simple audio enhancement - in a real implementation, this would do more
        return audio_data

def with_retry(error_manager: ErrorRecoveryManager, error_type: ErrorType, max_retries: int = 3, fallback_func=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_manager.record_error(error_type)
                    if not error_manager.should_retry(error_type):
                        logger.error(f"Circuit breaker triggered for {error_type}: {e}")
                        if fallback_func:
                            return fallback_func(*args, **kwargs)
                        raise
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for {error_type}: {e}")
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# ============================================================================
# UNIFIED APP CREATION
# ============================================================================

def create_unified_app() -> FastAPI:
    """Create the unified FastAPI app with all versions"""
    app = FastAPI(
        title="Dharsan Voice Agent Backend",
        version="3.0.0",
        description="Unified backend for voice agent versions v1, v2, and v3"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Global managers
    manager = ConnectionManager()
    error_manager = ErrorRecoveryManager()
    
    # ============================================================================
    # V1 ENDPOINTS
    # ============================================================================
    
    @app.websocket("/v1/ws")
    async def v1_websocket(websocket: WebSocket):
        """V1 WebSocket handler"""
        session_id = await manager.connect(websocket)
        logger.info(f"V1 WebSocket connected: {session_id}")
        
        try:
            while True:
                data = await websocket.receive_text()
                # Echo back for now - in full implementation, this would process audio
                await manager.send_message(session_id, f"V1 received: {data}")
        except WebSocketDisconnect:
            manager.disconnect(session_id)
    
    @app.get("/v1/health")
    async def v1_health():
        return {
            "status": "healthy",
            "version": "v1",
            "connections": len(manager.active_connections)
        }
    
    @app.get("/v1/metrics/sessions")
    async def v1_metrics():
        return {
            "total_sessions": len(manager.sessions),
            "active_sessions": len(manager.active_connections),
            "sessions": list(manager.sessions.values())
        }
    
    # ============================================================================
    # V2 ENDPOINTS
    # ============================================================================
    
    @app.websocket("/v2/ws")
    async def v2_websocket(websocket: WebSocket):
        """V2 WebSocket handler"""
        session_id = await manager.connect(websocket)
        logger.info(f"V2 WebSocket connected: {session_id}")
        
        try:
            while True:
                data = await websocket.receive_text()
                # Echo back for now - in full implementation, this would process audio
                await manager.send_message(session_id, f"V2 received: {data}")
        except WebSocketDisconnect:
            manager.disconnect(session_id)
    
    @app.get("/v2/health")
    async def v2_health():
        return {
            "status": "healthy",
            "version": "v2",
            "connections": len(manager.active_connections)
        }
    
    @app.get("/v2/sessions")
    async def v2_sessions():
        return {
            "sessions": list(manager.sessions.values())
        }
    
    # ============================================================================
    # V3 ENDPOINTS
    # ============================================================================
    
    @app.websocket("/v3/ws")
    async def v3_websocket(websocket: WebSocket):
        """V3 WebSocket handler"""
        session_id = await manager.connect(websocket)
        logger.info(f"V3 WebSocket connected: {session_id}")
        
        try:
            while True:
                data = await websocket.receive_text()
                # Echo back for now - in full implementation, this would process audio
                await manager.send_message(session_id, f"V3 received: {data}")
        except WebSocketDisconnect:
            manager.disconnect(session_id)
    
    @app.get("/v3/health")
    async def v3_health():
        return {
            "status": "healthy",
            "version": "v3",
            "connections": len(manager.active_connections)
        }
    
    @app.get("/v3/webrtc/stats")
    async def v3_webrtc_stats():
        return {
            "webrtc_enabled": True,
            "active_connections": len(manager.active_connections)
        }
    
    # ============================================================================
    # ROOT ENDPOINTS
    # ============================================================================
    
    @app.get("/")
    async def root():
        return {
            "message": "Dharsan Voice Agent Backend",
            "version": "3.0.0",
            "status": "running",
            "available_versions": {
                "v1": {
                    "description": "Basic voice agent with metrics",
                    "websocket": "/v1/ws",
                    "health": "/v1/health",
                    "metrics": "/v1/metrics/sessions"
                },
                "v2": {
                    "description": "Modular voice agent with session management",
                    "websocket": "/v2/ws",
                    "health": "/v2/health",
                    "sessions": "/v2/sessions"
                },
                "v3": {
                    "description": "WebRTC-based voice agent",
                    "websocket": "/v3/ws",
                    "health": "/v3/health",
                    "webrtc_stats": "/v3/webrtc/stats"
                }
            },
            "documentation": {
                "api_docs": "/docs",
                "redoc": "/redoc"
            }
        }
    
    @app.get("/health")
    async def health_check():
        return {
            "status": "healthy",
            "version": "3.0.0",
            "available_versions": ["v1", "v2", "v3"],
            "active_connections": len(manager.active_connections)
        }
    
    return app

# ============================================================================
# MODAL DEPLOYMENT
# ============================================================================

# Create the unified app
fastapi_app = create_unified_app()

# Modal setup
app_image = modal.Image.debian_slim().pip_install([
    "fastapi",
    "websockets",
    "deepgram-sdk",
    "groq",
    "elevenlabs",
    "python-dotenv",
    "uvicorn",
    "pydantic",
    "numpy",
    "aiortc",
    "aiohttp",
    "azure-cognitiveservices-speech"
])

app = modal.App(
    "voice-ai-backend-unified-standalone",
    image=app_image,
    secrets=[
        modal.Secret.from_name("deepgram-secret"),
        modal.Secret.from_name("groq-secret"),
        modal.Secret.from_name("elevenlabs-secret"),
        modal.Secret.from_name("azure-speech-secret")
    ]
)

@app.function()
@modal.asgi_app()
def run_app():
    """Run the unified FastAPI app with Modal"""
    return fastapi_app

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting unified voice agent backend...")
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000) 