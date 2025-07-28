"""
V2 Voice Agent Implementation
Refactored version using shared core components and modular services.
"""

import asyncio
import os
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import modal

# Import shared core components
from core.base import (
    ErrorType, ErrorSeverity, ConnectionStatus, ProcessingStatus, SessionInfo,
    with_retry, ErrorContext, logger
)

# Import V2-specific services
from .services import VoiceService, AIService, STTService, SessionManager
from .config import VoiceConfig

# ============================================================================
# MODAL SETUP
# ============================================================================

# Define the container image with necessary dependencies
app_image = modal.Image.debian_slim().pip_install([
    "fastapi",
    "websockets",
    "deepgram-sdk",
    "groq",
    "elevenlabs",
    "python-dotenv",
    "uvicorn",
    "pydantic",
    "numpy"
])

# Define the Modal application
app = modal.App(
    "voice-ai-backend-v2",
    image=app_image,
    secrets=[
        modal.Secret.from_name("deepgram-secret"),
        modal.Secret.from_name("groq-secret"),
        modal.Secret.from_name("elevenlabs-secret")
    ]
)

# Create FastAPI app
fastapi_app = FastAPI(title="Voice AI Backend V2", version="2.0.0")

# Add CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# GLOBAL MANAGERS
# ============================================================================

session_manager = SessionManager()

# ============================================================================
# WEBSOCKET HANDLER
# ============================================================================

@fastapi_app.websocket("/ws/v2")
async def websocket_handler_v2(websocket: WebSocket):
    """V2 WebSocket handler for the voice agent with modular services"""
    await websocket.accept()
    
    # Generate session ID
    session_id = f"v2_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
    session = session_manager.create_session(session_id)
    
    logger.info(f"V2 WebSocket connected: {session_id}")
    
    try:
        # Update connection status
        session_manager.update_session_status(session_id, ConnectionStatus.CONNECTED)
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "session_id": session_id,
            "version": "2.0.0",
            "features": ["voice_synthesis", "ai_processing", "real_time_transcription"]
        }))
        
        # Initialize conversation history
        conversation_history = []
        
        # Start STT transcription
        async def on_transcript(result, **kwargs):
            """Handle transcription results"""
            try:
                if hasattr(result, 'channel') and hasattr(result.channel, 'alternatives'):
                    transcript = result.channel.alternatives[0].transcript
                    if not transcript or not transcript.strip():
                        return
                    
                    if hasattr(result, 'is_final') and result.is_final:
                        logger.info(f"STT (Final): {transcript}")
                        
                        # Update session status
                        session_manager.update_session_status(session_id, processing_status=ProcessingStatus.PROCESSING)
                        
                        # Send final transcript
                        await websocket.send_text(json.dumps({
                            "type": "final_transcript",
                            "text": transcript,
                            "session_id": session_id
                        }))
                        
                        # Generate AI response
                        ai_response = await session_manager.ai_service.generate_response(transcript, conversation_history)
                        
                        # Add to conversation history
                        conversation_history.append({"role": "user", "content": transcript})
                        conversation_history.append({"role": "assistant", "content": ai_response})
                        
                        # Send processing complete
                        await websocket.send_text(json.dumps({
                            "type": "processing_complete",
                            "response": ai_response,
                            "session_id": session_id
                        }))
                        
                        # Synthesize speech
                        session_manager.update_session_status(session_id, processing_status=ProcessingStatus.SPEAKING)
                        
                        audio_data = await session_manager.voice_service.synthesize_speech(ai_response, websocket)
                        
                        if audio_data:
                            await websocket.send_bytes(audio_data)
                        
                        # Update session status
                        session_manager.update_session_status(session_id, processing_status=ProcessingStatus.IDLE)
                        session.messages_processed += 1
                        
                    else:
                        # Interim transcript
                        logger.info(f"STT (Interim): {transcript}")
                        await websocket.send_text(json.dumps({
                            "type": "interim_transcript",
                            "text": transcript,
                            "session_id": session_id
                        }))
                        
            except Exception as e:
                logger.error(f"Transcript handler error: {e}")
                session.errors_count += 1
        
        # Start transcription
        stt_connection = await session_manager.stt_service.start_transcription(websocket, on_transcript)
        
        if not stt_connection:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Failed to initialize speech recognition",
                "session_id": session_id
            }))
            return
        
        # Audio receiver
        async def audio_receiver():
            """Receive audio from client and send to STT service"""
            try:
                async for data in websocket.iter_bytes():
                    await session_manager.stt_service.send_audio(data)
            except WebSocketDisconnect:
                logger.info("Audio receiver: Client disconnected")
            except Exception as e:
                logger.error(f"Audio receiver error: {e}")
                session.errors_count += 1
        
        # Start audio receiver
        audio_task = asyncio.create_task(audio_receiver())
        
        try:
            # Keep connection alive
            while True:
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            logger.info("V2 WebSocket disconnected")
        finally:
            # Cleanup
            audio_task.cancel()
            session_manager.close_session(session_id)
            
    except Exception as e:
        logger.error(f"V2 WebSocket handler error: {e}")
        session_manager.close_session(session_id)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@fastapi_app.get("/v2/health")
async def health_check_v2():
    """V2 health check endpoint"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": session_manager.get_active_sessions_count(),
        "services": {
            "voice_service": session_manager.voice_service.get_provider_info(),
            "ai_service": "available",
            "stt_service": "available"
        }
    }

@fastapi_app.get("/v2/sessions")
async def get_sessions_v2():
    """Get active V2 sessions"""
    sessions = session_manager.get_all_sessions()
    return {
        "sessions": [
            {
                "session_id": session.session_id,
                "start_time": session.start_time.isoformat(),
                "connection_status": session.connection_status.value,
                "processing_status": session.processing_status.value,
                "messages_processed": session.messages_processed,
                "errors_count": session.errors_count
            }
            for session in sessions
        ],
        "total_sessions": len(sessions)
    }

@fastapi_app.get("/v2/config")
async def get_config_v2():
    """Get V2 configuration"""
    return {
        "version": "2.0.0",
        "voice_config": session_manager.voice_service.get_provider_info(),
        "features": [
            "modular_services",
            "session_management",
            "real_time_transcription",
            "ai_processing",
            "voice_synthesis"
        ]
    }

@fastapi_app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Voice AI Backend V2",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "websocket": "/ws/v2",
            "health": "/v2/health",
            "sessions": "/v2/sessions",
            "config": "/v2/config"
        }
    }

# ============================================================================
# MODAL APP
# ============================================================================

@app.function()
@modal.asgi_app()
def run_app():
    """Run the FastAPI app with Modal"""
    return fastapi_app 