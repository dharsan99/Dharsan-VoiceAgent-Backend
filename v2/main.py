"""
Voice AI Backend v2.0
A clean, modular implementation with improved architecture and features.
"""

import os
import asyncio
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass

import modal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Modal app configuration
app = modal.App("voice-ai-backend-v2")

# Create FastAPI app
fastapi_app = FastAPI(
    title="Voice AI Backend v2.0",
    description="Advanced voice AI with modular architecture",
    version="2.0.0"
)

# Add CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ENUMS AND DATA MODELS
# ============================================================================

class VoiceProvider(str, Enum):
    """Available voice synthesis providers"""
    ELEVENLABS = "elevenlabs"
    AZURE = "azure"
    FALLBACK = "fallback"

class ConnectionStatus(str, Enum):
    """WebSocket connection status"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class ProcessingStatus(str, Enum):
    """Processing pipeline status"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"

@dataclass
class VoiceConfig:
    """Voice configuration settings"""
    provider: VoiceProvider = VoiceProvider.ELEVENLABS
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    model_id: str = "eleven_turbo_v2"
    sample_rate: int = 44100
    output_format: str = "mp3_44100_128"

@dataclass
class SessionInfo:
    """Session information and statistics"""
    session_id: str
    start_time: datetime
    connection_status: ConnectionStatus
    processing_status: ProcessingStatus
    messages_processed: int = 0
    errors_count: int = 0
    total_duration: float = 0.0

# ============================================================================
# CORE SERVICES
# ============================================================================

