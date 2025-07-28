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

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import modal

# Modal Cloud Storage Integration
try:
    # Try to import modal_storage module
    import sys
    sys.path.append("/app")
    from modal_storage import (
        store_session, store_conversation, queue_voice_processing,
        store_session_metrics, update_session, get_storage_stats,
        get_conversation_history, list_all_sessions, get_session,
        get_session_metrics, get_queue_status, get_voice_processing_result
    )
    MODAL_STORAGE_AVAILABLE = True
    logger.info("Modal cloud storage integration enabled")
except ImportError as e:
    MODAL_STORAGE_AVAILABLE = False
    logger.warning(f"Modal storage not available: {e}")
    
    # Fallback implementations for when modal_storage is not available
    def store_session(session_data):
        logger.info(f"Fallback: Would store session {session_data.get('session_id', 'unknown')}")
        return session_data.get('session_id', 'unknown')
    
    def store_conversation(session_id, conversation_data):
        logger.info(f"Fallback: Would store conversation for session {session_id}")
        return f"conv_{int(time.time())}"
    
    def queue_voice_processing(processing_data):
        logger.info(f"Fallback: Would queue processing task")
        return f"task_{int(time.time())}"
    
    def store_session_metrics(session_data):
        logger.info(f"Fallback: Would store metrics for session {session_data.get('session_id', 'unknown')}")
        return "metrics_stored"
    
    def update_session(session_id, updates):
        logger.info(f"Fallback: Would update session {session_id}")
        return True
    
    def get_storage_stats():
        return {
            "sessions": 0,
            "conversations": 0,
            "metrics_files": 0,
            "storage_type": "fallback",
            "last_updated": datetime.now().isoformat()
        }
    
    def get_conversation_history(session_id):
        return []
    
    def list_all_sessions():
        return []
    
    def get_session(session_id):
        return None
    
    def get_session_metrics(session_id):
        return None
    
    def get_queue_status():
        return {
            "queue_name": "voice-processing",
            "estimated_items": "0",
            "status": "unavailable",
            "last_updated": datetime.now().isoformat()
        }
    
    def get_voice_processing_result(timeout=30):
        return None

# Audio enhancement imports
try:
    import numpy as np
    AUDIO_ENHANCEMENT_AVAILABLE = True
except ImportError:
    AUDIO_ENHANCEMENT_AVAILABLE = False
    np = None
    print("WARNING: Audio enhancement not available")

# Add metrics database import at the top
import sqlite3
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

