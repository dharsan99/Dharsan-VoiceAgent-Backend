# main_with_storage.py
# Dharsan Voice Agent Backend - Modal/FastAPI Implementation with Full Storage

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
    # Import modal_storage functions directly
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

# Import AI services
try:
    from deepgram import Deepgram
    from groq import Groq
    from elevenlabs import ElevenLabs
    AI_SERVICES_AVAILABLE = True
    logger.info("AI services imported successfully")
except ImportError as e:
    AI_SERVICES_AVAILABLE = False
    logger.error(f"Failed to import AI services: {e}")

# FastAPI app setup
fastapi_app = FastAPI(title="Dharsan Voice Agent API", version="2.0.0")

# CORS middleware
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modal app setup
app = modal.App("voice-agent-app-with-storage")

# Modal secrets
@app.function(secrets=[modal.Secret.from_name("voice-agent-secrets")])
def get_secrets():
    return {
        "deepgram_api_key": os.environ.get("DEEPGRAM_API_KEY"),
        "groq_api_key": os.environ.get("GROQ_API_KEY"),
        "elevenlabs_api_key": os.environ.get("ELEVENLABS_API_KEY"),
        "azure_speech_key": os.environ.get("AZURE_SPEECH_KEY"),
    }

# Metrics database
class MetricsDatabase:
    def __init__(self, db_path: str = "v1_metrics.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create sessions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                duration_seconds REAL,
                status TEXT DEFAULT 'active'
            )
        ''')
        
        # Create conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                user_input TEXT,
                ai_response TEXT,
                processing_time REAL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions (session_id)
            )
        ''')
        
        # Create network_metrics table
        cursor.execute('''
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
        ''')
        
        conn.commit()
        conn.close()
    
    def create_session(self, session_id: str) -> bool:
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO sessions (session_id, start_time, status) VALUES (?, CURRENT_TIMESTAMP, 'active')",
                (session_id,)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False
    
    def end_session(self, session_id: str, duration_seconds: float = None) -> bool:
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if duration_seconds is None:
                cursor.execute(
                    "UPDATE sessions SET end_time = CURRENT_TIMESTAMP, status = 'ended' WHERE session_id = ?",
                    (session_id,)
                )
            else:
                cursor.execute(
                    "UPDATE sessions SET end_time = CURRENT_TIMESTAMP, duration_seconds = ?, status = 'ended' WHERE session_id = ?",
                    (duration_seconds, session_id)
                )
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to end session: {e}")
            return False
    
    def record_conversation_exchange(self, session_id: str, user_input: str, 
                                   ai_response: str, processing_time: float) -> bool:
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversations (session_id, user_input, ai_response, processing_time) VALUES (?, ?, ?, ?)",
                (session_id, user_input, ai_response, processing_time)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to record conversation: {e}")
            return False
    
    def record_network_metrics(self, session_id: str, latency: float, jitter: float, 
                             packet_loss: float, buffer_size: int) -> bool:
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO network_metrics (session_id, latency, jitter, packet_loss, buffer_size) VALUES (?, ?, ?, ?, ?)",
                (session_id, latency, jitter, packet_loss, buffer_size)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"Failed to record network metrics: {e}")
            return False
    
    def get_session_metrics(self, session_id: str) -> Dict:
        try:
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get session info
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            session = cursor.fetchone()
            
            if not session:
                return None
            
            # Get conversation count
            cursor.execute("SELECT COUNT(*) FROM conversations WHERE session_id = ?", (session_id,))
            conversation_count = cursor.fetchone()[0]
            
            # Get average processing time
            cursor.execute("SELECT AVG(processing_time) FROM conversations WHERE session_id = ?", (session_id,))
            avg_processing_time = cursor.fetchone()[0] or 0
            
            # Get latest network metrics
            cursor.execute(
                "SELECT latency, jitter, packet_loss, buffer_size FROM network_metrics WHERE session_id = ? ORDER BY timestamp DESC LIMIT 1",
                (session_id,)
            )
            network_metrics = cursor.fetchone()
            
            conn.close()
            
            return {
                "session_id": session_id,
                "start_time": session[1],
                "end_time": session[2],
                "duration_seconds": session[3],
                "status": session[4],
                "conversation_count": conversation_count,
                "avg_processing_time": avg_processing_time,
                "latest_network_metrics": {
                    "latency": network_metrics[0] if network_metrics else 0,
                    "jitter": network_metrics[1] if network_metrics else 0,
                    "packet_loss": network_metrics[2] if network_metrics else 0,
                    "buffer_size": network_metrics[3] if network_metrics else 0
                } if network_metrics else None
            }
        except Exception as e:
            logger.error(f"Failed to get session metrics: {e}")
            return None

# Global metrics database instance
metrics_db = MetricsDatabase()

