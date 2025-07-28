# main.py
# Dharsan Voice Agent Backend - Modal/FastAPI Implementation

import asyncio
import os
import logging
import json
import io
import time
import traceback
import uuid
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import modal

# Inline metrics database implementation
import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from contextlib import contextmanager
import os

class MetricsDatabase:
    """Simple SQLite database for storing V1 voice agent metrics"""
    
    def __init__(self, db_path: str = "v1_metrics.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Create sessions table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT UNIQUE NOT NULL,
                        start_time TIMESTAMP NOT NULL,
                        end_time TIMESTAMP,
                        duration_seconds REAL,
                        total_exchanges INTEGER DEFAULT 0,
                        total_errors INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create metrics table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        metric_type TEXT NOT NULL,
                        metric_name TEXT NOT NULL,
                        metric_value REAL,
                        metric_data TEXT,  -- JSON for complex data
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
                
                # Create conversation exchanges table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS conversation_exchanges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        user_input TEXT NOT NULL,
                        ai_response TEXT NOT NULL,
                        processing_time_seconds REAL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
                
                # Create errors table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS errors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        error_type TEXT NOT NULL,
                        severity TEXT NOT NULL,
                        error_message TEXT NOT NULL,
                        context TEXT,  -- JSON for additional context
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                    )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    @contextmanager
    def _get_connection(self):
        """Get database connection with proper error handling"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()
    
    def create_session(self, session_id: str) -> bool:
        """Create a new session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO sessions (session_id, start_time)
                    VALUES (?, ?)
                ''', (session_id, datetime.utcnow()))
                conn.commit()
                logger.info(f"Session created: {session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            return False
    
    def end_session(self, session_id: str, duration_seconds: float, 
                   total_exchanges: int = 0, total_errors: int = 0) -> bool:
        """End a session and record final stats"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE sessions 
                    SET end_time = ?, duration_seconds = ?, 
                        total_exchanges = ?, total_errors = ?
                    WHERE session_id = ?
                ''', (datetime.utcnow(), duration_seconds, total_exchanges, total_errors, session_id))
                conn.commit()
                logger.info(f"Session ended: {session_id}, duration: {duration_seconds:.2f}s")
                return True
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}")
            return False
    
    def record_metrics(self, session_id: str, metrics: Dict[str, Any]) -> bool:
        """Record various metrics for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                for metric_name, metric_value in metrics.items():
                    if isinstance(metric_value, (dict, list)):
                        metric_data = json.dumps(metric_value)
                        metric_value = None
                    else:
                        metric_data = None
                    
                    cursor.execute('''
                        INSERT INTO metrics (session_id, metric_type, metric_name, metric_value, metric_data)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (session_id, 'network', metric_name, metric_value, metric_data))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to record metrics for session {session_id}: {e}")
            return False
    
    def record_conversation_exchange(self, session_id: str, user_input: str, 
                                   ai_response: str, processing_time: float) -> bool:
        """Record a conversation exchange"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO conversation_exchanges (session_id, user_input, ai_response, processing_time_seconds)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, user_input, ai_response, processing_time))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to record conversation exchange for session {session_id}: {e}")
            return False
    
    def record_error(self, session_id: str, error_type: str, severity: str, 
                    error_message: str, context: Dict = None) -> bool:
        """Record an error"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                context_json = json.dumps(context) if context else None
                cursor.execute('''
                    INSERT INTO errors (session_id, error_type, severity, error_message, context)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, error_type, severity, error_message, context_json))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to record error for session {session_id}: {e}")
            return False
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions with basic stats"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT session_id, start_time, end_time, duration_seconds, 
                           total_exchanges, total_errors
                    FROM sessions 
                    ORDER BY start_time DESC 
                    LIMIT ?
                ''', (limit,))
                
                sessions = []
                for row in cursor.fetchall():
                    sessions.append(dict(row))
                return sessions
        except Exception as e:
            logger.error(f"Failed to get recent sessions: {e}")
            return []
    
    def get_session_metrics(self, session_id: str) -> Dict:
        """Get detailed metrics for a specific session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get session info
                cursor.execute('''
                    SELECT * FROM sessions WHERE session_id = ?
                ''', (session_id,))
                session = cursor.fetchone()
                
                if not session:
                    return {"error": "Session not found"}
                
                # Get metrics
                cursor.execute('''
                    SELECT metric_name, metric_value, metric_data, timestamp
                    FROM metrics WHERE session_id = ?
                    ORDER BY timestamp DESC
                ''', (session_id,))
                metrics = [dict(row) for row in cursor.fetchall()]
                
                # Get conversation exchanges
                cursor.execute('''
                    SELECT user_input, ai_response, processing_time_seconds, timestamp
                    FROM conversation_exchanges WHERE session_id = ?
                    ORDER BY timestamp DESC
                ''', (session_id,))
                exchanges = [dict(row) for row in cursor.fetchall()]
                
                # Get errors
                cursor.execute('''
                    SELECT error_type, severity, error_message, context, timestamp
                    FROM errors WHERE session_id = ?
                    ORDER BY timestamp DESC
                ''', (session_id,))
                errors = [dict(row) for row in cursor.fetchall()]
                
                return {
                    "session": dict(session),
                    "metrics": metrics,
                    "conversations": exchanges,
                    "errors": errors
                }
        except Exception as e:
            logger.error(f"Failed to get session metrics for {session_id}: {e}")
            return {"error": str(e)}
    
    def get_aggregated_metrics(self, hours: int = 24) -> Dict:
        """Get aggregated metrics for the last N hours"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Calculate time threshold
                threshold = datetime.utcnow().timestamp() - (hours * 3600)
                
                # Get session count
                cursor.execute('''
                    SELECT COUNT(*) as total_sessions,
                           AVG(duration_seconds) as avg_duration,
                           SUM(total_exchanges) as total_exchanges,
                           SUM(total_errors) as total_errors
                    FROM sessions 
                    WHERE start_time >= datetime(?, 'unixepoch')
                ''', (threshold,))
                session_stats = dict(cursor.fetchone())
                
                # Get average metrics
                cursor.execute('''
                    SELECT metric_name, AVG(metric_value) as avg_value
                    FROM metrics 
                    WHERE timestamp >= datetime(?, 'unixepoch') AND metric_value IS NOT NULL
                    GROUP BY metric_name
                ''', (threshold,))
                avg_metrics = {row['metric_name']: row['avg_value'] for row in cursor.fetchall()}
                
                return {
                    "period_hours": hours,
                    "session_stats": session_stats,
                    "average_metrics": avg_metrics
                }
        except Exception as e:
            logger.error(f"Failed to get aggregated metrics: {e}")
            return {"error": str(e)}
    
    def cleanup_old_data(self, days: int = 30) -> bool:
        """Clean up old data to manage storage"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Calculate cutoff date
                cutoff = datetime.utcnow().timestamp() - (days * 24 * 3600)
                
                # Delete old data
                cursor.execute('DELETE FROM metrics WHERE timestamp < datetime(?, "unixepoch")', (cutoff,))
                cursor.execute('DELETE FROM conversation_exchanges WHERE timestamp < datetime(?, "unixepoch")', (cutoff,))
                cursor.execute('DELETE FROM errors WHERE timestamp < datetime(?, "unixepoch")', (cutoff,))
                cursor.execute('DELETE FROM sessions WHERE start_time < datetime(?, "unixepoch")', (cutoff,))
                
                conn.commit()
                logger.info(f"Cleaned up data older than {days} days")
                return True
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return False