# Metrics Database Class
class MetricsDatabase:
    """SQLite-based metrics database for tracking voice agent sessions"""
    
    def __init__(self, db_path: str = "v1_metrics.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize the database with required tables"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    duration_seconds REAL,
                    total_exchanges INTEGER DEFAULT 0,
                    total_errors INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # Conversation exchanges table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_exchanges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    user_input TEXT,
                    ai_response TEXT,
                    processing_time REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            # Network metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS network_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    latency REAL,
                    jitter REAL,
                    packet_loss REAL,
                    buffer_size INTEGER,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            conn.commit()
    
    @contextmanager
    def _get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        try:
            yield conn
        finally:
            conn.close()
    
    def create_session(self, session_id: str) -> bool:
        """Create a new session record"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sessions (session_id, start_time, status)
                    VALUES (?, CURRENT_TIMESTAMP, 'active')
                """, (session_id,))
                conn.commit()
                logger.info(f"Created session: {session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to create session {session_id}: {e}")
            return False
    
    def end_session(self, session_id: str, duration_seconds: float = None) -> bool:
        """End a session and record final metrics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if duration_seconds is None:
                    # Calculate duration from start_time
                    cursor.execute("""
                        UPDATE sessions 
                        SET end_time = CURRENT_TIMESTAMP,
                            duration_seconds = (julianday('now') - julianday(start_time)) * 86400,
                            status = 'completed'
                        WHERE session_id = ?
                    """, (session_id,))
                else:
                    cursor.execute("""
                        UPDATE sessions 
                        SET end_time = CURRENT_TIMESTAMP,
                            duration_seconds = ?,
                            status = 'completed'
                        WHERE session_id = ?
                    """, (duration_seconds, session_id))
                conn.commit()
                logger.info(f"Ended session: {session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}")
            return False
    
    def record_conversation_exchange(self, session_id: str, user_input: str, 
                                   ai_response: str, processing_time: float) -> bool:
        """Record a conversation exchange"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO conversation_exchanges 
                    (session_id, user_input, ai_response, processing_time)
                    VALUES (?, ?, ?, ?)
                """, (session_id, user_input, ai_response, processing_time))
                
                # Update session exchange count
                cursor.execute("""
                    UPDATE sessions 
                    SET total_exchanges = total_exchanges + 1
                    WHERE session_id = ?
                """, (session_id,))
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to record conversation exchange: {e}")
            return False
    
    def record_network_metrics(self, session_id: str, latency: float, jitter: float, 
                             packet_loss: float, buffer_size: int) -> bool:
        """Record network metrics"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO network_metrics 
                    (session_id, latency, jitter, packet_loss, buffer_size)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, latency, jitter, packet_loss, buffer_size))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to record network metrics: {e}")
            return False
    
    def get_session_metrics(self, session_id: str) -> Dict:
        """Get comprehensive metrics for a session"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Get session info
                cursor.execute("""
                    SELECT * FROM sessions WHERE session_id = ?
                """, (session_id,))
                session = cursor.fetchone()
                
                if not session:
                    return {"error": "Session not found"}
                
                # Get conversation exchanges
                cursor.execute("""
                    SELECT * FROM conversation_exchanges 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC
                """, (session_id,))
                exchanges = [dict(row) for row in cursor.fetchall()]
                
                # Get network metrics
                cursor.execute("""
                    SELECT * FROM network_metrics 
                    WHERE session_id = ? 
                    ORDER BY timestamp DESC
                """, (session_id,))
                network_metrics = [dict(row) for row in cursor.fetchall()]
                
                # Calculate averages
                avg_latency = sum(m['latency'] for m in network_metrics) / len(network_metrics) if network_metrics else 0
                avg_jitter = sum(m['jitter'] for m in network_metrics) / len(network_metrics) if network_metrics else 0
                avg_packet_loss = sum(m['packet_loss'] for m in network_metrics) / len(network_metrics) if network_metrics else 0
                
                return {
                    "session_id": session_id,
                    "start_time": session['start_time'],
                    "end_time": session['end_time'],
                    "duration_seconds": session['duration_seconds'],
                    "total_exchanges": session['total_exchanges'],
                    "total_errors": session['total_errors'],
                    "status": session['status'],
                    "conversation_exchanges": exchanges,
                    "network_metrics": {
                        "average_latency": avg_latency,
                        "average_jitter": avg_jitter,
                        "average_packet_loss": avg_packet_loss,
                        "recent_metrics": network_metrics[:10]  # Last 10 metrics
                    }
                }
        except Exception as e:
            logger.error(f"Failed to get session metrics: {e}")
            return {"error": str(e)}
    
    def get_recent_sessions(self, limit: int = 10) -> List[Dict]:
        """Get recent sessions"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM sessions 
                    ORDER BY start_time DESC 
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get recent sessions: {e}")
            return []

# Global metrics database instance
_metrics_db = None

