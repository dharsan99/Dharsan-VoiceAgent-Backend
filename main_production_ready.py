#!/usr/bin/env python3
"""
Voice Agent Backend - Production Ready with Full TTS Logging
Complete voice agent with STT, LLM, TTS, and Modal cloud storage.
"""

import modal
import os
import json
import time
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from contextlib import contextmanager
from enum import Enum
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the container image with necessary dependencies
image = modal.Image.debian_slim().pip_install([
    "fastapi",
    "websockets",
    "deepgram-sdk",
    "groq",
    "elevenlabs",
    "python-dotenv",
    "uvicorn",
    "pydantic",
    "numpy",
    "modal"
])

# Define the Modal application
app = modal.App("voice-ai-backend-tts-logging")

# Cloud Storage Resources
metrics_volume = modal.Volume.from_name("voice-agent-metrics", create_if_missing=True)
conversation_store = modal.Dict.from_name("voice-conversations", create_if_missing=True)
voice_queue = modal.Queue.from_name("voice-processing", create_if_missing=True)
session_store = modal.Dict.from_name("voice-sessions", create_if_missing=True)

# ==================== CLOUD STORAGE FUNCTIONS ====================

@app.function(
    image=image,
    volumes={"/metrics": metrics_volume},
    timeout=300,
    memory=1024
)
def store_session_metrics(session_data: Dict[str, Any]) -> str:
    """Store session metrics to cloud volume"""
    try:
        session_id = session_data.get("session_id")
        if not session_id:
            raise ValueError("Session ID is required")
        
        # Create timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_file = f"/metrics/session_{session_id}_{timestamp}.json"
        
        # Store metrics with metadata
        metrics_data = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "data": session_data,
            "version": "1.0"
        }
        
        with open(metrics_file, "w") as f:
            json.dump(metrics_data, f, indent=2)
        
        # Commit changes to volume
        metrics_volume.commit()
        
        logger.info(f"Stored metrics for session {session_id} to cloud volume")
        return f"Stored metrics for session {session_id}"
        
    except Exception as e:
        logger.error(f"Error storing session metrics: {e}")
        raise

