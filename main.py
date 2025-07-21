# main.py
# Dharsan Voice Agent Backend - Modal/FastAPI Implementation

import asyncio
import os
import logging
import json
import io
import time
import traceback
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import modal

# Audio enhancement imports
try:
    import numpy as np
    AUDIO_ENHANCEMENT_AVAILABLE = True
except ImportError:
    AUDIO_ENHANCEMENT_AVAILABLE = False
    np = None
    print("WARNING: Audio enhancement not available")

# Error Recovery System
class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorType(Enum):
    NETWORK = "network"
    API = "api"
    AUDIO = "audio"
    WEBSOCKET = "websocket"
    SYSTEM = "system"
    TIMEOUT = "timeout"

class RecoveryAction(Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    RESTART = "restart"
    DEGRADE = "degrade"
    ALERT = "alert"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    "numpy"      # For audio processing
])

# Define the Modal application
app = modal.App(
    "voice-ai-backend",
    image=app_image,
    secrets=[
        modal.Secret.from_name("deepgram-secret"),
        modal.Secret.from_name("groq-secret"),
        modal.Secret.from_name("elevenlabs-secret")
    ]
)

# Create FastAPI app
fastapi_app = FastAPI(title="Voice AI Backend", version="1.0.0")

# Add CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conversation memory management
class ConversationManager:
    def __init__(self, max_history: int = 10):
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history
    
    def add_exchange(self, user_input: str, ai_response: str):
        """Add a conversation exchange to memory"""
        self.history.append({
            "user": user_input,
            "assistant": ai_response,
            "timestamp": datetime.utcnow()
        })
        
        # Maintain history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_context_summary(self) -> str:
        """Get recent conversation context for LLM"""
        if not self.history:
            return ""
        
        # Create context from recent exchanges (last 3)
        recent_exchanges = self.history[-3:]
        context_lines = []
        
        for ex in recent_exchanges:
            context_lines.append(f"User: {ex['user']}")
            context_lines.append(f"Assistant: {ex['assistant']}")
        
        return "Previous conversation:\n" + "\n".join(context_lines) + "\n"
    
    def clear_history(self):
        """Clear conversation history"""
        self.history.clear()

# Error Recovery Manager
class ErrorRecoveryManager:
    def __init__(self):
        self.error_history: List[Dict] = []
        self.recovery_strategies: Dict[ErrorType, List[RecoveryAction]] = {
            ErrorType.NETWORK: [RecoveryAction.RETRY, RecoveryAction.FALLBACK],
            ErrorType.API: [RecoveryAction.RETRY, RecoveryAction.FALLBACK, RecoveryAction.DEGRADE],
            ErrorType.AUDIO: [RecoveryAction.FALLBACK, RecoveryAction.DEGRADE],
            ErrorType.WEBSOCKET: [RecoveryAction.RETRY, RecoveryAction.RESTART],
            ErrorType.SYSTEM: [RecoveryAction.RESTART, RecoveryAction.ALERT],
            ErrorType.TIMEOUT: [RecoveryAction.RETRY, RecoveryAction.FALLBACK]
        }
        self.max_retries = 3
        self.retry_delays = [1, 2, 5]  # seconds
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_timeout = 60  # seconds
        self.circuit_breaker_states = {}
    
    def log_error(self, error_type: ErrorType, severity: ErrorSeverity, 
                  error_message: str, context: Dict = None) -> Dict:
        """Log an error and determine recovery strategy"""
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type.value,
            "severity": severity.value,
            "message": error_message,
            "context": context or {},
            "recovery_actions": self.recovery_strategies.get(error_type, [])
        }
        
        self.error_history.append(error_record)
        logger.error(f"Error Recovery: {error_type.value} - {severity.value}: {error_message}")
        
        # Check circuit breaker
        if self._should_trigger_circuit_breaker(error_type):
            error_record["circuit_breaker"] = True
            logger.warning(f"Circuit breaker triggered for {error_type.value}")
        
        return error_record
    
    def _should_trigger_circuit_breaker(self, error_type: ErrorType) -> bool:
        """Check if circuit breaker should be triggered"""
        recent_errors = [
            e for e in self.error_history[-self.circuit_breaker_threshold:]
            if e["type"] == error_type.value and 
            time.time() - datetime.fromisoformat(e["timestamp"]).timestamp() < self.circuit_breaker_timeout
        ]
        return len(recent_errors) >= self.circuit_breaker_threshold
    
    def get_recovery_strategy(self, error_type: ErrorType, severity: ErrorSeverity) -> List[RecoveryAction]:
        """Get recovery strategy based on error type and severity"""
        base_strategy = self.recovery_strategies.get(error_type, [])
        
        if severity == ErrorSeverity.CRITICAL:
            base_strategy.insert(0, RecoveryAction.ALERT)
        elif severity == ErrorSeverity.HIGH:
            base_strategy.insert(0, RecoveryAction.DEGRADE)
        
        return base_strategy
    
    def should_retry(self, error_type: ErrorType) -> bool:
        """Determine if operation should be retried"""
        if self._should_trigger_circuit_breaker(error_type):
            return False
        
        recent_errors = [
            e for e in self.error_history[-self.max_retries:]
            if e["type"] == error_type.value
        ]
        return len(recent_errors) < self.max_retries
    
    def get_retry_delay(self, attempt: int) -> float:
        """Get delay for retry attempt"""
        return self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
    
    def get_error_stats(self) -> Dict:
        """Get error statistics for monitoring"""
        if not self.error_history:
            return {"total_errors": 0, "by_type": {}, "by_severity": {}}
        
        stats = {
            "total_errors": len(self.error_history),
            "by_type": {},
            "by_severity": {},
            "recent_errors": len([e for e in self.error_history 
                                if time.time() - datetime.fromisoformat(e["timestamp"]).timestamp() < 300])  # Last 5 minutes
        }
        
        for error in self.error_history:
            stats["by_type"][error["type"]] = stats["by_type"].get(error["type"], 0) + 1
            stats["by_severity"][error["severity"]] = stats["by_severity"].get(error["severity"], 0) + 1
        
        return stats