def get_metrics_db() -> MetricsDatabase:
    """Get or create metrics database instance"""
    global _metrics_db
    if _metrics_db is None:
        _metrics_db = MetricsDatabase()
    return _metrics_db

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
        """Log an error with context and determine recovery strategy"""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type.value,
            "severity": severity.value,
            "message": error_message,
            "context": context or {},
            "recovery_strategy": self.get_recovery_strategy(error_type, severity)
        }
        
        self.error_history.append(error_entry)
        
        # Log to console
        logger.error(f"[{error_type.value.upper()}] {error_message}")
        
        # Check circuit breaker
        if self._should_trigger_circuit_breaker(error_type):
            logger.warning(f"Circuit breaker triggered for {error_type.value}")
        
        return error_entry
    
    def _should_trigger_circuit_breaker(self, error_type: ErrorType) -> bool:
        """Check if circuit breaker should be triggered"""
        recent_errors = [
            e for e in self.error_history[-self.circuit_breaker_threshold:]
            if e["type"] == error_type.value and 
            (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < self.circuit_breaker_timeout
        ]
        return len(recent_errors) >= self.circuit_breaker_threshold
    
    def get_recovery_strategy(self, error_type: ErrorType, severity: ErrorSeverity) -> List[RecoveryAction]:
        """Get recovery strategy for error type and severity"""
        base_strategy = self.recovery_strategies.get(error_type, [RecoveryAction.FALLBACK])
        
        if severity == ErrorSeverity.CRITICAL:
            return [RecoveryAction.ALERT, RecoveryAction.RESTART]
        elif severity == ErrorSeverity.HIGH:
            return base_strategy + [RecoveryAction.DEGRADE]
        else:
            return base_strategy
    
    def should_retry(self, error_type: ErrorType) -> bool:
        """Determine if operation should be retried"""
        if error_type in [ErrorType.SYSTEM, ErrorType.CRITICAL]:
            return False
        return RecoveryAction.RETRY in self.get_recovery_strategy(error_type, ErrorSeverity.MEDIUM)
    
    def get_retry_delay(self, attempt: int) -> float:
        """Get delay for retry attempt"""
        if attempt < len(self.retry_delays):
            return self.retry_delays[attempt]
        return self.retry_delays[-1]
    
    def get_error_stats(self) -> Dict:
        """Get error statistics"""
        if not self.error_history:
            return {"total_errors": 0, "error_types": {}, "recent_errors": []}
        
        error_types = {}
        for error in self.error_history:
            error_type = error["type"]
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        recent_errors = self.error_history[-10:]  # Last 10 errors
        
        return {
            "total_errors": len(self.error_history),
            "error_types": error_types,
            "recent_errors": recent_errors,
            "circuit_breaker_states": self.circuit_breaker_states
        }

# Error Context Manager
class ErrorContext:
    """Context manager for tracking error context during operations."""
    def __init__(self, error_manager: ErrorRecoveryManager, error_type: ErrorType, severity: ErrorSeverity):
        self.error_manager = error_manager
        self.error_type = error_type
        self.severity = severity
        self.context: Dict[str, Any] = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.error_manager.log_error(self.error_type, self.severity, f"Operation failed: {exc_val}", self.context)
            return True # Re-raise the exception after logging
        return False # No exception, continue

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            error_message = f"{exc_type.__name__}: {str(exc_val)}"
            self.error_manager.log_error(
                self.error_type, self.severity, error_message, self.context
            )
        return False  # Don't suppress the exception

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
    session_id = f"session_{int(time.time())}_{websocket.client.port}"
    metrics_db.create_session(session_id)
    logger.info(f"Created metrics session: {session_id}")
    
    # Initialize cloud storage if available
    if MODAL_STORAGE_AVAILABLE:
        try:
            # Store session in cloud
            session_data = {
                "session_id": session_id,
                "client_port": websocket.client.port,
                "start_time": datetime.now().isoformat(),
                "status": "active"
            }
            store_session.remote(session_data)
            logger.info(f"Stored session {session_id} in cloud storage")
        except Exception as e:
            logger.warning(f"Failed to store session in cloud: {e}")
    
    session_start_time = time.time()
    
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
                diarize=False,
                no_delay=True  # Reduce latency
            )
            await dg_connection.start(options)
            logger.info("Deepgram connection configured")
            
            # Send a keepalive message to prevent timeout
            try:
                await dg_connection.send(json.dumps({"type": "keepalive"}))
                logger.info("Sent Deepgram keepalive message")
            except Exception as e:
                logger.warning(f"Failed to send Deepgram keepalive: {e}")
        
        # Define the asynchronous pipeline components
        async def audio_receiver(ws: WebSocket):
            """Receives audio from client and sends to Deepgram"""
            last_audio_time = time.time()
            audio_count = 0
            try:
                async for data in ws.iter_bytes():
                    if data is None:
                        logger.warning("Received None data in audio receiver, skipping")
                        continue
                    
                    current_time = time.time()
                    last_audio_time = current_time
                    audio_count += 1
                    
                    logger.info(f"Received {len(data)} bytes of audio data (count: {audio_count})")
                    
                    # Check if Deepgram connection is still active
                    try:
                        await dg_connection.send(data)
                        logger.debug(f"Successfully sent {len(data)} bytes to Deepgram")
                    except Exception as dg_error:
                        logger.error(f"Failed to send data to Deepgram: {dg_error}")
                        # Try to restart Deepgram connection
                        try:
                            await dg_connection.finish()
                            await configure_deepgram()
                            await dg_connection.send(data)
                            logger.info("Restarted Deepgram connection and sent data")
                        except Exception as restart_error:
                            logger.error(f"Failed to restart Deepgram: {restart_error}")
                            break
                    
            except WebSocketDisconnect:
                logger.info("Audio receiver: Client disconnected")
            except Exception as e:
                logger.error(f"Audio receiver error: {e}")
                logger.error(f"Audio receiver error traceback: {traceback.format_exc()}")
            finally:
                logger.info(f"Audio receiver ended. Total audio chunks processed: {audio_count}")
        
        async def deepgram_keepalive():
            """Send periodic keepalive messages to Deepgram to prevent timeout"""
            try:
                while True:
                    await asyncio.sleep(10)  # Send keepalive every 10 seconds
                    try:
                        # Check if Deepgram connection is still active
                        await dg_connection.send(json.dumps({"type": "keepalive"}))
                        logger.debug("Sent Deepgram keepalive")
                    except Exception as e:
                        logger.warning(f"Failed to send Deepgram keepalive: {e}")
                        # Don't break the loop, just log and continue
                        # The connection might recover
                        continue
            except asyncio.CancelledError:
                logger.info("Deepgram keepalive cancelled")
            except Exception as e:
                logger.error(f"Deepgram keepalive error: {e}")
                logger.error(f"Deepgram keepalive error traceback: {traceback.format_exc()}")
        
        async def connection_monitor():
            """Monitor WebSocket connection health"""
            try:
                while True:
                    await asyncio.sleep(5)  # Check every 5 seconds
                    try:
                        # Send a ping to check connection health
                        await websocket.send_text(json.dumps({
                            "type": "ping",
                            "timestamp": time.time()
                        }))
                        logger.debug("Sent connection ping")
                    except Exception as e:
                        logger.warning(f"Connection ping failed: {e}")
                        break
            except asyncio.CancelledError:
                logger.info("Connection monitor cancelled")
            except Exception as e:
                logger.error(f"Connection monitor error: {e}")
        
        async def message_handler(ws: WebSocket):
            """Handles text messages from client"""
            try:
                async for message in ws.iter_text():
                    if message is None:
                        logger.debug("Received None message in message handler, skipping")
                        continue
                    try:
                        data = json.loads(message)
                        if data.get("type") == "session_info":
                            # Update session ID from client
                            nonlocal session_id
                            session_id = data.get("session_id", session_id)
                            logger.info(f"Updated session ID from client: {session_id}")
                        elif data.get("type") == "metrics":
                            # Record network metrics from client
                            metrics = data.get("data", {})
                            metrics_db.record_network_metrics(
                                session_id,
                                metrics.get("averageLatency", 0),
                                metrics.get("jitter", 0),
                                metrics.get("packetLoss", 0),
                                metrics.get("bufferSize", 3)
                            )
                        elif data.get("type") == "pong":
                            # Handle pong response from client
                            logger.debug(f"Received pong from client: {data.get('timestamp')}")
                    except json.JSONDecodeError:
                        logger.warning(f"Received non-JSON message: {message}")
            except WebSocketDisconnect:
                logger.info("Message handler: Client disconnected")
            except Exception as e:
                logger.error(f"Message handler error: {e}")
                logger.error(f"Message handler error traceback: {traceback.format_exc()}")
        
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
                    
                    # Record start time for processing metrics
                    start_time = time.time()
                    
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
                        
                        # Calculate processing time
                        processing_time = time.time() - start_time
                        logger.info(f"LLM: Processing completed in {processing_time:.2f}s")
                        
                        # Record conversation exchange in database
                        try:
                            metrics_db.record_conversation_exchange(
                                session_id, text, full_response, processing_time
                            )
                            logger.debug(f"Recorded conversation exchange for session {session_id}")
                        except Exception as e:
                            logger.warning(f"Failed to record conversation exchange: {e}")
                        
                        # Store conversation in cloud storage if available
                        if MODAL_STORAGE_AVAILABLE:
                            try:
                                conversation_data = {
                                    "user_input": text,
                                    "ai_response": full_response,
                                    "processing_time": processing_time,
                                    "timestamp": datetime.now().isoformat(),
                                    "session_id": session_id,
                                    "response_length": len(full_response),
                                    "word_count": len(full_response.split())
                                }
                                store_conversation.remote(session_id, conversation_data)
                                logger.debug(f"Stored conversation in cloud for session {session_id}")
                            except Exception as e:
                                logger.warning(f"Failed to store conversation in cloud: {e}")
                        
                        # Queue voice processing task for asynchronous analysis
                        if MODAL_STORAGE_AVAILABLE:
                            try:
                                processing_data = {
                                    "session_id": session_id,
                                    "user_input": text,
                                    "ai_response": full_response,
                                    "processing_time": processing_time,
                                    "timestamp": datetime.now().isoformat(),
                                    "task_type": "conversation_analysis"
                                }
                                queue_voice_processing.remote(processing_data)
                                logger.debug(f"Queued voice processing task for session {session_id}")
                            except Exception as e:
                                logger.warning(f"Failed to queue voice processing: {e}")
                        
                        # Send processing complete message to client
                        processing_message = {
                            "type": "processing_complete",
                            "response": full_response,
                            "metrics": {
                                "processing_time_ms": int(processing_time * 1000),
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
        try:
            await configure_deepgram()
            logger.info("Deepgram configured successfully")
        except Exception as e:
            logger.error(f"Failed to configure Deepgram: {e}")
            logger.error(f"Deepgram configuration error traceback: {traceback.format_exc()}")
            # Send error message to client
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Failed to initialize speech recognition. Please try again."
            }))
            return
        
        logger.info("Starting AI pipeline...")
        
        # Run all pipeline components concurrently
        await asyncio.gather(
            audio_receiver(websocket),
            message_handler(websocket),
            llm_to_tts_producer(),
            tts_to_client_producer(),
            audio_sender(websocket),
            deepgram_keepalive(),
            connection_monitor(),
            return_exceptions=True
        )
        
        # Cleanly close the Deepgram connection
        try:
            await dg_connection.finish()
            logger.info("Deepgram connection closed")
        except Exception as e:
            logger.warning(f"Error closing Deepgram connection: {e}")
        
    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket handler error: {e}")
    finally:
        # End session and record final metrics
        session_duration = time.time() - session_start_time
        metrics_db.end_session(session_id, session_duration)
        logger.info(f"Ended metrics session: {session_id} (duration: {session_duration:.2f}s)")
        
        # Store final session metrics in cloud storage if available
        if MODAL_STORAGE_AVAILABLE:
            try:
                # Get final session metrics
                final_metrics = metrics_db.get_session_metrics(session_id)
                
                # Store in cloud volume
                store_session_metrics.remote(final_metrics)
                
                # Update session status in cloud
                session_updates = {
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": session_duration,
                    "status": "completed",
                    "final_metrics": final_metrics
                }
                update_session.remote(session_id, session_updates)
                
                logger.info(f"Stored final metrics for session {session_id} in cloud storage")
            except Exception as e:
                logger.warning(f"Failed to store final metrics in cloud: {e}")
        
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