@fastapi_app.websocket("/ws")
async def websocket_handler(websocket: WebSocket):
    await websocket.accept()
    session_id = f"session_{int(time.time())}_{os.getpid()}"
    session_start_time = time.time()
    
    # Create session in metrics database
    metrics_db.create_session(session_id)
    logger.info(f"Created session: {session_id}")
    
    # Store session in cloud storage if available
    if MODAL_STORAGE_AVAILABLE:
        try:
            store_session({
                "session_id": session_id,
                "start_time": datetime.now().isoformat(),
                "status": "active"
            })
            logger.info(f"Stored session {session_id} in cloud storage")
        except Exception as e:
            logger.error(f"Failed to store session in cloud storage: {e}")
    
    try:
        # Get API keys from Modal secrets
        secrets = get_secrets.remote()
        deepgram_api_key = secrets["deepgram_api_key"]
        groq_api_key = secrets["groq_api_key"]
        elevenlabs_api_key = secrets["elevenlabs_api_key"]
        
        if not all([deepgram_api_key, groq_api_key, elevenlabs_api_key]):
            logger.error("Missing required API keys")
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Missing API keys. Please check configuration."
            }))
            return
        
        # Initialize AI clients
        deepgram_client = Deepgram(deepgram_api_key)
        groq_client = Groq(api_key=groq_api_key)
        elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
        
        # WebSocket connection for Deepgram
        dg_connection = None
        
        async def configure_deepgram():
            nonlocal dg_connection
            try:
                dg_connection = await deepgram_client.listen.live({
                    "language": "en-US",
                    "smart_format": True,
                    "model": "nova-2",
                    "interim_results": True,
                    "punctuate": True,
                    "utterances": True,
                    "vad_turnoff": 500,
                })
                logger.info("Deepgram connection configured successfully")
            except Exception as e:
                logger.error(f"Failed to configure Deepgram: {e}")
                raise
        
        async def audio_receiver(ws: WebSocket):
            """Receives audio from client and sends to Deepgram"""
            try:
                while True:
                    audio_data = await ws.receive_bytes()
                    if dg_connection and dg_connection.is_connected():
                        await dg_connection.send(audio_data)
            except WebSocketDisconnect:
                logger.info("Audio receiver: Client disconnected")
            except Exception as e:
                logger.error(f"Audio receiver error: {e}")
        
        async def deepgram_keepalive():
            """Sends keepalive messages to Deepgram"""
            try:
                while True:
                    if dg_connection and dg_connection.is_connected():
                        await dg_connection.keepalive()
                    await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"Deepgram keepalive error: {e}")
        
        async def connection_monitor():
            """Monitors connection health"""
            try:
                while True:
                    if dg_connection and not dg_connection.is_connected():
                        logger.warning("Deepgram connection lost, attempting to reconnect...")
                        await configure_deepgram()
                    await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Connection monitor error: {e}")
        
        async def message_handler(ws: WebSocket):
            """Handles messages from client"""
            try:
                while True:
                    message = await ws.receive_text()
                    data = json.loads(message)
                    
                    if data.get("type") == "session_info":
                        logger.info(f"Received session info: {data}")
                    elif data.get("type") == "ping":
                        await ws.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
            except WebSocketDisconnect:
                logger.info("Message handler: Client disconnected")
            except Exception as e:
                logger.error(f"Message handler error: {e}")
        
        async def on_transcript(self, result, **kwargs):
            """Handles Deepgram transcript results"""
            try:
                if result.is_final:
                    transcript_text = result.channel.alternatives[0].transcript
                    logger.info(f"🎤 Deepgram transcript received: {type(result)}")
                    logger.info(f"📝 Transcript: '{transcript_text}' (final: {result.is_final})")
                    
                    # Send transcript to client
                    await websocket.send_text(json.dumps({
                        "type": "transcript",
                        "text": transcript_text,
                        "is_final": True
                    }))
                    
                    # Send to LLM processing queue
                    await stt_llm_queue.put(transcript_text)
                else:
                    # Interim transcript
                    transcript_text = result.channel.alternatives[0].transcript
                    if transcript_text.strip():
                        await websocket.send_text(json.dumps({
                            "type": "transcript",
                            "text": transcript_text,
                            "is_final": False
                        }))
            except Exception as e:
                logger.error(f"Transcript handler error: {e}")
        
        # Set up Deepgram message handler
        if dg_connection:
            dg_connection.on("transcript", on_transcript)
        
        async def call_groq_api(messages):
            """Calls Groq API for LLM response"""
            try:
                start_time = time.time()
                logger.info(f"🤖 Starting LLM processing for: '{messages[-1]['content']}'")
                logger.info(f"📤 Sending to Groq LLM: {messages[-1]['content']}")
                
                response = groq_client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=messages,
                    temperature=0.7,
                    max_tokens=150,
                    stream=False
                )
                
                ai_response = response.choices[0].message.content
                processing_time = time.time() - start_time
                
                logger.info(f"🤖 LLM Response: '{ai_response}' (took {processing_time:.2f}s)")
                
                # Store conversation in cloud storage if available
                if MODAL_STORAGE_AVAILABLE:
                    try:
                        store_conversation(session_id, {
                            "user_input": messages[-1]['content'],
                            "ai_response": ai_response,
                            "processing_time": processing_time,
                            "timestamp": datetime.now().isoformat()
                        })
                        logger.info(f"💾 Stored conversation in cloud storage")
                    except Exception as e:
                        logger.error(f"Failed to store conversation: {e}")
                
                # Record in local metrics database
                metrics_db.record_conversation_exchange(
                    session_id, messages[-1]['content'], ai_response, processing_time
                )
                
                return ai_response
            except Exception as e:
                logger.error(f"Groq API error: {e}")
                return "I apologize, but I'm experiencing technical difficulties. Please try again."
        
        async def llm_to_tts_producer():
            """Processes transcripts through LLM and queues for TTS"""
            try:
                while True:
                    transcript = await stt_llm_queue.get()
                    
                    # Prepare messages for LLM
                    messages = [
                        {"role": "system", "content": "You are a helpful AI assistant. Keep responses concise and friendly."},
                        {"role": "user", "content": transcript}
                    ]
                    
                    # Get AI response
                    ai_response = await call_groq_api(messages)
                    
                    # Send AI response to client
                    await websocket.send_text(json.dumps({
                        "type": "ai_response",
                        "text": ai_response
                    }))
                    
                    # Queue for TTS
                    await llm_tts_queue.put(ai_response)
            except Exception as e:
                logger.error(f"LLM to TTS producer error: {e}")
        
        async def tts_to_client_producer():
            """Generates TTS audio from text and queues for client"""
            try:
                while True:
                    full_text = await llm_tts_queue.get()
                    
                    logger.info(f"🔊 Starting TTS generation for: '{full_text}'")
                    logger.info(f"🎵 TTS Request - Text: '{full_text}'")
                    logger.info(f"🎵 TTS Request - Voice: Josh")
                    logger.info(f"🎵 TTS Request - Model: eleven_monolingual_v1")
                    
                    try:
                        # Use ElevenLabs streaming with correct parameters
                        audio_stream = elevenlabs_client.text_to_speech.stream(
                            text=full_text,
                            voice_id="21m00Tcm4TlvDq8ikWAM",  # Josh voice
                            model_id="eleven_monolingual_v1",
                            output_format="mp3_44100_128"
                        )
                        
                        logger.info("🎵 TTS stream created successfully")
                        
                        # Process audio stream
                        for audio_chunk in audio_stream:
                            logger.info(f"🎵 TTS: Generated audio chunk of size {len(audio_chunk)} bytes")
                            await tts_client_queue.put(audio_chunk)
                        
                        logger.info("🎵 TTS generation completed successfully")
                        
                    except Exception as tts_error:
                        logger.error(f"🎵 TTS generation error: {tts_error}")
                        logger.error(f"🎵 TTS Error Type: {type(tts_error)}")
                        logger.error(f"🎵 TTS Error Details: {tts_error}")
                        
                        # Send error message to frontend
                        await websocket.send_text(json.dumps({
                            "type": "tts_error",
                            "message": f"TTS service error: {str(tts_error)}",
                            "error_details": {
                                "error_type": "tts_service_error",
                                "timestamp": datetime.now().isoformat()
                            }
                        }))
                    
                    # Signal end of audio
                    logger.info("🎵 TTS: Signaling end of audio with None")
                    await tts_client_queue.put(None)
                    
            except Exception as e:
                logger.error(f"TTS producer error: {e}")
        
        async def audio_sender(ws: WebSocket):
            """Sends synthesized audio from queue back to client"""
            try:
                logger.info("🎵 Audio sender: Starting audio sender loop")
                while True:
                    audio_chunk = await tts_client_queue.get()
                    
                    if audio_chunk is None:
                        logger.info("🎵 Audio sender: Received None signal, continuing...")
                        continue
                    
                    logger.info(f"🎵 Audio sender: Sending chunk of size {len(audio_chunk)} bytes")
                    await ws.send_bytes(audio_chunk)
                    logger.info(f"🎵 Audio sender: Successfully sent chunk")
            except WebSocketDisconnect:
                logger.info("🎵 Audio sender: Client disconnected")
            except Exception as e:
                logger.error(f"🎵 Audio sender error: {e}")
                logger.error(f"🎵 Audio sender error traceback: {traceback.format_exc()}")
        
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
                update_session(session_id, {
                    "end_time": datetime.now().isoformat(),
                    "duration_seconds": session_duration,
                    "status": "ended"
                })
                logger.info(f"Updated session {session_id} in cloud storage")
            except Exception as e:
                logger.error(f"Failed to update session in cloud storage: {e}")

@fastapi_app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "deepgram": "available",
            "groq": "available", 
            "elevenlabs": "available",
            "modal_storage": MODAL_STORAGE_AVAILABLE
        }
    }

@fastapi_app.get("/")
async def root():
    return {
        "message": "Dharsan Voice Agent API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.function()
@modal.asgi_app()
def run_app():
    return fastapi_app 