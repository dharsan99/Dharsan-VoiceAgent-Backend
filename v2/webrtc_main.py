"""
Voice AI Backend v2 - WebRTC Implementation
Low-latency audio transport using WebRTC and aiortc
"""

import asyncio
import json
import logging
import os
import uuid
import time
from typing import Dict, Optional, Set
from datetime import datetime, timedelta

import modal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

# WebRTC imports
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.mediastreams import MediaStreamError

# Audio processing
import numpy as np
import av

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis integration
try:
    from redis_manager import redis_manager, SessionData, SignalingMessage, MessageType
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis manager not available, using in-memory storage only")

# Performance monitoring
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client.openmetrics.exposition import generate_latest as generate_latest_openmetrics

# Prometheus metrics
WEBSOCKET_CONNECTIONS = Gauge('webrtc_websocket_connections_total', 'Total WebSocket connections')
ACTIVE_SESSIONS = Gauge('webrtc_active_sessions_total', 'Total active sessions')
PEER_CONNECTIONS = Gauge('webrtc_peer_connections_total', 'Total WebRTC peer connections')
SIGNALING_MESSAGES = Counter('webrtc_signaling_messages_total', 'Total signaling messages', ['type'])
SIGNALING_LATENCY = Histogram('webrtc_signaling_latency_seconds', 'Signaling message latency')
SESSION_DURATION = Histogram('webrtc_session_duration_seconds', 'Session duration')
AUDIO_FRAMES_PROCESSED = Counter('webrtc_audio_frames_processed_total', 'Total audio frames processed')
ERRORS_TOTAL = Counter('webrtc_errors_total', 'Total errors', ['type'])

# Modal app configuration
app = modal.App("voice-ai-backend-v2")

# Create Modal image with WebRTC dependencies
image = modal.Image.debian_slim(python_version="3.11").pip_install([
    "fastapi",
    "uvicorn[standard]",
    "websockets",
    "aiortc>=1.5.0",
    "aioice>=0.9.0",
    "pyee>=11.0.0",
    "python-dotenv",
    "pydantic",
    "numpy",
    "requests",
    "aiofiles",
    "av",  # PyAV for audio/video processing
    "deepgram-sdk",
    "groq",
    "elevenlabs",
    "prometheus-client",
    "redis>=4.5.0"  # Redis client for session persistence
])