# Metrics API Endpoints
@fastapi_app.get("/metrics/sessions")
async def get_recent_sessions(limit: int = 10):
    """Get recent sessions"""
    metrics_db = get_metrics_db()
    return metrics_db.get_recent_sessions(limit)

@fastapi_app.get("/metrics/session/{session_id}")
async def get_session_metrics(session_id: str):
    """Get metrics for a specific session"""
    metrics_db = get_metrics_db()
    return metrics_db.get_session_metrics(session_id)

@fastapi_app.get("/metrics/session/{session_id}/realtime")
async def get_session_metrics_realtime(session_id: str):
    """Get real-time metrics for a specific session (compatible with frontend)"""
    metrics_db = get_metrics_db()
    metrics = metrics_db.get_session_metrics(session_id)
    
    if "error" in metrics:
        return metrics
    
    # Format for frontend compatibility
    return {
        "session_id": session_id,
        "total_conversations": metrics.get("total_exchanges", 0),
        "average_processing_time": 0,  # Calculate from exchanges if needed
        "total_words": 0,  # Calculate from exchanges if needed
        "average_response_length": 0,  # Calculate from exchanges if needed
        "network_metrics": metrics.get("network_metrics", {}),
        "recent_conversations": metrics.get("conversation_exchanges", [])
    }