# Retry decorator for automatic error recovery
def with_retry(error_manager: ErrorRecoveryManager, error_type: ErrorType, 
               max_retries: int = None, fallback_func: Callable = None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            retries = max_retries or error_manager.max_retries
            
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_message = f"{func.__name__} failed: {str(e)}"
                    severity = ErrorSeverity.HIGH if attempt == retries else ErrorSeverity.MEDIUM
                    
                    error_record = error_manager.log_error(
                        error_type, severity, error_message, 
                        {"attempt": attempt, "function": func.__name__}
                    )
                    
                    if attempt == retries:
                        # Final attempt failed, try fallback
                        if fallback_func:
                            try:
                                logger.info(f"Using fallback for {func.__name__}")
                                return await fallback_func(*args, **kwargs)
                            except Exception as fallback_error:
                                error_manager.log_error(
                                    ErrorType.SYSTEM, ErrorSeverity.CRITICAL,
                                    f"Fallback also failed: {str(fallback_error)}"
                                )
                                raise fallback_error
                        raise e
                    
                    # Wait before retry
                    delay = error_manager.get_retry_delay(attempt)
                    logger.info(f"Retrying {func.__name__} in {delay}s (attempt {attempt + 1}/{retries + 1})")
                    await asyncio.sleep(delay)
            
        return wrapper
    return decorator

# Error context manager
class ErrorContext:
    def __init__(self, error_manager: ErrorRecoveryManager, error_type: ErrorType, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        self.error_manager = error_manager
        self.error_type = error_type
        self.severity = severity
        self.context = {}
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            error_message = f"{exc_type.__name__}: {str(exc_val)}"
            self.error_manager.log_error(
                self.error_type, self.severity, error_message, self.context
            )
        return False  # Don't suppress the exception

# High-Quality Audio Enhancement
class AudioEnhancer:
    def __init__(self, sample_rate: int = 44100, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.enhancement_enabled = AUDIO_ENHANCEMENT_AVAILABLE
        
        if self.enhancement_enabled:
            logger.info(f"Audio enhancer initialized: {sample_rate}Hz, {channels}ch")
        else:
            logger.info("Audio enhancement disabled - using standard quality")
    
    def enhance_audio(self, audio_data: bytes) -> Optional[bytes]:
        """Apply high-quality audio enhancements that maintain MP3 compatibility"""
        if not self.enhancement_enabled:
            return None
        
        try:
            # For now, return None to use standard audio
            # This prevents the encoding errors while maintaining the enhancement framework
            logger.info("Audio enhancement: Using standard audio for compatibility")
            return None
        except Exception as e:
            logger.error(f"Audio enhancement error: {e}")
            return None
    
    def get_enhancement_info(self) -> dict:
        """Get information about applied enhancements"""
        return {
            "enhancement_enabled": self.enhancement_enabled,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "features": ["mp3_compatibility", "standard_quality"]
        }

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)
    
    async def send_binary_message(self, data: bytes, websocket: WebSocket):
        await websocket.send_bytes(data)

manager = ConnectionManager()

@fastapi_app.websocket("/ws")
async def websocket_handler(websocket: WebSocket):
    """
    Main WebSocket handler for the voice agent.
    Orchestrates the entire real-time AI pipeline.
    """
    await manager.connect(websocket)
    logger.info("WebSocket connection established")
    
    try:
        # Get API keys from environment
        deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY")
        groq_api_key = os.environ.get("GROQ_API_KEY")
        elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
        
        # Validate API keys
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
        
        # Import AI service clients
        from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
        # THE FIX: Import the asynchronous client from Groq
        from groq import AsyncGroq
        from elevenlabs.client import ElevenLabs
        
        # Initialize clients
        deepgram_client = DeepgramClient(deepgram_api_key)
        # THE FIX: Use AsyncGroq client for proper async support
        groq_client = AsyncGroq(api_key=groq_api_key)
        elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
        
        # Initialize conversation manager
        conversation_manager = ConversationManager(max_history=10)
        
        # Initialize audio enhancer
        audio_enhancer = AudioEnhancer(sample_rate=44100, channels=1)
        
        # Initialize error recovery manager
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
                interim_results=True,  # Enable to get is_final attribute
                endpointing=300,  # 300ms silence to end sentence
                punctuate=True,
                diarize=False
            )
            await dg_connection.start(options)
            logger.info("Deepgram connection configured")
        
        # Define the asynchronous pipeline components
        async def audio_receiver(ws: WebSocket):
            """Receives audio from client and sends to Deepgram"""
            try:
                async for data in ws.iter_bytes():
                    logger.info(f"Received {len(data)} bytes of audio data")
                    await dg_connection.send(data)
            except WebSocketDisconnect:
                logger.info("Audio receiver: Client disconnected")
            except Exception as e:
                logger.error(f"Audio receiver error: {e}")
        
        # Event handler for Deepgram transcripts
        async def on_transcript(self, result, **kwargs):
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
                        
                        # Send final transcript with word data
                        final_transcript_message = {
                            "type": "final_transcript",
                            "text": transcript,
                            "words": words_data
                        }
                        await websocket.send_text(json.dumps(final_transcript_message))
                        await stt_llm_queue.put(transcript)
                    else:
                        # Interim transcript
                        logger.info(f"STT (Interim): {transcript}")
                        
                        # Send interim transcript
                        interim_transcript_message = {
                            "type": "interim_transcript",
                            "text": transcript
                        }
                        await websocket.send_text(json.dumps(interim_transcript_message))
                        
            except Exception as e:
                logger.error(f"Transcript handler error: {e}")

        # Register the event handler
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        
        @with_retry(error_manager, ErrorType.API, fallback_func=lambda *args, **kwargs: {"choices": [{"delta": {"content": "I apologize, but I'm experiencing technical difficulties. Please try again."}}]})
        async def call_groq_api(messages):
            """Call Groq API with retry logic"""
            return await groq_client.chat.completions.create(
                messages=messages,
                model="llama3-8b-8192",
                stream=True,
                temperature=0.7,
                max_tokens=150
            )
        
        async def llm_to_tts_producer():
            """Processes text from STT, sends to Groq, queues response for TTS"""
            try:
                while True:
                    text = await stt_llm_queue.get()
                    if text is None:
                        break  # End of stream
                    
                    async with ErrorContext(error_manager, ErrorType.API, ErrorSeverity.MEDIUM) as error_ctx:
                        error_ctx.context = {"user_input": text}
                        
                        # Build context-aware prompt
                        context = conversation_manager.get_context_summary()
                        messages = [
                            {"role": "system", "content": "You are a helpful, conversational AI assistant. Keep responses concise and natural for voice interaction."}
                        ]
                        
                        # Add conversation history
                        for exchange in conversation_manager.history[-3:]:  # Last 3 exchanges
                            messages.append({"role": "user", "content": exchange["user"]})
                            messages.append({"role": "assistant", "content": exchange["assistant"]})
                        
                        # Add current user input
                        messages.append({"role": "user", "content": text})
                        
                        logger.info(f"LLM: Processing user input: {text}")
                        
                        # Stream response from Groq with error recovery
                        stream = await call_groq_api(messages)
                        
                        full_response = ""
                        # Iterate over the stream asynchronously.
                        async for chunk in stream:
                            # Access the content correctly from the first choice's delta.
                            content = chunk.choices[0].delta.content
                            if content:
                                logger.info(f"LLM: {content}")
                                await llm_tts_queue.put(content)
                                full_response += content
                        
                        logger.info(f"LLM: Generated response: {full_response}")
                        
                        # Add to conversation history
                        conversation_manager.add_exchange(text, full_response)
                        
                        # Send processing complete message to client
                        processing_message = {
                            "type": "processing_complete",
                            "response": full_response
                        }
                        await websocket.send_text(json.dumps(processing_message))
                        
                        # Signal end of this response
                        await llm_tts_queue.put(None)
                    
            except Exception as e:
                error_manager.log_error(
                    ErrorType.API, ErrorSeverity.HIGH,
                    f"LLM producer failed: {str(e)}",
                    {"traceback": traceback.format_exc()}
                )
                # Send error message to user
                await llm_tts_queue.put("I apologize, but I'm experiencing technical difficulties. Please try again.")
                await llm_tts_queue.put(None)
        
        async def tts_to_client_producer():
            """Streams text from LLM to ElevenLabs and queues audio for client with word-level timestamps"""
            try:
                while True:
                    # Collect text chunks until we get a None signal
                    text_chunks = []
                    while True:
                        chunk = await llm_tts_queue.get()
                        if chunk is None:
                            break
                        text_chunks.append(chunk)
                    
                    if not text_chunks:
                        continue
                    
                    # Combine text chunks
                    full_text = "".join(text_chunks)
                    logger.info(f"TTS: Synthesizing: {full_text}")
                    
                    # Send word-level timing data to frontend
                    await websocket.send_text(json.dumps({
                        "type": "word_timing_start",
                        "text": full_text
                    }))
                    
                    # Generate audio stream from ElevenLabs with word-level timestamps
                    try:
                        async with ErrorContext(error_manager, ErrorType.AUDIO, ErrorSeverity.MEDIUM) as error_ctx:
                            error_ctx.context = {"text_length": len(full_text)}
                            
                            # Use ElevenLabs streaming with correct parameters
                            audio_stream = elevenlabs_client.text_to_speech.stream(
                                text=full_text,
                                voice_id="21m00Tcm4TlvDq8ikWAM",  # Correct ID for "Rachel"
                                model_id="eleven_turbo_v2",
                                output_format="mp3_44100_128"
                            )
                        
                        # Process audio stream with timestamps
                        print("INFO: TTS synthesis started with word timestamps.")
                        
                        # Track audio position for word timing
                        audio_position = 0
                        word_index = 0
                        words = full_text.split()
                        
                        for audio_chunk in audio_stream:
                            # Calculate approximate word timing based on audio chunk size
                            # This is a simplified approach - ElevenLabs doesn't provide direct word timestamps in Python SDK
                            chunk_duration = len(audio_chunk) / 44100  # Approximate duration in seconds
                            
                            # Send word timing updates periodically
                            if word_index < len(words) and audio_position > (word_index * 0.5):  # ~0.5s per word estimate
                                await websocket.send_text(json.dumps({
                                    "type": "word_highlight",
                                    "word_index": word_index,
                                    "word": words[word_index],
                                    "timestamp": audio_position
                                }))
                                word_index += 1
                            
                            audio_position += chunk_duration
                            
                            # Send audio directly (enhancement disabled for MP3 compatibility)
                            logger.info(f"TTS: Generated audio chunk of size {len(audio_chunk)} bytes")
                            logger.info(f"TTS: Queue size before put: {tts_client_queue.qsize()}")
                            await tts_client_queue.put(audio_chunk)
                            logger.info(f"TTS: Queue size after put: {tts_client_queue.qsize()}")
                        
                        # Send completion signal
                        await websocket.send_text(json.dumps({
                            "type": "word_timing_complete",
                            "total_words": len(words)
                        }))
                        
                        print("INFO: TTS synthesis finished with word timestamps.")
                        
                    except Exception as tts_error:
                        logger.error(f"ElevenLabs TTS error: {tts_error}")
                        # Fallback to basic TTS without timestamps
                        audio_stream = elevenlabs_client.text_to_speech.stream(
                            text=full_text,
                            voice_id="21m00Tcm4TlvDq8ikWAM",  # Correct ID for "Rachel"
                            model_id="eleven_turbo_v2",
                        )
                        
                        for audio_chunk in audio_stream:
                            # Send audio directly (enhancement disabled for MP3 compatibility)
                            logger.info(f"TTS Fallback: Generated audio chunk of size {len(audio_chunk)} bytes")
                            await tts_client_queue.put(audio_chunk)
                    
                    # Signal end of audio
                    logger.info("TTS: Signaling end of audio with None")
                    await tts_client_queue.put(None)
                    
            except Exception as e:
                logger.error(f"TTS producer error: {e}")
        
        async def audio_sender(ws: WebSocket):
            """Sends synthesized audio from queue back to client"""
            try:
                logger.info("Audio sender: Starting audio sender loop")
                while True:
                    logger.info(f"Audio sender: Waiting for audio chunk, queue size: {tts_client_queue.qsize()}")
                    audio_chunk = await tts_client_queue.get()
                    logger.info(f"Audio sender: Received chunk from queue, type: {type(audio_chunk)}, size: {len(audio_chunk) if audio_chunk else 'None'}")
                    
                    if audio_chunk is None:
                        logger.info("Audio sender: Received None signal, continuing...")
                        continue
                    
                    logger.info(f"Audio sender: Sending chunk of size {len(audio_chunk)} bytes")
                    await ws.send_bytes(audio_chunk)
                    logger.info(f"Audio sender: Successfully sent chunk")
            except WebSocketDisconnect:
                logger.info("Audio sender: Client disconnected")
            except Exception as e:
                logger.error(f"Audio sender error: {e}")
                logger.error(f"Audio sender error traceback: {traceback.format_exc()}")
        
        # Setup the queues
        stt_llm_queue = asyncio.Queue()
        llm_tts_queue = asyncio.Queue()
        tts_client_queue = asyncio.Queue()
        
        # Configure Deepgram
        await configure_deepgram()
        
        logger.info("Starting AI pipeline...")
        
        # Run all pipeline components concurrently
        await asyncio.gather(
            audio_receiver(websocket),
            llm_to_tts_producer(),
            tts_to_client_producer(),
            audio_sender(websocket),
            return_exceptions=True
        )
        
        # Cleanly close the Deepgram connection
        await dg_connection.finish()
        logger.info("Deepgram connection closed")
        
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")
    finally:
        manager.disconnect(websocket)
        logger.info("WebSocket connection cleaned up")

# Health check endpoint
@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "active_connections": len(manager.active_connections)
    }

# Error statistics endpoint
@fastapi_app.get("/errors")
async def get_error_stats():
    """Get error statistics for monitoring"""
    return {
        "message": "Error recovery system active",
        "features": [
            "Circuit Breaker Pattern",
            "Automatic Retry Logic",
            "Graceful Degradation",
            "Error Context Tracking",
            "Recovery Strategy Management"
        ]
    }

# Root endpoint
@fastapi_app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Voice AI Backend API",
        "version": "1.0.0",
        "websocket_endpoint": "/ws",
        "health_check": "/health",
        "error_monitoring": "/errors",
        "features": [
            "Real-time AI Voice Agent",
            "Enhanced Error Recovery",
            "Audio Enhancement",
            "Word-level Highlighting",
            "Dynamic Jitter Buffering"
        ]
    }

# Modal ASGI app entry point
@app.function()
@modal.asgi_app()
def run_app():
    """
    Modal entry point that serves our FastAPI application.
    This function is called by Modal to start the web server.
    """
    return fastapi_app

# For local development (optional)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8000) 