class VoiceService:
    """Core voice processing service"""
    
    def __init__(self, config: VoiceConfig):
        self.config = config
        self.providers = {}
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available voice providers"""
        try:
            from elevenlabs.client import ElevenLabs
            elevenlabs_key = os.environ.get("ELEVENLABS_API_KEY")
            if elevenlabs_key:
                self.providers[VoiceProvider.ELEVENLABS] = ElevenLabs(api_key=elevenlabs_key)
                logger.info("ElevenLabs provider initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize ElevenLabs: {e}")
        
        try:
            from azure.cognitiveservices.speech import SpeechConfig
            azure_key = os.environ.get("AZURE_SPEECH_KEY")
            if azure_key and azure_key != "your_azure_speech_key_here":
                self.providers[VoiceProvider.AZURE] = azure_key
                logger.info("Azure Speech provider initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Azure Speech: {e}")
    
    async def synthesize_speech(self, text: str, websocket: WebSocket) -> Optional[bytes]:
        """Synthesize speech using the best available provider"""
        providers_order = [
            VoiceProvider.ELEVENLABS,
            VoiceProvider.AZURE,
            VoiceProvider.FALLBACK
        ]
        
        for provider in providers_order:
            try:
                if provider == VoiceProvider.ELEVENLABS and provider in self.providers:
                    return await self._synthesize_elevenlabs(text, websocket)
                elif provider == VoiceProvider.AZURE and provider in self.providers:
                    return await self._synthesize_azure(text, websocket)
                elif provider == VoiceProvider.FALLBACK:
                    return await self._synthesize_fallback(text, websocket)
            except Exception as e:
                logger.error(f"Provider {provider} failed: {e}")
                continue
        
        return None
    
    async def _synthesize_elevenlabs(self, text: str, websocket: WebSocket) -> bytes:
        """Synthesize speech using ElevenLabs"""
        logger.info(f"ElevenLabs TTS: Synthesizing: {text}")
        
        # Send word timing start
        await websocket.send_text(json.dumps({
            "type": "word_timing_start",
            "text": text,
            "provider": "elevenlabs"
        }))
        
        client = self.providers[VoiceProvider.ELEVENLABS]
        audio_stream = client.text_to_speech.stream(
            text=text,
            voice_id=self.config.voice_id,
            model_id=self.config.model_id,
            output_format=self.config.output_format
        )
        
        audio_data = bytearray()
        audio_position = 0
        word_index = 0
        words = text.split()
        
        for audio_chunk in audio_stream:
            chunk_duration = len(audio_chunk) / self.config.sample_rate
            if word_index < len(words) and audio_position > (word_index * 0.5):
                await websocket.send_text(json.dumps({
                    "type": "word_highlight",
                    "word_index": word_index,
                    "word": words[word_index],
                    "timestamp": audio_position
                }))
                word_index += 1
            audio_position += chunk_duration
            audio_data.extend(audio_chunk)
        
        await websocket.send_text(json.dumps({
            "type": "word_timing_complete",
            "total_words": len(words),
            "provider": "elevenlabs"
        }))
        
        logger.info("ElevenLabs TTS: Synthesis completed")
        return bytes(audio_data)
    
    async def _synthesize_azure(self, text: str, websocket: WebSocket) -> bytes:
        """Synthesize speech using Azure Cognitive Services"""
        logger.info(f"Azure TTS: Synthesizing: {text}")
        
        await websocket.send_text(json.dumps({
            "type": "word_timing_start",
            "text": text,
            "provider": "azure"
        }))
        
        from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, ResultReason
        
        speech_config = SpeechConfig(subscription=self.providers[VoiceProvider.AZURE], region="eastus")
        speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
        synthesizer = SpeechSynthesizer(speech_config=speech_config)
        
        result = synthesizer.speak_text_sync(text)
        if result.reason == ResultReason.SynthesizingAudioCompleted:
            await websocket.send_text(json.dumps({
                "type": "word_timing_complete",
                "total_words": len(text.split()),
                "provider": "azure"
            }))
            logger.info("Azure TTS: Synthesis completed")
            return result.audio_data
        else:
            raise Exception(f"Azure TTS failed: {result.reason}")
    
    async def _synthesize_fallback(self, text: str, websocket: WebSocket) -> bytes:
        """Generate fallback audio response"""
        logger.info(f"Fallback TTS: Synthesizing: {text}")
        
        await websocket.send_text(json.dumps({
            "type": "word_timing_start",
            "text": text,
            "provider": "fallback"
        }))
        
        import math
        sample_rate = 44100
        duration = 2.0
        samples = int(sample_rate * duration)
        audio_data = bytearray()
        
        for i in range(samples):
            t = i / sample_rate
            amplitude = 0.3
            frequency = 440
            sample = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * t))
            audio_data.extend(sample.to_bytes(2, byteorder='little', signed=True))
        
        await websocket.send_text(json.dumps({
            "type": "word_timing_complete",
            "total_words": len(text.split()),
            "provider": "fallback"
        }))
        
        logger.info("Fallback TTS: Synthesis completed")
        return bytes(audio_data)

class AIService:
    """AI processing service for LLM interactions"""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize AI client"""
        try:
            from groq import AsyncGroq
            groq_key = os.environ.get("GROQ_API_KEY")
            if groq_key:
                self.client = AsyncGroq(api_key=groq_key)
                logger.info("Groq AI client initialized")
            else:
                logger.error("GROQ_API_KEY not found")
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
    
    async def generate_response(self, user_input: str, conversation_history: List[Dict] = None) -> str:
        """Generate AI response"""
        if not self.client:
            return "I apologize, but the AI service is currently unavailable."
        
        try:
            messages = [
                {"role": "system", "content": "You are a helpful AI assistant. Keep responses concise and natural for voice interaction."}
            ]
            
            if conversation_history:
                messages.extend(conversation_history[-5:])  # Last 5 messages for context
            
            messages.append({"role": "user", "content": user_input})
            
            response = await self.client.chat.completions.create(
                messages=messages,
                model="llama3-8b-8192",
                stream=True,
                temperature=0.7,
                max_tokens=150
            )
            
            full_response = ""
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_response += content
            
            return full_response.strip()
            
        except Exception as e:
            logger.error(f"AI response generation failed: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Please try again."

class STTService:
    """Speech-to-Text service"""
    
    def __init__(self):
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize STT client"""
        try:
            from deepgram import DeepgramClient
            deepgram_key = os.environ.get("DEEPGRAM_API_KEY")
            if deepgram_key:
                self.client = DeepgramClient(deepgram_key)
                logger.info("Deepgram STT client initialized")
            else:
                logger.error("DEEPGRAM_API_KEY not found")
        except Exception as e:
            logger.error(f"Failed to initialize Deepgram client: {e}")
    
    async def start_transcription(self, websocket: WebSocket, transcript_callback: Callable):
        """Start real-time transcription"""
        if not self.client:
            logger.error("STT client not available")
            return
        
        try:
            connection = self.client.listen.asynclive.v("1")
            
            options = {
                "model": "nova-2",
                "language": "en-US",
                "smart_format": True,
                "encoding": "linear16",
                "sample_rate": 16000,
                "interim_results": True,
                "endpointing": 300,
                "punctuate": True,
                "diarize": False
            }
            
            await connection.start(options)
            logger.info("Deepgram transcription started")
            
            # Set up event handlers
            connection.on("Transcript", transcript_callback)
            
            return connection
            
        except Exception as e:
            logger.error(f"Failed to start transcription: {e}")
            return None

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

class SessionManager:
    """Manages active sessions and their state"""
    
    def __init__(self):
        self.active_sessions: Dict[str, SessionInfo] = {}
        self.voice_service = VoiceService(VoiceConfig())
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
        self.active_sessions[session_id] = session
        logger.info(f"Created session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session by ID"""
        return self.active_sessions.get(session_id)
    
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
        """Close and cleanup session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.info(f"Closed session: {session_id}")
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        return len(self.active_sessions)

# Global session manager
session_manager = SessionManager()

# ============================================================================
# WEBSOCKET HANDLER
# ============================================================================

@fastapi_app.websocket("/ws/v2")
async def websocket_handler_v2(websocket: WebSocket):
    """WebSocket handler for v2 voice AI"""
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
        
        # Audio receiver loop
        async def audio_receiver():
            try:
                async for audio_data in websocket.iter_bytes():
                    if stt_connection:
                        await stt_connection.send(audio_data)
            except WebSocketDisconnect:
                logger.info(f"Audio receiver disconnected: {session_id}")
            except Exception as e:
                logger.error(f"Audio receiver error: {e}")
        
        # Run audio receiver
        await audio_receiver()
        
    except WebSocketDisconnect:
        logger.info(f"V2 WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"V2 WebSocket error: {e}")
        session.errors_count += 1
    finally:
        session_manager.close_session(session_id)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@fastapi_app.get("/v2/health")
async def health_check_v2():
    """Health check for v2"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "active_sessions": session_manager.get_active_sessions_count(),
        "features": {
            "voice_synthesis": True,
            "ai_processing": session_manager.ai_service.client is not None,
            "speech_recognition": session_manager.stt_service.client is not None
        }
    }

