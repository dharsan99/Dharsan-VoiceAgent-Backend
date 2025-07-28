"""
Base module containing shared classes and utilities for all voice agent versions.
"""

import asyncio
import logging
import time
import traceback
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from contextlib import contextmanager

from fastapi import WebSocket

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS
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
    WEBSOCKET = "websocket"
    SYSTEM = "system"
    TIMEOUT = "timeout"

class RecoveryAction(Enum):
    RETRY = "retry"
    FALLBACK = "fallback"
    RESTART = "restart"
    DEGRADE = "degrade"
    ALERT = "alert"

class ConnectionStatus(Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"

class ProcessingStatus(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    ERROR = "error"

# ============================================================================
# BASE CLASSES
# ============================================================================

@dataclass
class SessionInfo:
    """Base session information"""
    session_id: str
    start_time: datetime
    connection_status: ConnectionStatus
    processing_status: ProcessingStatus
    messages_processed: int = 0
    errors_count: int = 0
    total_duration: float = 0.0

class ConversationManager:
    """Manages conversation history and context"""
    
    def __init__(self, max_history: int = 10):
        self.history: List[Dict[str, Any]] = []
        self.max_history = max_history
    
    def add_exchange(self, user_input: str, ai_response: str):
        """Add a conversation exchange to memory"""
        self.history.append({
            "user": user_input,
            "ai": ai_response,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Maintain max history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
    
    def get_context_summary(self) -> str:
        """Get a summary of recent conversation context"""
        if not self.history:
            return ""
        
        # Get last few exchanges for context
        recent_exchanges = self.history[-3:]  # Last 3 exchanges
        context_parts = []
        
        for exchange in recent_exchanges:
            context_parts.append(f"User: {exchange['user']}")
            context_parts.append(f"Assistant: {exchange['ai']}")
        
        return "\n".join(context_parts)
    
    def clear_history(self):
        """Clear conversation history"""
        self.history.clear()

class ErrorRecoveryManager:
    """Manages error recovery and circuit breaker patterns"""
    
    def __init__(self):
        self.error_counts: Dict[ErrorType, int] = {error_type: 0 for error_type in ErrorType}
        self.circuit_breakers: Dict[ErrorType, bool] = {error_type: False for error_type in ErrorType}
        self.last_error_times: Dict[ErrorType, float] = {error_type: 0 for error_type in ErrorType}
        self.recovery_strategies: Dict[ErrorType, List[RecoveryAction]] = {
            ErrorType.NETWORK: [RecoveryAction.RETRY, RecoveryAction.FALLBACK],
            ErrorType.API: [RecoveryAction.RETRY, RecoveryAction.FALLBACK, RecoveryAction.DEGRADE],
            ErrorType.AUDIO: [RecoveryAction.FALLBACK, RecoveryAction.DEGRADE],
            ErrorType.WEBSOCKET: [RecoveryAction.RETRY, RecoveryAction.RESTART],
            ErrorType.SYSTEM: [RecoveryAction.RESTART, RecoveryAction.ALERT],
            ErrorType.TIMEOUT: [RecoveryAction.RETRY, RecoveryAction.FALLBACK]
        }
    
    def log_error(self, error_type: ErrorType, severity: ErrorSeverity, 
                  error_message: str, context: Dict = None) -> Dict:
        """Log an error and determine recovery strategy"""
        current_time = time.time()
        
        # Update error counts
        self.error_counts[error_type] += 1
        self.last_error_times[error_type] = current_time
        
        # Check if circuit breaker should be triggered
        if self._should_trigger_circuit_breaker(error_type):
            self.circuit_breakers[error_type] = True
            logger.warning(f"Circuit breaker triggered for {error_type.value}")
        
        error_info = {
            "type": error_type.value,
            "severity": severity.value,
            "message": error_message,
            "context": context or {},
            "timestamp": current_time,
            "count": self.error_counts[error_type],
            "circuit_breaker_active": self.circuit_breakers[error_type]
        }
        
        logger.error(f"Error logged: {error_info}")
        return error_info
    
    def _should_trigger_circuit_breaker(self, error_type: ErrorType) -> bool:
        """Determine if circuit breaker should be triggered"""
        error_count = self.error_counts[error_type]
        current_time = time.time()
        last_error_time = self.last_error_times[error_type]
        
        # Trigger if 5+ errors in last 60 seconds
        if error_count >= 5 and (current_time - last_error_time) < 60:
            return True
        
        return False
    
    def get_recovery_strategy(self, error_type: ErrorType, severity: ErrorSeverity) -> List[RecoveryAction]:
        """Get recovery strategy for error type and severity"""
        base_strategy = self.recovery_strategies.get(error_type, [RecoveryAction.FALLBACK])
        
        # Adjust strategy based on severity
        if severity == ErrorSeverity.CRITICAL:
            base_strategy.insert(0, RecoveryAction.ALERT)
        elif severity == ErrorSeverity.HIGH:
            base_strategy.insert(0, RecoveryAction.RESTART)
        
        return base_strategy
    
    def should_retry(self, error_type: ErrorType) -> bool:
        """Determine if operation should be retried"""
        if self.circuit_breakers[error_type]:
            return False
        
        # Don't retry system errors
        if error_type == ErrorType.SYSTEM:
            return False
        
        return True
    
    def get_retry_delay(self, attempt: int) -> float:
        """Get exponential backoff delay for retry attempts"""
        return min(2 ** attempt, 30)  # Max 30 seconds
    
    def get_error_stats(self) -> Dict:
        """Get error statistics"""
        return {
            "error_counts": {error_type.value: count for error_type, count in self.error_counts.items()},
            "circuit_breakers": {error_type.value: active for error_type, active in self.circuit_breakers.items()},
            "last_error_times": {error_type.value: time for error_type, time in self.last_error_times.items()}
        }

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Add a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Client connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a text message to a specific WebSocket"""
        await websocket.send_text(message)
    
    async def send_binary_message(self, data: bytes, websocket: WebSocket):
        """Send binary data to a specific WebSocket"""
        await websocket.send_bytes(data)

class AudioEnhancer:
    """Enhances audio quality for better processing"""
    
    def __init__(self, sample_rate: int = 44100, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self.enhancement_enabled = True
    
    def enhance_audio(self, audio_data: bytes) -> Optional[bytes]:
        """Enhance audio data for better quality"""
        if not self.enhancement_enabled:
            return audio_data
        
        try:
            # Basic audio enhancement logic
            # This is a placeholder - implement actual audio processing here
            return audio_data
        except Exception as e:
            logger.error(f"Audio enhancement failed: {e}")
            return audio_data
    
    def get_enhancement_info(self) -> dict:
        """Get audio enhancement configuration"""
        return {
            "enabled": self.enhancement_enabled,
            "sample_rate": self.sample_rate,
            "channels": self.channels
        }

# ============================================================================
# DECORATORS AND UTILITIES
# ============================================================================

def with_retry(error_manager: ErrorRecoveryManager, error_type: ErrorType, 
               max_retries: int = None, fallback_func: Callable = None):
    """Decorator for retry logic with error recovery"""
    
    def decorator(func):
        async def wrapper(*args, **kwargs):
            attempt = 0
            max_attempts = max_retries or 3
            
            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    error_message = f"Attempt {attempt} failed: {str(e)}"
                    
                    # Log error
                    error_info = error_manager.log_error(
                        error_type, 
                        ErrorSeverity.MEDIUM, 
                        error_message
                    )
                    
                    # Check if we should retry
                    if not error_manager.should_retry(error_type) or attempt >= max_attempts:
                        logger.error(f"Max retries reached or circuit breaker active: {error_message}")
                        if fallback_func:
                            return fallback_func(*args, **kwargs)
                        raise e
                    
                    # Wait before retry
                    delay = error_manager.get_retry_delay(attempt)
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
            
            # If we get here, all retries failed
            if fallback_func:
                return fallback_func(*args, **kwargs)
            raise Exception(f"All {max_attempts} attempts failed")
        
        return wrapper
    return decorator

class ErrorContext:
    """Context manager for error handling"""
    
    def __init__(self, error_manager: ErrorRecoveryManager, error_type: ErrorType, 
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        self.error_manager = error_manager
        self.error_type = error_type
        self.severity = severity
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            error_message = f"{exc_type.__name__}: {str(exc_val)}"
            self.error_manager.log_error(self.error_type, self.severity, error_message)
        return False  # Don't suppress the exception 