@app.function(
    image=image,
    volumes={"/metrics": metrics_volume},
    timeout=300,
    memory=1024
)
def get_session_metrics(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session metrics from cloud volume"""
    try:
        import os
        import glob
        
        # Search for session files
        pattern = f"/metrics/session_{session_id}_*.json"
        session_files = glob.glob(pattern)
        
        if not session_files:
            logger.warning(f"No metrics found for session {session_id}")
            return None
        
        # Get the most recent file
        latest_file = max(session_files, key=os.path.getctime)
        
        with open(latest_file, "r") as f:
            metrics_data = json.load(f)
        
        logger.info(f"Retrieved metrics for session {session_id} from cloud volume")
        return metrics_data
        
    except Exception as e:
        logger.error(f"Error retrieving session metrics: {e}")
        return None

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def store_conversation(session_id: str, conversation_data: Dict[str, Any]) -> str:
    """Store conversation data in Modal Dict"""
    try:
        conv_id = f"conv_{int(time.time())}"
        
        if session_id not in conversation_store:
            conversation_store[session_id] = []
        
        conversation_store[session_id].append({
            "conv_id": conv_id,
            "data": conversation_data,
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Stored conversation {conv_id} for session {session_id}")
        return conv_id
        
    except Exception as e:
        logger.error(f"Error storing conversation: {e}")
        raise

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def get_conversation_history(session_id: str) -> List[Dict[str, Any]]:
    """Get conversation history for a session"""
    try:
        return conversation_store.get(session_id, [])
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return []

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def store_session(session_data: Dict[str, Any]) -> str:
    """Store session data in Modal Dict"""
    try:
        session_id = session_data.get("session_id", f"session_{int(time.time())}")
        session_store[session_id] = session_data
        logger.info(f"Stored session {session_id}")
        return session_id
    except Exception as e:
        logger.error(f"Error storing session: {e}")
        raise

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def update_session(session_id: str, updates: Dict[str, Any]) -> bool:
    """Update session data"""
    try:
        if session_id in session_store:
            session_store[session_id].update(updates)
            logger.info(f"Updated session {session_id}")
            return True
        else:
            logger.warning(f"Session {session_id} not found")
            return False
    except Exception as e:
        logger.error(f"Error updating session: {e}")
        return False

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get specific session"""
    try:
        return session_store.get(session_id)
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        return None

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def list_all_sessions() -> List[str]:
    """List all session IDs"""
    try:
        return list(session_store.keys())
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return []

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def queue_voice_processing(processing_data: Dict[str, Any]) -> str:
    """Queue voice processing task"""
    try:
        task_id = f"task_{int(time.time())}"
        voice_queue.put({
            "task_id": task_id,
            "data": processing_data,
            "timestamp": datetime.now().isoformat()
        })
        logger.info(f"Queued processing task {task_id}")
        return task_id
    except Exception as e:
        logger.error(f"Error queuing task: {e}")
        raise

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def get_voice_processing_result(timeout: int = 30) -> Optional[Dict[str, Any]]:
    """Get voice processing result from queue"""
    try:
        result = voice_queue.get(timeout=timeout)
        return result
    except Exception as e:
        logger.error(f"Error getting processing result: {e}")
        return None

@app.function(
    image=image,
    timeout=300,
    memory=1024
)
def get_queue_status() -> Dict[str, Any]:
    """Get queue status"""
    try:
        estimated_items = voice_queue.size()
        return {
            "queue_name": "voice-processing",
            "estimated_items": str(estimated_items),
            "status": "available",
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return {
            "queue_name": "voice-processing",
            "estimated_items": "0",
            "status": "error",
            "last_updated": datetime.now().isoformat()
        }

@app.function(
    image=image,
    volumes={"/metrics": metrics_volume},
    timeout=300,
    memory=1024
)
def get_storage_stats() -> Dict[str, Any]:
    """Get storage statistics"""
    try:
        # Count sessions
        session_count = len(session_store)
        
        # Count conversations
        conv_count = sum(len(convs) for convs in conversation_store.values())
        
        # Count metrics files
        metrics_count = 0
        try:
            import os
            import glob
            metrics_files = glob.glob("/metrics/session_*_*.json")
            metrics_count = len(metrics_files)
        except:
            pass
        
        # Count queue items
        queue_count = len(voice_queue)
        
        return {
            "sessions": session_count,
            "conversations": conv_count,
            "metrics_files": metrics_count,
            "queue_items": str(queue_count),
            "storage_type": "modal",
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting storage stats: {e}")
        return {
            "sessions": 0,
            "conversations": 0,
            "metrics_files": 0,
            "queue_items": "0",
            "storage_type": "error",
            "last_updated": datetime.now().isoformat()
        }

# ==================== MAIN APPLICATION ====================

@app.function(
    image=image,
    volumes={"/metrics": metrics_volume},
    secrets=[
        modal.Secret.from_name("deepgram-secret"),
        modal.Secret.from_name("groq-secret"),
        modal.Secret.from_name("elevenlabs-secret")
    ],
    timeout=3600,
    memory=2048,
    cpu=2.0
)
@modal.asgi_app()
def voice_agent_app():
    """Deploy the voice agent as a Modal ASGI app - Production Ready with TTS Logging"""
    
    # Import FastAPI and other dependencies
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    import os
    from datetime import datetime
    import time
    from typing import Dict, List, Optional, Any
    from contextlib import contextmanager
    from enum import Enum
    
    # Create FastAPI app
    fastapi_app = FastAPI(title="Voice AI Backend - TTS Logging", version="1.0.0")
    
    # Add CORS middleware
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Connection manager
    class ConnectionManager:
        def __init__(self):
            self.active_connections: List[WebSocket] = []
        
        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)
        
        def disconnect(self, websocket: WebSocket):
            self.active_connections.remove(websocket)
        
        async def send_personal_message(self, message: str, websocket: WebSocket):
            await websocket.send_text(message)
        
        async def send_binary_message(self, data: bytes, websocket: WebSocket):
            await websocket.send_bytes(data)
    
    manager = ConnectionManager()
    
    # Conversation manager
    class ConversationManager:
        def __init__(self, max_history: int = 10):
            self.history: List[Dict[str, Any]] = []
            self.max_history = max_history
        
        def add_exchange(self, user_input: str, ai_response: str):
            self.history.append({
                "user": user_input,
                "assistant": ai_response,
                "timestamp": datetime.utcnow()
            })
            
            if len(self.history) > self.max_history:
                self.history.pop(0)
        
        def get_context_summary(self) -> str:
            if not self.history:
                return ""
            
            recent_exchanges = self.history[-3:]
            context_lines = []
            
            for ex in recent_exchanges:
                context_lines.append(f"User: {ex['user']}")
                context_lines.append(f"Assistant: {ex['assistant']}")
            
            return "Previous conversation:\n" + "\n".join(context_lines) + "\n"
        
        def clear_history(self):
            self.history.clear()
    
    # WebSocket handler
    @fastapi_app.websocket("/ws")
    async def websocket_handler(websocket: WebSocket):
        await manager.connect(websocket)
        logger.info("WebSocket connection established")
        
        # Initialize session tracking
        session_id = f"session_{int(time.time())}_{websocket.client.port}"
        logger.info(f"Created session: {session_id}")
        
        # Store session in cloud storage
        try:
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
            from groq import AsyncGroq
            from elevenlabs.client import ElevenLabs
            
            # Initialize clients
            deepgram_client = DeepgramClient(deepgram_api_key)
            groq_client = AsyncGroq(api_key=groq_api_key)
            elevenlabs_client = ElevenLabs(api_key=elevenlabs_api_key)
            
            logger.info("✅ All AI service clients initialized successfully")
            
            # Initialize conversation manager
            conversation_manager = ConversationManager(max_history=10)
            
            # Setup Deepgram connection
            dg_connection = deepgram_client.listen.asynclive.v("1")
            
            async def configure_deepgram():
                options = LiveOptions(
                    model="nova-2",
                    language="en-US",
                    smart_format=True,
                    encoding="linear16",
                    sample_rate=16000,
                    interim_results=True,
                    endpointing=300,
                    punctuate=True,
                    diarize=False,
                    no_delay=True
                )
                await dg_connection.start(options)
                logger.info("✅ Deepgram connection configured and started")
            
            await configure_deepgram()
            
            # Audio receiver - Production ready with proper validation
            async def audio_receiver(ws: WebSocket):
                try:
                    while True:
                        audio_data = await ws.receive_bytes()
                        
                        # Production validation of audio data
                        if audio_data is None:
                            logger.warning("Received None audio data, skipping")
                            continue
                        
                        if not isinstance(audio_data, bytes):
                            logger.warning(f"Received non-bytes audio data: {type(audio_data)}, converting if possible")
                            if hasattr(audio_data, 'tobytes'):
                                audio_data = audio_data.tobytes()
                            else:
                                logger.warning("Cannot convert audio data to bytes, skipping")
                                continue
                        
                        if len(audio_data) == 0:
                            logger.warning("Received empty audio data, skipping")
                            continue
                        
                        # Send to Deepgram if connected
                        if await dg_connection.is_connected():
                            await dg_connection.send(audio_data)
                        else:
                            logger.warning("Deepgram connection not ready, skipping audio data")
                            
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected")
                except Exception as e:
                    logger.error(f"Audio receiver error: {e}")
            
            # Message handler
            async def message_handler(ws: WebSocket):
                try:
                    while True:
                        message = await ws.receive_text()
                        if not message:
                            continue
                        
                        try:
                            data = json.loads(message)
                            
                            if data.get("type") == "ping":
                                await ws.send_text(json.dumps({"type": "pong"}))
                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON message: {e}")
                            continue
                        
                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected")
                except Exception as e:
                    logger.error(f"Message handler error: {e}")
            
            # Production ready transcript handler with comprehensive TTS logging
            def create_transcript_handler(websocket, session_id, session_start_time, conversation_manager):
                async def on_transcript(client, result, **kwargs):
                    """Handle Deepgram transcript events with comprehensive TTS logging"""
                    try:
                        logger.info(f"🎤 Deepgram transcript received: {type(result)}")
                        
                        # Extract transcript from the result object
                        transcript = None
                        is_final = False
                        
                        try:
                            if hasattr(result, 'channel') and hasattr(result.channel, 'alternatives'):
                                transcript = result.channel.alternatives[0].transcript
                                is_final = getattr(result, 'is_final', False)
                        except Exception as e:
                            logger.debug(f"Direct attribute access failed: {e}")
                        
                        # Fallback: Try dictionary access
                        if transcript is None:
                            try:
                                if isinstance(result, dict):
                                    if 'channel' in result and 'alternatives' in result['channel']:
                                        transcript = result['channel']['alternatives'][0]['transcript']
                                        is_final = result.get('is_final', False)
                            except Exception as e:
                                logger.debug(f"Dictionary access failed: {e}")
                        
                        if transcript is None:
                            logger.warning(f"Could not extract transcript from result: {result}")
                            return
                        
                        logger.info(f"📝 Transcript: '{transcript}' (final: {is_final})")
                        
                        if is_final and transcript.strip():
                            # Send transcript to client
                            await manager.send_personal_message(
                                json.dumps({
                                    "type": "transcript",
                                    "text": transcript,
                                    "is_final": True
                                }),
                                websocket
                            )
                            
                            logger.info(f"🤖 Starting LLM processing for: '{transcript}'")
                            
                            # Process with LLM
                            try:
                                messages = [
                                    {"role": "system", "content": "You are a helpful AI assistant. Keep responses concise and natural for voice conversation."},
                                    {"role": "user", "content": transcript}
                                ]
                                
                                logger.info(f"📤 Sending to Groq LLM: {transcript}")
                                llm_start_time = time.time()
                                
                                response = await groq_client.chat.completions.create(
                                    model="llama3-8b-8192",
                                    messages=messages,
                                    max_tokens=150,
                                    temperature=0.7,
                                    stream=True
                                )
                                
                                ai_response = ""
                                async for chunk in response:
                                    if chunk.choices[0].delta.content:
                                        ai_response += chunk.choices[0].delta.content
                                
                                llm_duration = time.time() - llm_start_time
                                logger.info(f"🤖 LLM Response: '{ai_response}' (took {llm_duration:.2f}s)")
                                
                                # Store conversation in cloud storage
                                conversation_data = {
                                    "user_input": transcript,
                                    "ai_response": ai_response,
                                    "processing_time": time.time() - session_start_time,
                                    "llm_duration": llm_duration,
                                    "timestamp": datetime.now().isoformat()
                                }
                                
                                store_conversation.remote(session_id, conversation_data)
                                logger.info(f"💾 Stored conversation in cloud storage")
                                
                                # Send text response to client
                                await manager.send_personal_message(
                                    json.dumps({
                                        "type": "ai_response",
                                        "text": ai_response
                                    }),
                                    websocket
                                )
                                
                                logger.info(f"🔊 Starting TTS generation for: '{ai_response}'")
                                
                                # Generate TTS audio with comprehensive logging
                                try:
                                    tts_start_time = time.time()
                                    logger.info(f"🎵 TTS Request - Text: '{ai_response}'")
                                    logger.info(f"🎵 TTS Request - Voice ID: jBpfuIE2acCO8z3wKNLl (Josh)")
                                    logger.info(f"🎵 TTS Request - Model ID: eleven_monolingual_v1")
                                    
                                    # Get audio generator from ElevenLabs
                                    audio_generator = elevenlabs_client.text_to_speech.stream(
                                        text=ai_response,
                                        voice_id="jBpfuIE2acCO8z3wKNLl",  # Josh voice ID
                                        model_id="eleven_monolingual_v1"
                                    )
                                    
                                    # Collect audio data from generator
                                    audio_chunks = []
                                    for chunk in audio_generator:
                                        audio_chunks.append(chunk)
                                    
                                    # Combine all chunks into single audio data
                                    audio_response = b''.join(audio_chunks)
                                    
                                    tts_duration = time.time() - tts_start_time
                                    audio_size = len(audio_response) if audio_response else 0
                                    
                                    logger.info(f"🎵 TTS Generation Complete!")
                                    logger.info(f"🎵 TTS Duration: {tts_duration:.2f}s")
                                    logger.info(f"🎵 Audio Size: {audio_size} bytes")
                                    logger.info(f"🎵 Audio Type: {type(audio_response)}")
                                    
                                    if audio_response:
                                        logger.info(f"🎵 Sending audio to client (size: {len(audio_response)} bytes)")
                                        
                                        # Send audio in chunks for better frontend compatibility
                                        chunk_size = 8192  # 8KB chunks
                                        audio_length = len(audio_response)
                                        
                                        for i in range(0, audio_length, chunk_size):
                                            chunk = audio_response[i:i + chunk_size]
                                            await manager.send_binary_message(chunk, websocket)
                                            logger.info(f"🎵 Sent audio chunk {i//chunk_size + 1}/{(audio_length + chunk_size - 1)//chunk_size} (size: {len(chunk)} bytes)")
                                        
                                        # Send empty chunk to signal completion
                                        await manager.send_binary_message(b'', websocket)
                                        logger.info(f"🎵 Audio sent successfully to client")
                                        
                                        # Send audio complete message
                                        await manager.send_personal_message(
                                            json.dumps({
                                                "type": "audio_complete",
                                                "text": ai_response,
                                                "audio_size": len(audio_response),
                                                "tts_duration": tts_duration
                                            }),
                                            websocket
                                        )
                                        logger.info(f"🎵 Audio complete message sent")
                                    else:
                                        logger.error(f"🎵 TTS generated empty audio response")
                                    
                                except Exception as e:
                                    logger.error(f"🎵 TTS generation error: {e}")
                                    logger.error(f"🎵 TTS Error Type: {type(e)}")
                                    logger.error(f"🎵 TTS Error Details: {str(e)}")
                                    # Continue without TTS if it fails
                                    await manager.send_personal_message(
                                        json.dumps({
                                            "type": "tts_error",
                                            "message": "TTS generation failed",
                                            "error": str(e)
                                        }),
                                        websocket
                                    )
                                
                            except Exception as e:
                                logger.error(f"🤖 LLM processing error: {e}")
                                logger.error(f"🤖 LLM Error Type: {type(e)}")
                                await manager.send_personal_message(
                                    json.dumps({
                                        "type": "error",
                                        "message": "Sorry, I'm having trouble processing your request."
                                    }),
                                    websocket
                                )
                    except Exception as e:
                        logger.error(f"Transcript handler error: {e}")
                        logger.error(f"Error Type: {type(e)}")
                
                return on_transcript
            
            # Create transcript handler with TTS integration
            transcript_handler = create_transcript_handler(websocket, session_id, session_start_time, conversation_manager)
            
            # Set up transcript handler
            dg_connection.on(LiveTranscriptionEvents.Transcript, transcript_handler)
            logger.info("✅ Deepgram transcript handler configured")
            
            # Start background tasks
            audio_task = asyncio.create_task(audio_receiver(websocket))
            message_task = asyncio.create_task(message_handler(websocket))
            
            logger.info("✅ Background tasks started - ready for voice processing")
            
            # Wait for tasks to complete
            await asyncio.gather(audio_task, message_task)
            
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected")
        except Exception as e:
            logger.error(f"WebSocket handler error: {e}")
        finally:
            # Update session status
            try:
                session_duration = time.time() - session_start_time
                update_session.remote(session_id, {
                    "end_time": datetime.now().isoformat(),
                    "duration": session_duration,
                    "status": "completed"
                })
                
                # Store final metrics
                final_metrics = {
                    "session_id": session_id,
                    "duration": session_duration,
                    "conversation_count": len(conversation_manager.history),
                    "end_time": datetime.now().isoformat()
                }
                store_session_metrics.remote(final_metrics)
                
            except Exception as e:
                logger.warning(f"Failed to update session: {e}")
            
            manager.disconnect(websocket)
    
    # Health check endpoint
    @fastapi_app.get("/health")
    async def health_check():
        return {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    # Cloud storage endpoints
    @fastapi_app.get("/cloud/storage/status")
    async def get_cloud_storage_status():
        """Get cloud storage status and statistics"""
        try:
            stats = get_storage_stats.remote()
            return {
                "status": "available",
                "storage_stats": stats,
                "message": "Modal cloud storage is available and working"
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
    
    @fastapi_app.get("/cloud/sessions")
    async def get_cloud_sessions():
        """Get all sessions from cloud storage"""
        try:
            session_ids = list_all_sessions.remote()
            sessions = []
            
            for session_id in session_ids:
                session_data = get_session.remote(session_id)
                if session_data:
                    # Transform session data to match frontend expectations
                    transformed_session = {
                        "session_id": session_id,
                        "created_at": session_data.get("start_time") or session_data.get("timestamp") or datetime.now().isoformat(),
                        "updated_at": session_data.get("start_time") or session_data.get("timestamp") or datetime.now().isoformat(),
                        "status": session_data.get("status", "active"),
                        "data": session_data,
                        "version": "1.0"
                    }
                    sessions.append(transformed_session)
            
            return {
                "sessions": sessions,
                "count": len(sessions),
                "message": "Sessions retrieved from Modal cloud storage"
            }
        except Exception as e:
            return {
                "sessions": [],
                "count": 0,
                "message": f"Error retrieving sessions: {str(e)}"
            }
    
    @fastapi_app.get("/cloud/conversations/{session_id}")
    async def get_cloud_conversations(session_id: str):
        """Get conversation history for a specific session"""
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
                "message": f"Error retrieving conversations: {str(e)}"
            }
    
    @fastapi_app.get("/cloud/metrics/{session_id}")
    async def get_cloud_metrics(session_id: str):
        """Get metrics for a specific session"""
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
                "message": f"Error retrieving metrics: {str(e)}"
            }
    
    @fastapi_app.get("/cloud/queue/status")
    async def get_queue_status():
        """Get voice processing queue status"""
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
                "status": "error",
                "last_updated": datetime.now().isoformat(),
                "message": f"Error checking queue status: {str(e)}"
            }
    
    @fastapi_app.post("/cloud/queue/process")
    async def process_queue():
        """Process queued voice processing tasks"""
        try:
            # Get a result from the queue
            result = get_voice_processing_result.remote(timeout=5)
            
            if result:
                return {
                    "processed": True,
                    "result": result,
                    "message": "Successfully processed queued task"
                }
            else:
                return {
                    "processed": False,
                    "result": None,
                    "message": "No tasks in queue to process"
                }
        except Exception as e:
            return {
                "processed": False,
                "result": None,
                "message": f"Error processing queue: {str(e)}"
            }
    
    # Root endpoint
    @fastapi_app.get("/")
    async def root():
        return {
            "message": "Voice AI Backend - TTS Logging",
            "version": "1.0.0",
            "status": "running",
            "features": ["STT", "LLM", "TTS", "Cloud Storage", "TTS Logging"],
            "cloud_storage": "enabled"
        }
    
    return fastapi_app

@app.local_entrypoint()
def main():
    """Main entrypoint for deployment"""
    print("🚀 Deploying Voice Agent - TTS Logging...")
    print("✅ Deployment complete!")
    print("🌐 Your app is available at: https://dharsan99--voice-ai-backend-tts-logging-voice-agent-app.modal.run")
    print("🎯 Features: STT (Deepgram) + LLM (Groq) + TTS (ElevenLabs) + Modal Cloud Storage + TTS Logging") 