@fastapi_app.get("/v2/sessions")
async def get_sessions_v2():
    """Get active sessions info"""
    sessions = []
    for session_id, session in session_manager.active_sessions.items():
        sessions.append({
            "session_id": session_id,
            "start_time": session.start_time.isoformat(),
            "connection_status": session.connection_status,
            "processing_status": session.processing_status,
            "messages_processed": session.messages_processed,
            "errors_count": session.errors_count,
            "duration": (datetime.utcnow() - session.start_time).total_seconds()
        })
    return {"sessions": sessions}

@fastapi_app.get("/v2/config")
async def get_config_v2():
    """Get current configuration"""
    return {
        "voice_config": {
            "provider": session_manager.voice_service.config.provider,
            "voice_id": session_manager.voice_service.config.voice_id,
            "model_id": session_manager.voice_service.config.model_id,
            "sample_rate": session_manager.voice_service.config.sample_rate
        },
        "available_providers": list(session_manager.voice_service.providers.keys())
    }

@fastapi_app.get("/")
async def root():
    """Root endpoint with version information"""
    return {
        "message": "Voice AI Backend",
        "versions": {
            "v1": "/v1",
            "v2": "/v2"
        },
        "current_version": "v2",
        "docs": "/docs"
    }

# ============================================================================
# MODAL DEPLOYMENT
# ============================================================================

@app.function()
@modal.asgi_app()
def run_app():
    """Modal deployment function"""
    return fastapi_app 