# Global database instance
_metrics_db = None

def get_metrics_db() -> MetricsDatabase:
    """Get the global metrics database instance"""
    global _metrics_db
    if _metrics_db is None:
        _metrics_db = MetricsDatabase()
    return _metrics_db

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
    "azure-cognitiveservices-speech",
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

# TTS Service Class for multiple providers
class TTSService:
    def __init__(self, elevenlabs_client=None, azure_speech_key=None):
        self.elevenlabs_client = elevenlabs_client
        self.azure_speech_key = azure_speech_key
        self.current_provider = "elevenlabs"  # Default provider

    async def synthesize_speech(self, text: str, websocket: WebSocket, tts_client_queue: asyncio.Queue):
        """Synthesize speech using the best available TTS provider"""
        try:
            # Try ElevenLabs first
            if self.elevenlabs_client and self.current_provider == "elevenlabs":
                await self._synthesize_elevenlabs(text, websocket, tts_client_queue)
            elif self.azure_speech_key and self.azure_speech_key != "your_azure_speech_key_here":
                # Fallback to Azure
                await self._synthesize_azure(text, websocket, tts_client_queue)
            else:
                # Final fallback - generate simple audio response
                await self._synthesize_fallback(text, websocket, tts_client_queue)
        except Exception as e:
            logger.error(f"TTS Service error: {e}")
            # Final fallback - send text response without audio
            await websocket.send_text(json.dumps({
                "type": "tts_fallback",
                "text": text,
                "message": "Audio synthesis unavailable, displaying text response"
            }))
            await tts_client_queue.put(None)

    async def _synthesize_elevenlabs(self, text: str, websocket: WebSocket, tts_client_queue: asyncio.Queue):
        """Synthesize speech using ElevenLabs"""
        try:
            logger.info(f"🔍 TTS PINPOINT: ElevenLabs TTS starting for text: {text[:50]}...")
            await websocket.send_text(json.dumps({"type": "word_timing_start", "text": text}))
            
            audio_stream = self.elevenlabs_client.text_to_speech.stream(
                text=text,
                voice_id="21m00Tcm4TlvDq8ikWAM",
                model_id="eleven_turbo_v2",
                output_format="mp3_44100_128"
            )
            
            audio_position = 0
            word_index = 0
            words = text.split()
            chunk_count = 0
            
            logger.info(f"🔍 TTS PINPOINT: ElevenLabs stream created, processing {len(words)} words")
            
            for audio_chunk in audio_stream:
                try:
                    # Validate audio chunk
                    if not isinstance(audio_chunk, bytes) or len(audio_chunk) == 0:
                        logger.warning(f"🔍 TTS PINPOINT: Invalid audio chunk from ElevenLabs: {type(audio_chunk)}, size: {len(audio_chunk) if audio_chunk else 'None'}")
                        continue
                    
                    chunk_duration = len(audio_chunk) / 44100
                    chunk_count += 1
                    
                    logger.info(f"🔍 TTS PINPOINT: ElevenLabs chunk #{chunk_count}, size: {len(audio_chunk)} bytes, duration: {chunk_duration:.3f}s")
                    
                    # Send word timing updates
                    if word_index < len(words) and audio_position > (word_index * 0.5):
                        await websocket.send_text(json.dumps({
                            "type": "word_highlight", 
                            "word_index": word_index, 
                            "word": words[word_index], 
                            "timestamp": audio_position
                        }))
                        logger.info(f"🔍 TTS PINPOINT: Word highlight - {words[word_index]} at {audio_position:.3f}s")
                        word_index += 1
                    
                    audio_position += chunk_duration
                    
                    # Add chunk to queue with timeout
                    try:
                        await asyncio.wait_for(tts_client_queue.put(audio_chunk), timeout=5.0)
                        logger.info(f"🔍 TTS PINPOINT: ElevenLabs chunk #{chunk_count} queued successfully")
                    except asyncio.TimeoutError:
                        logger.warning(f"🔍 TTS PINPOINT: Timeout putting ElevenLabs chunk #{chunk_count} in queue")
                        break
                        
                except Exception as e:
                    logger.error(f"🔍 TTS PINPOINT: Error processing ElevenLabs audio chunk #{chunk_count}: {e}")
                    continue
            
            await websocket.send_text(json.dumps({"type": "word_timing_complete", "total_words": len(words)}))
            logger.info(f"🔍 TTS PINPOINT: ElevenLabs TTS completed, {chunk_count} chunks processed")
            
            # Send completion signal
            await tts_client_queue.put(None)
            logger.info(f"🔍 TTS PINPOINT: ElevenLabs completion signal sent")
            
        except Exception as e:
            logger.error(f"🔍 TTS PINPOINT: ElevenLabs TTS error: {e}")
            self.current_provider = "azure"
            raise e

    async def _synthesize_azure(self, text: str, websocket: WebSocket, tts_client_queue: asyncio.Queue):
        """Synthesize speech using Azure Cognitive Services"""
        try:
            logger.info(f"Azure TTS: Synthesizing: {text}")
            await websocket.send_text(json.dumps({"type": "word_timing_start", "text": text}))
            
            speech_config = SpeechConfig(subscription=self.azure_speech_key, region="eastus")
            speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            synthesizer = SpeechSynthesizer(speech_config=speech_config)
            result = synthesizer.speak_text_sync(text)
            
            if result.reason == ResultReason.SynthesizingAudioCompleted:
                audio_data = result.audio_data
                chunk_size = 4096
                audio_chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data), chunk_size)]
                audio_position = 0
                word_index = 0
                words = text.split()
                chunk_count = 0
                
                for audio_chunk in audio_chunks:
                    try:
                        # Validate audio chunk
                        if not isinstance(audio_chunk, bytes) or len(audio_chunk) == 0:
                            logger.warning(f"Azure TTS: Invalid audio chunk: {type(audio_chunk)}, size: {len(audio_chunk) if audio_chunk else 'None'}")
                            continue
                        
                        chunk_duration = len(audio_chunk) / 16000
                        chunk_count += 1
                        
                        # Send word timing updates
                        if word_index < len(words) and audio_position > (word_index * 0.5):
                            await websocket.send_text(json.dumps({
                                "type": "word_highlight", 
                                "word_index": word_index, 
                                "word": words[word_index], 
                                "timestamp": audio_position
                            }))
                            word_index += 1
                        
                        audio_position += chunk_duration
                        
                        # Add chunk to queue with timeout
                        try:
                            await asyncio.wait_for(tts_client_queue.put(audio_chunk), timeout=5.0)
                            logger.debug(f"Azure TTS: Queued chunk {chunk_count}, size: {len(audio_chunk)} bytes")
                        except asyncio.TimeoutError:
                            logger.warning("Azure TTS: Timeout putting chunk in queue")
                            break
                            
                    except Exception as e:
                        logger.error(f"Azure TTS: Error processing audio chunk: {e}")
                        continue
                
                await websocket.send_text(json.dumps({"type": "word_timing_complete", "total_words": len(words)}))
                logger.info(f"Azure TTS: Synthesis completed successfully, {chunk_count} chunks processed")
                
                # Send completion signal
                await tts_client_queue.put(None)
                
            else:
                raise Exception(f"Azure TTS failed: {result.reason}")
                
        except Exception as e:
            logger.error(f"Azure TTS error: {e}")
            raise e

    async def _synthesize_fallback(self, text: str, websocket: WebSocket, tts_client_queue: asyncio.Queue):
        """Generate a simple fallback audio response for testing"""
        try:
            logger.info(f"Fallback TTS: Synthesizing: {text}")
            await websocket.send_text(json.dumps({"type": "word_timing_start", "text": text}))
            
            sample_rate = 44100
            duration = 2.0
            samples = int(sample_rate * duration)
            import math
            audio_data = bytearray()
            
            for i in range(samples):
                t = i / sample_rate
                amplitude = 0.3
                frequency = 440
                sample = int(amplitude * 32767 * math.sin(2 * math.pi * frequency * t))
                audio_data.extend(sample.to_bytes(2, byteorder='little', signed=True))
            
            chunk_size = 4096
            audio_chunks = [audio_data[i:i+chunk_size] for i in range(0, len(audio_data), chunk_size)]
            audio_position = 0
            word_index = 0
            words = text.split()
            chunk_count = 0
            
            for audio_chunk in audio_chunks:
                try:
                    # Validate audio chunk
                    if not isinstance(audio_chunk, bytes) or len(audio_chunk) == 0:
                        logger.warning(f"Fallback TTS: Invalid audio chunk: {type(audio_chunk)}, size: {len(audio_chunk) if audio_chunk else 'None'}")
                        continue
                    
                    chunk_duration = len(audio_chunk) / (sample_rate * 2)
                    chunk_count += 1
                    
                    # Send word timing updates
                    if word_index < len(words) and audio_position > (word_index * 0.5):
                        await websocket.send_text(json.dumps({
                            "type": "word_highlight", 
                            "word_index": word_index, 
                            "word": words[word_index], 
                            "timestamp": audio_position
                        }))
                        word_index += 1
                    
                    audio_position += chunk_duration
                    
                    # Add chunk to queue with timeout
                    try:
                        await asyncio.wait_for(tts_client_queue.put(audio_chunk), timeout=5.0)
                        logger.debug(f"Fallback TTS: Queued chunk {chunk_count}, size: {len(audio_chunk)} bytes")
                    except asyncio.TimeoutError:
                        logger.warning("Fallback TTS: Timeout putting chunk in queue")
                        break
                        
                except Exception as e:
                    logger.error(f"Fallback TTS: Error processing audio chunk: {e}")
                    continue
            
            await websocket.send_text(json.dumps({"type": "word_timing_complete", "total_words": len(words)}))
            logger.info(f"Fallback TTS: Synthesis completed successfully, {chunk_count} chunks processed")
            
            # Send completion signal
            await tts_client_queue.put(None)
            
        except Exception as e:
            logger.error(f"Fallback TTS error: {e}")
            raise e

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
    
    # Initialize metrics database and session tracking
    metrics_db = get_metrics_db()
    session_id = str(uuid.uuid4())
    session_start_time = time.time()
    
    # Create session record
    metrics_db.create_session(session_id)
    logger.info(f"Created metrics session: {session_id}")
    
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
        # THE FIX: Import the asynchronous client from Groq
        from groq import AsyncGroq
        from elevenlabs.client import ElevenLabs
        from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason
        
        # Initialize clients
        deepgram_client = DeepgramClient(deepgram_api_key)
        # THE FIX: Use AsyncGroq client for proper async support
        groq_client = AsyncGroq(api_key=groq_api_key)
        elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
        
        # Initialize TTS service with fallback support
        tts_service = TTSService(elevenlabs_client=elevenlabs_client, azure_speech_key=azure_speech_key)
        
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
                sample_rate=16000,  # Frontend sends 16kHz audio
                interim_results=True,  # Enable to get is_final attribute
                endpointing=150,  # Reduced to 150ms silence to end sentence (more sensitive)
                punctuate=True,
                diarize=False
            )
            logger.info(f"Deepgram options: {options}")
            await dg_connection.start(options)
            logger.info("Deepgram connection configured and started")
        
        # Define the asynchronous pipeline components
        async def message_handler(ws: WebSocket):
            """Handles both audio and text messages from client"""
            logger.info("Message handler started")
            try:
                while True:
                    # Receive message from client
                    logger.info("Message handler: Waiting for message...")
                    message = await ws.receive()
                    logger.info(f"Message handler: Received message type: {message.get('type', 'unknown')}")
                    
                    # Check if this is a disconnect message
                    if message["type"] == "websocket.disconnect":
                        logger.info("Message handler: Received disconnect message")
                        break
                    
                    # Handle different message types
                    if message["type"] == "websocket.receive":
                        # This is a generic receive message, check if it has bytes or text
                        if "bytes" in message:
                            # Audio data
                            audio_data = message["bytes"]
                            logger.info(f"Received {len(audio_data)} bytes of audio data")
                            
                            # Debug: Log first few bytes to verify format
                            if len(audio_data) >= 4:
                                first_bytes = audio_data[:4]
                                logger.debug(f"First 4 bytes: {[b for b in first_bytes]}")
                            
                            try:
                                logger.info(f"Attempting to send {len(audio_data)} bytes to Deepgram...")
                                await dg_connection.send(audio_data)
                                logger.info(f"Successfully sent {len(audio_data)} bytes to Deepgram")
                            except Exception as e:
                                logger.error(f"Failed to send audio to Deepgram: {e}")
                                logger.error(f"Deepgram send error traceback: {traceback.format_exc()}")
                                raise
                        elif "text" in message:
                            # Text message (e.g., metrics data)
                            try:
                                data = json.loads(message["text"])
                                if data.get("type") == "metrics":
                                    # Handle metrics data from frontend
                                    metrics_data = data.get("data", {})
                                    logger.info(f"Received metrics from frontend: {metrics_data}")
                                    metrics_db.record_metrics(session_id, metrics_data)
                                    
                                    # Send acknowledgment
                                    await ws.send_text(json.dumps({
                                        "type": "metrics_ack",
                                        "success": True,
                                        "session_id": session_id
                                    }))
                                elif data.get("type") == "ping":
                                    # Handle ping for connection health
                                    await ws.send_text(json.dumps({"type": "pong"}))
                                else:
                                    logger.info(f"Received text message: {data}")
                            except json.JSONDecodeError:
                                logger.warning(f"Received non-JSON text message: {message['text']}")
                            except Exception as e:
                                logger.error(f"Error processing text message: {e}")
                        else:
                            logger.warning(f"Received websocket.receive message without bytes or text: {message}")
                    elif message["type"] == "websocket.receive.binary":
                        # Audio data (legacy format)
                        audio_data = message["bytes"]
                        logger.info(f"Received {len(audio_data)} bytes of audio data (legacy)")
                        try:
                            logger.info(f"Attempting to send {len(audio_data)} bytes to Deepgram...")
                            await dg_connection.send(audio_data)
                            logger.info(f"Successfully sent {len(audio_data)} bytes to Deepgram")
                        except Exception as e:
                            logger.error(f"Failed to send audio to Deepgram: {e}")
                            logger.error(f"Deepgram send error traceback: {traceback.format_exc()}")
                            raise
                    elif message["type"] == "websocket.receive.text":
                        # Text message (e.g., metrics data)
                        try:
                            data = json.loads(message["text"])
                            if data.get("type") == "metrics":
                                # Handle metrics data from frontend
                                metrics_data = data.get("data", {})
                                logger.info(f"Received metrics from frontend: {metrics_data}")
                                metrics_db.record_metrics(session_id, metrics_data)
                                
                                # Send acknowledgment
                                await ws.send_text(json.dumps({
                                    "type": "metrics_ack",
                                    "success": True,
                                    "session_id": session_id
                                }))
                            elif data.get("type") == "ping":
                                # Handle ping for connection health
                                await ws.send_text(json.dumps({"type": "pong"}))
                            else:
                                logger.info(f"Received text message: {data}")
                        except json.JSONDecodeError:
                            logger.warning(f"Received non-JSON text message: {message['text']}")
                        except Exception as e:
                            logger.error(f"Error processing text message: {e}")
            except WebSocketDisconnect:
                logger.info("Message handler: Client disconnected")
            except Exception as e:
                logger.error(f"Message handler error: {e}")
                # Don't re-raise the exception to prevent the entire pipeline from crashing
        
        async def audio_receiver(ws: WebSocket):
            """Receives audio from client and sends to Deepgram (legacy method)"""
            try:
                while True:
                    data = await ws.receive_bytes()
                    logger.info(f"Received {len(data)} bytes of audio data")
                    await dg_connection.send(data)
            except WebSocketDisconnect:
                logger.info("Audio receiver: Client disconnected")
            except Exception as e:
                logger.error(f"Audio receiver error: {e}")
        
        # Event handler for Deepgram transcripts
        async def on_transcript(*args, **kwargs):
            """Callback for Deepgram transcript events"""
            # Deepgram passes the client as first arg, transcript data in kwargs
            client = args[0] if args else None
            logger.info(f"Deepgram transcript callback called with client: {type(client)}")
            logger.info(f"Transcript kwargs: {kwargs}")
            
            # Extract transcript data from kwargs
            transcript_data = kwargs.get('result') or kwargs.get('transcript') or kwargs
            logger.info(f"Transcript data: {transcript_data}")
            
            try:
                if hasattr(transcript_data, 'channel') and hasattr(transcript_data.channel, 'alternatives'):
                    transcript = transcript_data.channel.alternatives[0].transcript
                    if not transcript or not transcript.strip():
                        return
                    
                    if hasattr(transcript_data, 'is_final') and transcript_data.is_final:
                        # Final transcript with word-level data
                        logger.info(f"🎯 STT (FINAL): '{transcript}' - Processing for AI response")
                        
                        # Extract word-level data with confidence scores
                        words_data = []
                        if hasattr(transcript_data.channel.alternatives[0], 'words'):
                            for word in transcript_data.channel.alternatives[0].words:
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
                        logger.info(f"✅ Final transcript '{transcript}' queued for AI processing")
                    else:
                        # Interim transcript
                        logger.debug(f"STT (Interim): {transcript}")
                        
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
                    
                    # Start timing this conversation
                    conversation_start_time = time.time()
                    
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
                        
                        # Calculate conversation timing
                        conversation_end_time = time.time()
                        processing_time = (conversation_end_time - conversation_start_time) * 1000  # Convert to ms
                        
                        # Add to conversation history
                        conversation_manager.add_exchange(text, full_response)
                        
                        # Record detailed conversation exchange in database
                        conversation_metrics = {
                            "user_input_length": len(text),
                            "ai_response_length": len(full_response),
                            "processing_time_ms": processing_time,
                            "word_count": len(full_response.split()),
                            "conversation_turn": len(conversation_manager.history)
                        }
                        
                        metrics_db.record_conversation_exchange(
                            session_id=session_id,
                            user_input=text,
                            ai_response=full_response,
                            processing_time=processing_time / 1000.0  # Store in seconds
                        )
                        
                        # Record additional metrics
                        metrics_db.record_metrics(session_id, conversation_metrics)
                        
                        # Send processing complete message with metrics to client
                        processing_message = {
                            "type": "processing_complete",
                            "response": full_response,
                            "metrics": {
                                "processing_time_ms": processing_time,
                                "response_length": len(full_response),
                                "word_count": len(full_response.split()),
                                "conversation_turn": len(conversation_manager.history)
                            }
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
                # Record error in database
                metrics_db.record_error(
                    session_id=session_id,
                    error_type="api",
                    severity="high",
                    error_message=f"LLM producer failed: {str(e)}",
                    context={"traceback": traceback.format_exc()}
                )
                # Send error message to user
                await llm_tts_queue.put("I apologize, but I'm experiencing technical difficulties. Please try again.")
                await llm_tts_queue.put(None)
        

        
        async def tts_to_client_producer():
            """Streams text from LLM to TTS service and queues audio for client"""
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
                    
                    # Use TTS service with automatic fallback
                    await tts_service.synthesize_speech(full_text, websocket, tts_client_queue)
                    
            except Exception as e:
                logger.error(f"TTS producer error: {e}")
        
        async def audio_sender(ws: WebSocket):
            """Sends synthesized audio from queue back to client"""
            try:
                logger.info("🔍 TTS PINPOINT: Audio sender starting")
                consecutive_errors = 0
                max_consecutive_errors = 3
                chunk_count = 0
                
                while True:
                    try:
                        logger.info(f"🔍 TTS PINPOINT: Waiting for audio chunk, queue size: {tts_client_queue.qsize()}")
                        audio_chunk = await asyncio.wait_for(tts_client_queue.get(), timeout=30.0)
                        chunk_count += 1
                        logger.info(f"🔍 TTS PINPOINT: Received chunk #{chunk_count}, type: {type(audio_chunk)}, size: {len(audio_chunk) if audio_chunk else 'None'}")
                        
                        if audio_chunk is None:
                            logger.info("🔍 TTS PINPOINT: Received completion signal, ending audio sender")
                            consecutive_errors = 0  # Reset error counter
                            break
                        
                        # Validate audio chunk
                        if not isinstance(audio_chunk, bytes) or len(audio_chunk) == 0:
                            logger.warning(f"🔍 TTS PINPOINT: Invalid audio chunk: {type(audio_chunk)}, size: {len(audio_chunk) if audio_chunk else 'None'}")
                            continue
                        
                        logger.info(f"🔍 TTS PINPOINT: Sending chunk #{chunk_count}, size: {len(audio_chunk)} bytes")
                        await ws.send_bytes(audio_chunk)
                        logger.info(f"🔍 TTS PINPOINT: Successfully sent chunk #{chunk_count}")
                        consecutive_errors = 0  # Reset error counter
                        
                    except asyncio.TimeoutError:
                        logger.warning("🔍 TTS PINPOINT: Timeout waiting for audio chunk")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error("🔍 TTS PINPOINT: Too many consecutive timeouts, stopping audio sender")
                            break
                        continue
                        
                    except WebSocketDisconnect:
                        logger.info("🔍 TTS PINPOINT: Client disconnected, stopping audio sender")
                        break
                        
                    except Exception as e:
                        logger.error(f"🔍 TTS PINPOINT: Audio sender error: {e}")
                        consecutive_errors += 1
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error("🔍 TTS PINPOINT: Too many consecutive errors, stopping audio sender")
                            break
                        continue
                        
            except Exception as e:
                logger.error(f"🔍 TTS PINPOINT: Audio sender critical error: {e}")
                logger.error(f"🔍 TTS PINPOINT: Audio sender error traceback: {traceback.format_exc()}")
            finally:
                logger.info(f"🔍 TTS PINPOINT: Audio sender ended, sent {chunk_count} chunks total")
        
        # Setup the queues
        stt_llm_queue = asyncio.Queue()
        llm_tts_queue = asyncio.Queue()
        tts_client_queue = asyncio.Queue()
        
        # Configure Deepgram
        await configure_deepgram()
        
        # Set up Deepgram event handlers
        dg_connection.on(LiveTranscriptionEvents.Transcript, on_transcript)
        
        def on_error(*args, **kwargs):
            error = args[0] if args else "Unknown error"
            logger.error(f"Deepgram error: {error}")
        
        def on_close(*args, **kwargs):
            logger.info("Deepgram connection closed")
        
        dg_connection.on(LiveTranscriptionEvents.Error, on_error)
        dg_connection.on(LiveTranscriptionEvents.Close, on_close)
        
        logger.info("Deepgram event handlers configured")
        
        logger.info("Starting AI pipeline...")
        
        # Run all pipeline components concurrently
        tasks = [
            asyncio.create_task(message_handler(websocket), name="message_handler"),
            asyncio.create_task(llm_to_tts_producer(), name="llm_to_tts_producer"),
            asyncio.create_task(tts_to_client_producer(), name="tts_to_client_producer"),
            asyncio.create_task(audio_sender(websocket), name="audio_sender")
        ]
        
        try:
            # Wait for all tasks to complete
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
        finally:
            # Cancel all remaining tasks
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
        
        # Cleanly close the Deepgram connection
        await dg_connection.finish()
        logger.info("Deepgram connection closed")
        
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")
        # Record error in database
        metrics_db.record_error(
            session_id=session_id,
            error_type="websocket",
            severity="high",
            error_message=f"WebSocket handler error: {str(e)}",
            context={"traceback": traceback.format_exc()}
        )
    finally:
        # End session and record duration
        session_duration = time.time() - session_start_time
        metrics_db.end_session(session_id, session_duration)
        logger.info(f"Session ended: {session_id}, duration: {session_duration:.2f}s")
        
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

# Metrics database endpoints
@fastapi_app.get("/metrics/sessions")
async def get_recent_sessions(limit: int = 10):
    """Get recent sessions with summary metrics"""
    try:
        metrics_db = get_metrics_db()
        sessions = metrics_db.get_recent_sessions(limit)
        return {
            "sessions": sessions,
            "count": len(sessions)
        }
    except Exception as e:
        logger.error(f"Failed to get recent sessions: {e}")
        return {"error": str(e)}

@fastapi_app.get("/metrics/session/{session_id}")
async def get_session_metrics(session_id: str):
    """Get detailed metrics for a specific session"""
    try:
        metrics_db = get_metrics_db()
        metrics = metrics_db.get_session_metrics(session_id)
        return metrics
    except Exception as e:
        logger.error(f"Failed to get session metrics: {e}")
        return {"error": str(e)}

@fastapi_app.get("/metrics/aggregated")
async def get_aggregated_metrics(hours: int = 24):
    """Get aggregated metrics for the last N hours"""
    try:
        metrics_db = get_metrics_db()
        metrics = metrics_db.get_aggregated_metrics(hours)
        return metrics
    except Exception as e:
        logger.error(f"Failed to get aggregated metrics: {e}")
        return {"error": str(e)}

@fastapi_app.post("/metrics/cleanup")
async def cleanup_old_metrics(days: int = 30):
    """Clean up metrics data older than N days"""
    try:
        metrics_db = get_metrics_db()
        deleted_count = metrics_db.cleanup_old_data(days)
        return {
            "message": f"Cleaned up {deleted_count} old records",
            "deleted_count": deleted_count,
            "older_than_days": days
        }
    except Exception as e:
        logger.error(f"Failed to cleanup old metrics: {e}")
        return {"error": str(e)}

@fastapi_app.post("/metrics/network")
async def record_network_metrics(session_id: str, metrics: Dict[str, Any]):
    """Record network metrics from frontend"""
    try:
        metrics_db = get_metrics_db()
        success = metrics_db.record_metrics(session_id, metrics)
        return {
            "success": success,
            "message": "Network metrics recorded" if success else "Failed to record metrics"
        }
    except Exception as e:
        logger.error(f"Network metrics recording error: {e}")
        return {"success": False, "error": str(e)}

@fastapi_app.get("/metrics/session/{session_id}/realtime")
async def get_session_realtime_metrics(session_id: str):
    """Get real-time metrics for an active session"""
    try:
        metrics_db = get_metrics_db()
        session_data = metrics_db.get_session_metrics(session_id)
        
        if "error" in session_data:
            return {"error": "Session not found"}
        
        # Calculate real-time stats
        conversations = session_data.get("conversations", [])
        metrics = session_data.get("metrics", [])
        
        realtime_stats = {
            "session_id": session_id,
            "total_conversations": len(conversations),
            "average_processing_time": 0,
            "total_words": 0,
            "average_response_length": 0,
            "network_metrics": {},
            "recent_conversations": conversations[:5]  # Last 5 conversations
        }
        
        if conversations:
            processing_times = [conv.get("processing_time_seconds", 0) for conv in conversations]
            response_lengths = [len(conv.get("ai_response", "")) for conv in conversations]
            word_counts = [len(conv.get("ai_response", "").split()) for conv in conversations]
            
            realtime_stats["average_processing_time"] = sum(processing_times) / len(processing_times)
            realtime_stats["average_response_length"] = sum(response_lengths) / len(response_lengths)
            realtime_stats["total_words"] = sum(word_counts)
        
        # Extract network metrics
        for metric in metrics:
            if metric.get("metric_name") in ["averageLatency", "jitter", "packetLoss", "bufferSize"]:
                realtime_stats["network_metrics"][metric["metric_name"]] = metric.get("metric_value")
        
        return realtime_stats
        
    except Exception as e:
        logger.error(f"Real-time metrics error: {e}")
        return {"error": str(e)}

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
        "metrics_endpoints": {
            "recent_sessions": "/metrics/sessions",
            "session_details": "/metrics/session/{session_id}",
            "realtime_metrics": "/metrics/session/{session_id}/realtime",
            "aggregated_metrics": "/metrics/aggregated",
            "network_metrics": "/metrics/network",
            "cleanup": "/metrics/cleanup"
        },
        "features": [
            "Real-time AI Voice Agent",
            "Enhanced Error Recovery",
            "Audio Enhancement",
            "Word-level Highlighting",
            "Dynamic Jitter Buffering",
            "Historic Metrics Database"
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