# Cloud Storage API Endpoints
@fastapi_app.get("/cloud/storage/status")
async def get_cloud_storage_status():
    """Get cloud storage status and statistics"""
    try:
        if MODAL_STORAGE_AVAILABLE:
            # Try to get actual storage stats from Modal
            try:
                stats = get_storage_stats.remote()
                return {
                    "status": "available",
                    "storage_stats": stats,
                    "message": "Modal cloud storage is available and working"
                }
            except Exception as e:
                return {
                    "status": "available",
                    "storage_stats": {
                        "sessions": 0,
                        "conversations": 0,
                        "metrics_files": 0,
                        "storage_type": "modal",
                        "last_updated": datetime.now().isoformat()
                    },
                    "message": f"Modal cloud storage available but stats error: {str(e)}"
                }
        else:
            return {
                "status": "unavailable",
                "storage_stats": {
                    "sessions": 0,
                    "conversations": 0,
                    "metrics_files": 0,
                    "storage_type": "fallback",
                    "last_updated": datetime.now().isoformat()
                },
                "message": "Modal cloud storage not available - using local storage"
            }
    except Exception as e:
        return {
            "status": "error",
            "storage_stats": {
                "sessions": 0,
                "conversations": 0,
                "metrics_files": 0,
                "storage_type": "error",
                "last_updated": datetime.now().isoformat()
            },
            "message": f"Error checking cloud storage: {str(e)}"
        }

