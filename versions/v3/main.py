"""
V3 Voice Agent Implementation (WebRTC-based)
Refactored version using shared core components and WebRTC for real-time communication.
"""

import asyncio
import os
import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import modal

# Import shared core components
from core.base import (
    ErrorType, ErrorSeverity, ConnectionStatus, ProcessingStatus, SessionInfo,
    with_retry, ErrorContext, logger
)

# Import V3-specific services
from .webrtc_service import WebRTCService
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
    "numpy",
    "aiortc",
    "aiohttp"
])

# Define the Modal application
app = modal.App(
    "voice-ai-backend-v3",
    image=app_image,
    secrets=[
        modal.Secret.from_name("deepgram-secret"),
        modal.Secret.from_name("groq-secret"),
        modal.Secret.from_name("elevenlabs-secret")
    ]
)

# Create FastAPI app
fastapi_app = FastAPI(title="Voice AI Backend V3", version="3.0.0")

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
webrtc_service = WebRTCService()

# ============================================================================
# WEBSOCKET HANDLER
# ============================================================================

@fastapi_app.websocket("/ws/v3")
async def websocket_handler_v3(websocket: WebSocket):
    """V3 WebSocket handler for WebRTC-based voice agent"""
    await websocket.accept()
    
    # Generate session ID
    session_id = f"v3_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
    session = session_manager.create_session(session_id)
    
    logger.info(f"V3 WebSocket connected: {session_id}")
    
    try:
        # Update connection status
        session_manager.update_session_status(session_id, ConnectionStatus.CONNECTED)
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "session_id": session_id,
            "version": "3.0.0",
            "features": ["webrtc", "voice_synthesis", "ai_processing", "real_time_transcription"],
            "webrtc_config": webrtc_service.get_config()
        }))
        
        # Initialize conversation history
        conversation_history = []
        
        # Handle WebRTC signaling
        async def handle_webrtc_signaling():
            """Handle WebRTC signaling messages"""
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    message_type = data.get("type")
                    
                    if message_type == "webrtc_offer":
                        # Handle WebRTC offer
                        offer = data.get("offer")
                        answer = await webrtc_service.handle_offer(session_id, offer)
                        
                        await websocket.send_text(json.dumps({
                            "type": "webrtc_answer",
                            "answer": answer,
                            "session_id": session_id
                        }))
                        
                    elif message_type == "webrtc_ice_candidate":
                        # Handle ICE candidate
                        candidate = data.get("candidate")
                        await webrtc_service.add_ice_candidate(session_id, candidate)
                        
                    elif message_type == "webrtc_disconnect":
                        # Handle WebRTC disconnect
                        await webrtc_service.disconnect_session(session_id)
                        
            except WebSocketDisconnect:
                logger.info("WebRTC signaling: Client disconnected")
            except Exception as e:
                logger.error(f"WebRTC signaling error: {e}")
                session.errors_count += 1
        
        # Start WebRTC signaling handler
        signaling_task = asyncio.create_task(handle_webrtc_signaling())
        
        # Set up WebRTC audio processing
        async def on_audio_data(audio_data: bytes):
            """Handle incoming audio data from WebRTC"""
            try:
                # Send to STT service
                await session_manager.stt_service.send_audio(audio_data)
            except Exception as e:
                logger.error(f"Audio processing error: {e}")
                session.errors_count += 1
        
        # Set up STT transcription handler
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
                        
                        # Synthesize speech and send via WebRTC
                        session_manager.update_session_status(session_id, processing_status=ProcessingStatus.SPEAKING)
                        
                        audio_data = await session_manager.voice_service.synthesize_speech(ai_response, websocket)
                        
                        if audio_data:
                            # Send audio via WebRTC
                            await webrtc_service.send_audio(session_id, audio_data)
                        
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
        
        # Start STT transcription
        stt_connection = await session_manager.stt_service.start_transcription(websocket, on_transcript)
        
        if not stt_connection:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Failed to initialize speech recognition",
                "session_id": session_id
            }))
            return
        
        # Set up WebRTC audio handler
        webrtc_service.set_audio_handler(session_id, on_audio_data)
        
        try:
            # Keep connection alive
            while True:
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            logger.info("V3 WebSocket disconnected")
        finally:
            # Cleanup
            signaling_task.cancel()
            await webrtc_service.disconnect_session(session_id)
            session_manager.close_session(session_id)
            
    except Exception as e:
        logger.error(f"V3 WebSocket handler error: {e}")
        session_manager.close_session(session_id)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@fastapi_app.get("/v3/health")
async def health_check_v3():
    """V3 health check endpoint"""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": session_manager.get_active_sessions_count(),
        "webrtc_sessions": webrtc_service.get_active_sessions_count(),
        "services": {
            "voice_service": session_manager.voice_service.get_provider_info(),
            "ai_service": "available",
            "stt_service": "available",
            "webrtc_service": "available"
        }
    }

@fastapi_app.get("/v3/sessions")
async def get_sessions_v3():
    """Get active V3 sessions"""
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
        "total_sessions": len(sessions),
        "webrtc_sessions": webrtc_service.get_active_sessions_count()
    }

@fastapi_app.get("/v3/webrtc/stats")
async def get_webrtc_stats():
    """Get WebRTC statistics"""
    return webrtc_service.get_stats()

@fastapi_app.get("/v3/config")
async def get_config_v3():
    """Get V3 configuration"""
    return {
        "version": "3.0.0",
        "voice_config": session_manager.voice_service.get_provider_info(),
        "webrtc_config": webrtc_service.get_config(),
        "features": [
            "webrtc_communication",
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
        "message": "Voice AI Backend V3 (WebRTC)",
        "version": "3.0.0",
        "status": "running",
        "endpoints": {
            "websocket": "/ws/v3",
            "health": "/v3/health",
            "sessions": "/v3/sessions",
            "webrtc_stats": "/v3/webrtc/stats",
            "config": "/v3/config"
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