# Create FastAPI app
fastapi_app = FastAPI(
    title="Voice AI Backend v2 - WebRTC",
    description="Low-latency voice AI with WebRTC transport",
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
# DATA MODELS
# ============================================================================

class SignalingMessage(BaseModel):
    type: str
    session_id: str
    data: Optional[Dict] = None

class WebRTCOffer(BaseModel):
    sdp: str
    type: str = "offer"

class WebRTCAnswer(BaseModel):
    sdp: str
    type: str = "answer"

class ICECandidate(BaseModel):
    candidate: str
    sdpMLineIndex: int
    sdpMid: str

# ============================================================================
# SESSION MANAGEMENT
# ============================================================================

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict] = {}
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self.redis_enabled = False
    
    async def initialize_redis(self):
        """Initialize Redis connection"""
        if not REDIS_AVAILABLE:
            logger.info("Redis not available, using in-memory storage")
            self.redis_enabled = False
            return
            
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            await redis_manager.connect()
            self.redis_enabled = True
            await redis_manager.start_maintenance_tasks()
            logger.info("Redis initialized successfully")
        except Exception as e:
            logger.warning(f"Redis initialization failed, using in-memory storage: {e}")
            self.redis_enabled = False
    
    async def create_session(self, session_id: str) -> Dict:
        """Create a new session"""
        session = {
            "id": session_id,
            "created_at": datetime.utcnow(),
            "status": "active",
            "peer_connections": {},
            "is_ai_speaking": False,
            "transcript": "",
            "ai_response": "",
            "metrics": {
                "start_time": time.time(),
                "messages_received": 0,
                "errors_count": 0,
                "audio_frames_processed": 0
            }
        }
        
        # Store in memory
        self.sessions[session_id] = session
        self.active_connections[session_id] = set()
        
        # Store in Redis if available
        if self.redis_enabled and REDIS_AVAILABLE:
            try:
                session_data = SessionData(
                    id=session_id,
                    created_at=session["created_at"].isoformat(),
                    status=session["status"],
                    peer_connections=session["peer_connections"],
                    is_ai_speaking=session["is_ai_speaking"],
                    transcript=session["transcript"],
                    ai_response=session["ai_response"],
                    metrics=session["metrics"],
                    last_activity=datetime.now().isoformat(),
                    expires_at=(datetime.now() + timedelta(hours=1)).isoformat()
                )
                await redis_manager.save_session(session_data)
            except Exception as e:
                logger.error(f"Failed to save session to Redis: {e}")
        
        # Update metrics
        ACTIVE_SESSIONS.inc()
        
        logger.info(f"Created session: {session_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID"""
        # Try memory first
        session = self.sessions.get(session_id)
        if session:
            return session
        
        # Try Redis if available
        if self.redis_enabled and REDIS_AVAILABLE:
            try:
                session_data = await redis_manager.get_session(session_id)
                if session_data:
                    # Convert back to dict format
                    session = {
                        "id": session_data.id,
                        "created_at": datetime.fromisoformat(session_data.created_at),
                        "status": session_data.status,
                        "peer_connections": session_data.peer_connections,
                        "is_ai_speaking": session_data.is_ai_speaking,
                        "transcript": session_data.transcript,
                        "ai_response": session_data.ai_response,
                        "metrics": session_data.metrics
                    }
                    # Cache in memory
                    self.sessions[session_id] = session
                    return session
            except Exception as e:
                logger.error(f"Failed to get session from Redis: {e}")
        
        return None
    
    def add_connection(self, session_id: str, websocket: WebSocket):
        """Add WebSocket connection to session"""
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        self.active_connections[session_id].add(websocket)
        
        # Update metrics
        WEBSOCKET_CONNECTIONS.inc()
    
    def remove_connection(self, session_id: str, websocket: WebSocket):
        """Remove WebSocket connection from session"""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        
        # Update metrics
        WEBSOCKET_CONNECTIONS.dec()
    
    async def close_session(self, session_id: str):
        """Close a session and record metrics"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            duration = time.time() - session["metrics"]["start_time"]
            
            # Record session duration
            SESSION_DURATION.observe(duration)
            
            # Record final metrics
            AUDIO_FRAMES_PROCESSED.inc(session["metrics"]["audio_frames_processed"])
            ERRORS_TOTAL.labels(type="session").inc(session["metrics"]["errors_count"])
            
            # Clean up memory
            del self.sessions[session_id]
            if session_id in self.active_connections:
                del self.active_connections[session_id]
            
            # Clean up Redis
            if self.redis_enabled:
                try:
                    await redis_manager.delete_session(session_id)
                except Exception as e:
                    logger.error(f"Failed to delete session from Redis: {e}")
            
            # Update metrics
            ACTIVE_SESSIONS.dec()
            
            logger.info(f"Closed session: {session_id}, duration: {duration:.2f}s")
    
    def broadcast_to_session(self, session_id: str, message: Dict):
        """Broadcast message to all connections in a session"""
        if session_id in self.active_connections:
            message_str = json.dumps(message)
            for websocket in self.active_connections[session_id]:
                try:
                    asyncio.create_task(websocket.send_text(message_str))
                except Exception as e:
                    logger.error(f"Failed to send message: {e}")
                    ERRORS_TOTAL.labels(type="broadcast").inc()

# Global session manager
session_manager = SessionManager()

# ============================================================================
# AI GENERATED AUDIO TRACK
# ============================================================================

class AIGeneratedAudioTrack(MediaStreamTrack):
    """Custom MediaStreamTrack for AI-generated audio"""
    kind = "audio"

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id
        self.audio_queue = asyncio.Queue()
        self.sample_rate = 48000
        self.channels = 1
        self.samples_per_frame = 960  # 20ms at 48kHz
        self.frames_processed = 0
        
    async def recv(self):
        """Called by aiortc to get the next audio frame"""
        try:
            # Get audio data from queue
            audio_data = await asyncio.wait_for(self.audio_queue.get(), timeout=1.0)
            
            # Create audio frame
            frame = av.AudioFrame.from_ndarray(
                audio_data,
                format='s16',
                layout='mono'
            )
            frame.sample_rate = self.sample_rate
            frame.pts = 0
            frame.time_base = av.time_base
            
            # Update metrics
            self.frames_processed += 1
            AUDIO_FRAMES_PROCESSED.inc()
            
            return frame
            
        except asyncio.TimeoutError:
            # Return silence if no audio data
            silence = np.zeros(self.samples_per_frame, dtype=np.int16)
            frame = av.AudioFrame.from_ndarray(
                silence,
                format='s16',
                layout='mono'
            )
            frame.sample_rate = self.sample_rate
            frame.pts = 0
            frame.time_base = av.time_base
            return frame
    
    async def push_audio(self, audio_data: np.ndarray):
        """Push audio data to the queue"""
        await self.audio_queue.put(audio_data)

# ============================================================================
# WEBRTC PEER CONNECTION MANAGER
# ============================================================================

class WebRTCManager:
    def __init__(self):
        self.peer_connections: Dict[str, RTCPeerConnection] = {}
        self.audio_tracks: Dict[str, AIGeneratedAudioTrack] = {}
    
    async def create_peer_connection(self, session_id: str) -> RTCPeerConnection:
        """Create a new RTCPeerConnection for a session"""
        pc = RTCPeerConnection()
        self.peer_connections[session_id] = pc
        
        # Configure ICE servers for NAT traversal
        # Note: aiortc uses a different approach for ICE servers
        # The STUN servers are configured globally in the library
        # For cloud deployments, we may need to handle ICE differently
        
        # Update metrics
        PEER_CONNECTIONS.inc()
        
        # Create AI audio track
        ai_track = AIGeneratedAudioTrack(session_id)
        self.audio_tracks[session_id] = ai_track
        pc.addTrack(ai_track)
        
        # Handle incoming tracks (user audio)
        @pc.on("track")
        async def on_track(track):
            logger.info(f"Received track: {track.kind} for session {session_id}")
            if track.kind == "audio":
                await self.handle_user_audio(session_id, track)
        
        # Handle connection state changes
        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state for {session_id}: {pc.connectionState}")
            if pc.connectionState == "failed":
                logger.error(f"WebRTC connection failed for session {session_id}")
                ERRORS_TOTAL.labels(type="connection_failed").inc()
                await self.cleanup_session(session_id)
            elif pc.connectionState == "connected":
                logger.info(f"WebRTC connection established for session {session_id}")
            elif pc.connectionState == "disconnected":
                logger.warning(f"WebRTC connection disconnected for session {session_id}")
                ERRORS_TOTAL.labels(type="connection_disconnected").inc()
        
        # Handle ICE connection state changes
        @pc.on("iceconnectionstatechange")
        async def on_iceconnectionstatechange():
            logger.info(f"ICE connection state for {session_id}: {pc.iceConnectionState}")
            if pc.iceConnectionState == "failed":
                logger.error(f"ICE connection failed for session {session_id}")
                ERRORS_TOTAL.labels(type="ice_failed").inc()
            elif pc.iceConnectionState == "connected":
                logger.info(f"ICE connection established for session {session_id}")
            elif pc.iceConnectionState == "disconnected":
                logger.warning(f"ICE connection disconnected for session {session_id}")
                ERRORS_TOTAL.labels(type="ice_disconnected").inc()
        
        # Handle ICE gathering state changes
        @pc.on("icegatheringstatechange")
        async def on_icegatheringstatechange():
            logger.info(f"ICE gathering state for {session_id}: {pc.iceGatheringState}")
        
        # Handle ICE candidates
        @pc.on("icecandidate")
        async def on_icecandidate(candidate):
            if candidate:
                logger.info(f"Generated ICE candidate for {session_id}: {candidate.candidate}")
                # Send candidate to client via WebSocket
                candidate_message = {
                    "type": "ice-candidate",
                    "candidate": candidate.candidate,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                    "sdpMid": candidate.sdpMid
                }
                # Note: We'll need to store the WebSocket connection to send this
                # For now, just log it
            else:
                logger.info(f"ICE candidate gathering complete for {session_id}")
        
        return pc
    
    async def handle_user_audio(self, session_id: str, track: MediaStreamTrack):
        """Handle incoming user audio"""
        logger.info(f"Processing user audio for session {session_id}")
        
        # Update session metrics
        session = session_manager.get_session(session_id)
        if session:
            session["metrics"]["audio_frames_processed"] += 1
        
        # For now, just log that we received audio
        # In a full implementation, this would:
        # 1. Process audio through STT
        # 2. Send to LLM
        # 3. Generate TTS response
        # 4. Push to AI audio track
        
        try:
            while True:
                frame = await track.recv()
                # Process audio frame here
                # await self.process_audio_frame(session_id, frame)
                
        except MediaStreamError:
            logger.info(f"User audio track ended for session {session_id}")
    
    async def cleanup_session(self, session_id: str):
        """Clean up resources for a session"""
        if session_id in self.peer_connections:
            pc = self.peer_connections[session_id]
            await pc.close()
            del self.peer_connections[session_id]
            
            # Update metrics
            PEER_CONNECTIONS.dec()
        
        if session_id in self.audio_tracks:
            del self.audio_tracks[session_id]
        
        # Close session
        session_manager.close_session(session_id)
        
        logger.info(f"Cleaned up session: {session_id}")

# Global WebRTC manager
webrtc_manager = WebRTCManager()

# ============================================================================
# WEBRTC SIGNALING ENDPOINTS
# ============================================================================

@fastapi_app.websocket("/ws/v2/{session_id}")
async def webrtc_signaling(websocket: WebSocket, session_id: str):
    """WebRTC signaling endpoint"""
    try:
        await websocket.accept()
        logger.info(f"WebSocket connection accepted for session {session_id}")
        
        # Initialize Redis if not already done and available
        if not session_manager.redis_enabled and REDIS_AVAILABLE:
            try:
                await session_manager.initialize_redis()
            except Exception as e:
                logger.warning(f"Failed to initialize Redis: {e}")
        
        # Create or get session
        session = await session_manager.get_session(session_id)
        if not session:
            session = await session_manager.create_session(session_id)
        
        # Add connection to session
        session_manager.add_connection(session_id, websocket)
        
        # Send initial connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Main message loop
        while True:
            try:
                # Receive signaling message with timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                
                # Update session metrics
                session["metrics"]["messages_received"] += 1
                
                await handle_signaling_message(session_id, message, websocket)
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_text(json.dumps({"type": "ping"}))
                except Exception:
                    break
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received for session {session_id}: {e}")
                ERRORS_TOTAL.labels(type="json_decode").inc()
            except Exception as e:
                logger.error(f"Error processing message for session {session_id}: {e}")
                ERRORS_TOTAL.labels(type="message_processing").inc()
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"Error in WebSocket connection for session {session_id}: {e}")
        ERRORS_TOTAL.labels(type="websocket_error").inc()
    finally:
        try:
            session_manager.remove_connection(session_id, websocket)
            logger.info(f"Cleaned up WebSocket connection for session {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up WebSocket connection for session {session_id}: {e}")

async def handle_signaling_message(session_id: str, message: Dict, websocket: WebSocket):
    """Handle WebRTC signaling messages"""
    message_type = message.get("type")
    start_time = time.time()
    
    # Update metrics
    SIGNALING_MESSAGES.labels(type=message_type).inc()
    
    try:
        if message_type == "offer":
            await handle_offer(session_id, message, websocket)
        elif message_type == "ice-candidate":
            await handle_ice_candidate(session_id, message, websocket)
        elif message_type == "ping":
            await websocket.send_text(json.dumps({"type": "pong"}))
        else:
            logger.warning(f"Unknown message type: {message_type}")
    finally:
        # Record latency
        latency = time.time() - start_time
        SIGNALING_LATENCY.observe(latency)

async def handle_offer(session_id: str, message: Dict, websocket: WebSocket):
    """Handle WebRTC offer"""
    try:
        logger.info(f"Processing offer for session {session_id}")
        
        # Create peer connection if it doesn't exist
        if session_id not in webrtc_manager.peer_connections:
            logger.info(f"Creating new peer connection for session {session_id}")
            await webrtc_manager.create_peer_connection(session_id)
        
        pc = webrtc_manager.peer_connections[session_id]
        logger.info(f"Using existing peer connection for session {session_id}")
        
        # Set remote description (offer)
        offer = RTCSessionDescription(sdp=message["sdp"], type="offer")
        logger.info(f"Setting remote description for session {session_id}")
        await pc.setRemoteDescription(offer)
        
        # Create answer
        logger.info(f"Creating answer for session {session_id}")
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        
        # Send answer back to client
        response = {
            "type": "answer",
            "sdp": pc.localDescription.sdp
        }
        await websocket.send_text(json.dumps(response))
        
        logger.info(f"Successfully handled offer for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error handling offer for session {session_id}: {e}")
        ERRORS_TOTAL.labels(type="offer").inc()
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))

async def handle_ice_candidate(session_id: str, message: Dict, websocket: WebSocket):
    """Handle ICE candidate"""
    try:
        if session_id in webrtc_manager.peer_connections:
            pc = webrtc_manager.peer_connections[session_id]
            candidate = message["candidate"]
            await pc.addIceCandidate(candidate)
            logger.info(f"Added ICE candidate for session {session_id}")
    except Exception as e:
        logger.error(f"Error handling ICE candidate: {e}")
        ERRORS_TOTAL.labels(type="ice_candidate").inc()

# ============================================================================
# API ENDPOINTS
# ============================================================================

@fastapi_app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Voice AI Backend v2 - WebRTC with Redis",
        "version": "2.0.0",
        "features": [
            "WebRTC", 
            "Low-latency audio", 
            "Real-time signaling", 
            "Performance monitoring",
            "Redis session persistence",
            "Message bus"
        ],
        "endpoints": {
            "signaling": "/ws/v2/{session_id}",
            "websocket_test": "/ws/test",
            "health": "/health",
            "sessions": "/v2/sessions",
            "metrics": "/metrics"
        }
    }

@fastapi_app.websocket("/ws/test")
async def websocket_test(websocket: WebSocket):
    """Simple WebSocket test endpoint"""
    try:
        await websocket.accept()
        logger.info("Test WebSocket connection accepted")
        
        # Send initial message
        await websocket.send_text(json.dumps({
            "type": "test_connection",
            "message": "WebSocket connection established",
            "timestamp": datetime.utcnow().isoformat()
        }))
        
        # Echo messages back
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)
                
                # Echo back with timestamp
                response = {
                    "type": "echo",
                    "original_message": message,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send_text(json.dumps(response))
                
            except asyncio.TimeoutError:
                # Send ping
                await websocket.send_text(json.dumps({"type": "ping"}))
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON received"
                }))
                
    except WebSocketDisconnect:
        logger.info("Test WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in test WebSocket: {e}")
    finally:
        logger.info("Test WebSocket connection closed")

@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_healthy = False
    redis_stats = {}
    
    if session_manager.redis_enabled and REDIS_AVAILABLE:
        try:
            redis_healthy = await redis_manager.health_check()
            redis_stats = await redis_manager.get_redis_stats()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
    
    return {
        "status": "healthy",
        "version": "2.0.0",
        "active_sessions": len(session_manager.sessions),
        "active_connections": sum(len(conns) for conns in session_manager.active_connections.values()),
        "peer_connections": len(webrtc_manager.peer_connections),
        "redis": {
            "enabled": session_manager.redis_enabled,
            "available": REDIS_AVAILABLE,
            "healthy": redis_healthy,
            "stats": redis_stats
        },
        "timestamp": datetime.utcnow().isoformat()
    }

@fastapi_app.get("/v2/sessions")
async def get_sessions():
    """Get active sessions"""
    sessions = []
    
    # Get sessions from memory
    for session_id, session in session_manager.sessions.items():
        sessions.append({
            "id": session_id,
            "status": session["status"],
            "created_at": session["created_at"].isoformat(),
            "connections": len(session_manager.active_connections.get(session_id, set())),
            "has_peer_connection": session_id in webrtc_manager.peer_connections,
            "metrics": {
                "messages_received": session["metrics"]["messages_received"],
                "errors_count": session["metrics"]["errors_count"],
                "audio_frames_processed": session["metrics"]["audio_frames_processed"],
                "duration": time.time() - session["metrics"]["start_time"]
            }
        })
    
    # Get sessions from Redis if available
    if session_manager.redis_enabled and REDIS_AVAILABLE:
        try:
            redis_session_ids = await redis_manager.list_sessions()
            for session_id in redis_session_ids:
                if session_id not in session_manager.sessions:  # Avoid duplicates
                    session_data = await redis_manager.get_session(session_id)
                    if session_data:
                        sessions.append({
                            "id": session_data.id,
                            "status": session_data.status,
                            "created_at": session_data.created_at,
                            "connections": 0,  # Redis sessions don't have active connections
                            "has_peer_connection": False,
                            "metrics": session_data.metrics
                        })
        except Exception as e:
            logger.error(f"Failed to get sessions from Redis: {e}")
    
    return {
        "sessions": sessions,
        "total": len(sessions)
    }

@fastapi_app.post("/v2/sessions")
async def create_session():
    """Create a new session"""
    session_id = str(uuid.uuid4())
    session = await session_manager.create_session(session_id)
    
    return {
        "session_id": session_id,
        "status": "created",
        "signaling_url": f"/ws/v2/{session_id}"
    }

@fastapi_app.get("/versions")
async def get_versions():
    """Get available API versions"""
    return {
        "versions": {
            "v1": {
                "name": "Voice AI v1",
                "description": "Original WebSocket-based voice AI with basic audio streaming",
                "status": "stable",
                "endpoints": {
                    "websocket": "/ws",
                    "health": "/health"
                }
            },
            "v2": {
                "name": "Voice AI v2",
                "description": "Enhanced WebSocket-based voice AI with session management and improved audio processing",
                "status": "stable",
                "endpoints": {
                    "websocket": "/ws/v2",
                    "health": "/health",
                    "sessions": "/v2/sessions"
                }
            },
            "webrtc": {
                "name": "Voice AI WebRTC",
                "description": "Low-latency voice AI using WebRTC for real-time audio communication",
                "status": "experimental",
                "endpoints": {
                    "websocket": "/ws/v2",
                    "health": "/health",
                    "sessions": "/v2/sessions"
                }
            }
        }
    }

@fastapi_app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

# ============================================================================
# MODAL DEPLOYMENT
# ============================================================================

@app.function(image=image)
@modal.asgi_app()
def run_app():
    """Modal deployment function"""
    return fastapi_app 