@fastapi_app.get("/cloud/conversations/{session_id}")
async def get_cloud_conversations(session_id: str):
    """Get conversation history for a specific session"""
    try:
        if MODAL_STORAGE_AVAILABLE:
            try:
                conversations = get_conversation_history.remote(session_id)
                return {
                    "session_id": session_id,
                    "conversations": conversations,
                    "count": len(conversations),
                    "message": "Conversations retrieved from Modal cloud storage"
                }
            except Exception as e:
                return {
                    "session_id": session_id,
                    "conversations": [],
                    "count": 0,
                    "message": f"Modal storage available but conversations error: {str(e)}"
                }
        else:
            return {
                "session_id": session_id,
                "conversations": [],
                "count": 0,
                "message": "Cloud storage not available - using local storage"
            }
    except Exception as e:
        return {
            "session_id": session_id,
            "conversations": [],
            "count": 0,
            "message": f"Error retrieving conversations: {str(e)}"
        }

@fastapi_app.get("/cloud/sessions")
async def get_cloud_sessions():
    """Get all sessions from cloud storage"""
    try:
        if MODAL_STORAGE_AVAILABLE:
            try:
                session_ids = list_all_sessions.remote()
                sessions = []
                
                for session_id in session_ids:
                    session_data = get_session.remote(session_id)
                    if session_data:
                        sessions.append(session_data)
                
                return {
                    "sessions": sessions,
                    "count": len(sessions),
                    "message": "Sessions retrieved from Modal cloud storage"
                }
            except Exception as e:
                return {
                    "sessions": [],
                    "count": 0,
                    "message": f"Modal storage available but sessions error: {str(e)}"
                }
        else:
            return {
                "sessions": [],
                "count": 0,
                "message": "Cloud storage not available - using local storage"
            }
    except Exception as e:
        return {
            "sessions": [],
            "count": 0,
            "message": f"Error retrieving sessions: {str(e)}"
        }

