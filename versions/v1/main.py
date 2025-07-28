"""
V1 Voice Agent Implementation
Refactored version using shared core components.
"""

import asyncio
import os
import logging
import json
import time
import uuid
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import modal

# Import shared core components
from core.base import (
    ConnectionManager, ConversationManager, ErrorRecoveryManager, AudioEnhancer,
    ErrorType, ErrorSeverity, ConnectionStatus, ProcessingStatus, SessionInfo,
    with_retry, ErrorContext, logger
)

# Import V1-specific components
from .metrics import MetricsDatabase, get_metrics_db
from .tts_service import TTSService

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
    "azure-cognitiveservices-speech"
])

# Define the Modal application
app = modal.App(
    "voice-ai-backend-v1",
    image=app_image,
    secrets=[
        modal.Secret.from_name("deepgram-secret"),
        modal.Secret.from_name("groq-secret"),
        modal.Secret.from_name("elevenlabs-secret"),
        modal.Secret.from_name("azure-speech-secret")
    ]
)

# Create FastAPI app
fastapi_app = FastAPI(title="Voice AI Backend V1", version="1.0.0")

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

manager = ConnectionManager()

# ============================================================================
# WEBSOCKET HANDLER
# ============================================================================

@fastapi_app.websocket("/ws")
async def websocket_handler(websocket: WebSocket):
    """
    V1 WebSocket handler for the voice agent.
    Orchestrates the entire real-time AI pipeline with metrics tracking.
    """
    await manager.connect(websocket)
    logger.info("V1 WebSocket connection established")
    
    # Initialize metrics database and session tracking
    metrics_db = get_metrics_db()
    session_id = str(uuid.uuid4())
    session_start_time = time.time()
    
    # Create session record
    metrics_db.create_session(session_id)
    logger.info(f"Created V1 metrics session: {session_id}")
    
    try:
        # Get API keys from environment
        deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY")
        groq_api_key = os.environ.get("GROQ_API_KEY")
        elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
        azure_speech_key = os.environ.get("AZURE_SPEECH_KEY")
        
        # Validate required API keys
        if not all([deepgram_api_key, groq_api_key, elevenlabs_api_key]):
            missing_keys = []
            if not deepgram_api_key:
                missing_keys.append("DEEPGRAM_API_KEY")
            if not groq_api_key:
                missing_keys.append("GROQ_API_KEY")
            if not elevenlabs_api_key:
                missing_keys.append("ELEVENLABS_API_KEY")
            logger.error(f"Missing required API keys: {missing_keys}")
            await websocket.close(code=1008, reason=f"Missing API configuration: {missing_keys}")
            return
        
        # Azure Speech key is optional
        if not azure_speech_key:
            logger.warning("AZURE_SPEECH_KEY not provided - will use fallback TTS")
            azure_speech_key = None
        
        # Import AI service clients
        from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
        from groq import AsyncGroq
        from elevenlabs.client import ElevenLabs
        
        # Initialize clients
        deepgram_client = DeepgramClient(deepgram_api_key)
        groq_client = AsyncGroq(api_key=groq_api_key)
        elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
        
        # Initialize services
        tts_service = TTSService(elevenlabs_client=elevenlabs_client, azure_speech_key=azure_speech_key)
        conversation_manager = ConversationManager(max_history=10)
        audio_enhancer = AudioEnhancer(sample_rate=44100, channels=1)
        error_manager = ErrorRecoveryManager()
        
        # Setup Deepgram connection for Speech-to-Text
        dg_connection = deepgram_client.listen.asynclive.v("1")
        
        async def configure_deepgram():
            """Configure Deepgram with optimal settings for real-time conversation"""
            options = LiveOptions(
                model="nova-2",
                language="en-US",
                smart_format=True,
                encoding="linear16",
                sample_rate=16000,
                interim_results=True,
                endpointing=150,
                punctuate=True,
                diarize=False
            )
            logger.info(f"Deepgram options: {options}")
            await dg_connection.start(options)
            logger.info("Deepgram connection configured and started")
        
        # Define the asynchronous pipeline components
        async def audio_receiver(ws: WebSocket):
            """Receives audio from client and sends to Deepgram"""
            try:
                async for data in ws.iter_bytes():
                    logger.info(f"Received {len(data)} bytes of audio data")
                    
                    # Enhance audio if enabled
                    enhanced_data = audio_enhancer.enhance_audio(data)
                    await dg_connection.send(enhanced_data)
                    
            except WebSocketDisconnect:
                logger.info("Audio receiver: Client disconnected")
            except Exception as e:
                logger.error(f"Audio receiver error: {e}")
                error_manager.log_error(ErrorType.AUDIO, ErrorSeverity.MEDIUM, str(e))
        
        # Event handler for Deepgram transcripts
        async def on_transcript(result, **kwargs):
            """Callback for Deepgram transcript events"""
            try:
                if hasattr(result, 'channel') and hasattr(result.channel, 'alternatives'):
                    transcript = result.channel.alternatives[0].transcript
                    if not transcript or not transcript.strip():
                        return
                    
                    if hasattr(result, 'is_final') and result.is_final:
                        # Final transcript with word-level data
                        logger.info(f"STT (Final): {transcript}")
                        
                        # Extract word-level data with confidence scores
                        words_data = []
                        if hasattr(result.channel.alternatives[0], 'words'):
                            for word in result.channel.alternatives[0].words:
                                words_data.append({
                                    "word": word.word,
                                    "start": word.start,
                                    "end": word.end,
                                    "confidence": word.confidence
                                })
                        
                        # Send final transcript to client
                        await websocket.send_text(json.dumps({
                            "type": "final_transcript",
                            "text": transcript,
                            "words": words_data,
                            "session_id": session_id
                        }))
                        
                        # Generate AI response
                        async with ErrorContext(error_manager, ErrorType.API):
                            ai_response = await call_groq_api([{
                                "role": "user",
                                "content": transcript
                            }])
                        
                        if ai_response:
                            # Add to conversation history
                            conversation_manager.add_exchange(transcript, ai_response)
                            
                            # Send AI response to client
                            await websocket.send_text(json.dumps({
                                "type": "ai_response",
                                "text": ai_response,
                                "session_id": session_id
                            }))
                            
                            # Synthesize speech
                            audio_data = await tts_service.synthesize_speech(
                                ai_response, websocket, asyncio.Queue()
                            )
                            
                            if audio_data:
                                await websocket.send_bytes(audio_data)
                        
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
                error_manager.log_error(ErrorType.AUDIO, ErrorSeverity.MEDIUM, str(e))
        
        @with_retry(error_manager, ErrorType.API, fallback_func=lambda *args, **kwargs: "I apologize, but I'm experiencing technical difficulties. Please try again.")
        async def call_groq_api(messages):
            """Call Groq API for AI response generation"""
            try:
                response = await groq_client.chat.completions.create(
                    model="llama3-8b-8192",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=150,
                    stream=False
                )
                
                if response.choices and len(response.choices) > 0:
                    return response.choices[0].message.content
                else:
                    return "I'm sorry, I couldn't generate a response at the moment."
                    
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                raise e
        
        # Start the pipeline
        await configure_deepgram()
        
        # Set up event handlers
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        
        # Start audio receiver
        audio_task = asyncio.create_task(audio_receiver(websocket))
        
        try:
            # Keep connection alive
            while True:
                await asyncio.sleep(1)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        finally:
            # Cleanup
            audio_task.cancel()
            await dg_connection.finish()
            
            # Record session metrics
            session_duration = time.time() - session_start_time
            metrics_db.end_session(session_id, session_duration)
            
            manager.disconnect(websocket)
            
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")
        error_manager.log_error(ErrorType.WEBSOCKET, ErrorSeverity.HIGH, str(e))
        manager.disconnect(websocket)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(manager.active_connections)
    }

@fastapi_app.get("/errors")
async def get_error_stats():
    """Get error statistics"""
    error_manager = ErrorRecoveryManager()  # This should be a global instance
    return error_manager.get_error_stats()

@fastapi_app.get("/metrics/sessions")
async def get_recent_sessions(limit: int = 10):
    """Get recent session metrics"""
    metrics_db = get_metrics_db()
    return metrics_db.get_recent_sessions(limit)

@fastapi_app.get("/metrics/session/{session_id}")
async def get_session_metrics(session_id: str):
    """Get metrics for a specific session"""
    metrics_db = get_metrics_db()
    return metrics_db.get_session_metrics(session_id)

@fastapi_app.get("/metrics/aggregated")
async def get_aggregated_metrics(hours: int = 24):
    """Get aggregated metrics"""
    metrics_db = get_metrics_db()
    return metrics_db.get_aggregated_metrics(hours)

@fastapi_app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Voice AI Backend V1",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "websocket": "/ws",
            "health": "/health",
            "errors": "/errors",
            "metrics": "/metrics/sessions"
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