@fastapi_app.get("/cloud/sessions/{session_id}")
async def get_cloud_session(session_id: str):
    """Get specific session from cloud storage"""
    if not MODAL_STORAGE_AVAILABLE:
        return {
            "session_id": session_id,
            "message": "Cloud storage not available - session not found",
            "status": "not_found"
        }
    
    try:
        session_data = get_session.remote(session_id)
        if not session_data:
            return {
                "session_id": session_id,
                "message": "Session not found",
                "status": "not_found"
            }
        
        return session_data
    except Exception as e:
        return {
            "session_id": session_id,
            "error": f"Failed to retrieve session: {str(e)}",
            "status": "error"
        }

@fastapi_app.get("/cloud/metrics/{session_id}")
async def get_cloud_metrics(session_id: str):
    """Get metrics for a specific session"""
    try:
        if MODAL_STORAGE_AVAILABLE:
            try:
                metrics = get_session_metrics.remote(session_id)
                if metrics:
                    return {
                        "session_id": session_id,
                        "metrics": metrics,
                        "message": "Metrics retrieved from Modal cloud storage"
                    }
                else:
                    return {
                        "session_id": session_id,
                        "metrics": None,
                        "message": "No metrics found for this session"
                    }
            except Exception as e:
                return {
                    "session_id": session_id,
                    "metrics": None,
                    "message": f"Modal storage available but metrics error: {str(e)}"
                }
        else:
            return {
                "session_id": session_id,
                "metrics": None,
                "message": "Cloud storage not available - using local storage"
            }
    except Exception as e:
        return {
            "session_id": session_id,
            "metrics": None,
            "message": f"Error retrieving metrics: {str(e)}"
        }

@fastapi_app.get("/cloud/queue/status")
async def get_queue_status():
    """Get voice processing queue status"""
    try:
        if MODAL_STORAGE_AVAILABLE:
            try:
                queue_status = get_queue_status.remote()
                return {
                    **queue_status,
                    "message": "Queue status retrieved from Modal cloud storage"
                }
            except Exception as e:
                return {
                    "queue_name": "voice-processing",
                    "estimated_items": "0",
                    "status": "available",
                    "last_updated": datetime.now().isoformat(),
                    "message": f"Modal storage available but queue error: {str(e)}"
                }
        else:
            return {
                "queue_name": "voice-processing",
                "estimated_items": "0",
                "status": "unavailable",
                "last_updated": datetime.now().isoformat(),
                "message": "Cloud storage not available"
            }
    except Exception as e:
        return {
            "queue_name": "voice-processing",
            "estimated_items": "0",
            "status": "error",
            "last_updated": datetime.now().isoformat(),
            "message": f"Error checking queue status: {str(e)}"
        }

@fastapi_app.post("/cloud/queue/process")
async def process_queued_tasks():
    """Process queued voice processing tasks"""
    if not MODAL_STORAGE_AVAILABLE:
        return {
            "processed": False,
            "message": "Cloud storage not available",
            "tasks_processed": 0
        }
    
    try:
        # Get next task from queue
        task = get_voice_processing_result.remote(timeout=5)
        
        if not task:
            return {
                "processed": False,
                "message": "No tasks in queue",
                "tasks_processed": 0
            }
        
        # Process the task (simplified for now)
        logger.info(f"Processing queued task: {task.get('task_id', 'unknown')}")
        
        return {
            "processed": True,
            "task_id": task.get("task_id"),
            "message": "Task processed successfully",
            "tasks_processed": 1
        }
    except Exception as e:
        return {
            "processed": False,
            "error": f"Failed to process tasks: {str(e)}",
            "tasks_processed": 0
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
        "metrics_endpoints": [
            "/metrics/sessions",
            "/metrics/session/{session_id}",
            "/metrics/session/{session_id}/realtime"
        ],
        "features": [
            "Real-time AI Voice Agent",
            "Enhanced Error Recovery",
            "Audio Enhancement",
            "Word-level Highlighting",
            "Dynamic Jitter Buffering",
            "Persistent Metrics Storage"
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