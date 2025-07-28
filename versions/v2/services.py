"""
V2 Services Module
Contains modular service classes for V2 voice agent.
"""

import asyncio
import os
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from fastapi import WebSocket

from core.base import ConnectionStatus, ProcessingStatus, SessionInfo, logger
from .config import VoiceConfig, VoiceProvider, AIConfig, STTConfig

class VoiceService:
    """Voice synthesis service with multiple provider support"""
    
    def __init__(self, config: VoiceConfig = None):
        self.config = config or VoiceConfig()
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize available voice providers"""
        self.providers = {}
        
        # Initialize ElevenLabs
        try:
            from elevenlabs.client import ElevenLabs
            elevenlabs_api_key = os.environ.get("ELEVENLABS_API_KEY")
            if elevenlabs_api_key:
                self.providers[VoiceProvider.ELEVENLABS] = ElevenLabs(api_key=elevenlabs_api_key)
                logger.info("ElevenLabs provider initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize ElevenLabs: {e}")
        
        # Initialize Azure (if configured)
        azure_speech_key = os.environ.get("AZURE_SPEECH_KEY")
        if azure_speech_key:
            self.providers[VoiceProvider.AZURE] = azure_speech_key
            logger.info("Azure Speech provider initialized")
        
        # Fallback is always available
        self.providers[VoiceProvider.FALLBACK] = None
        logger.info("Fallback TTS provider available")
    
    async def synthesize_speech(self, text: str, websocket: WebSocket) -> Optional[bytes]:
        """Synthesize speech from text using available providers"""
        if not text or not text.strip():
            return None
        
        # Try providers in order of preference
        providers_to_try = [
            self.config.provider,
            VoiceProvider.ELEVENLABS,
            VoiceProvider.AZURE,
            VoiceProvider.FALLBACK
        ]
        
        for provider in providers_to_try:
            if provider not in self.providers:
                continue
                
            try:
                if provider == VoiceProvider.ELEVENLABS:
                    audio_data = await self._synthesize_elevenlabs(text)
                elif provider == VoiceProvider.AZURE:
                    audio_data = await self._synthesize_azure(text)
                elif provider == VoiceProvider.FALLBACK:
                    audio_data = await self._synthesize_fallback(text)
                else:
                    continue
                
                if audio_data:
                    logger.info(f"Successfully synthesized speech using {provider.value}")
                    return audio_data
                    
            except Exception as e:
                logger.warning(f"TTS provider {provider.value} failed: {e}")
                continue
        
        logger.error("All TTS providers failed")
        return None
    
    async def _synthesize_elevenlabs(self, text: str) -> bytes:
        """Synthesize speech using ElevenLabs"""
        if VoiceProvider.ELEVENLABS not in self.providers:
            raise Exception("ElevenLabs not available")
        
        client = self.providers[VoiceProvider.ELEVENLABS]
        
        voice_settings = {
            "stability": self.config.stability,
            "similarity_boost": self.config.similarity_boost,
            "style": self.config.style,
            "use_speaker_boost": self.config.use_speaker_boost
        }
        
        audio_stream = await client.generate(
            text=text,
            voice_id=self.config.voice_id,
            model_id=self.config.model_id,
            voice_settings=voice_settings
        )
        
        audio_data = b""
        async for chunk in audio_stream:
            audio_data += chunk
        
        return audio_data
    
    async def _synthesize_azure(self, text: str) -> bytes:
        """Synthesize speech using Azure Speech Service"""
        if VoiceProvider.AZURE not in self.providers:
            raise Exception("Azure Speech not available")
        
        try:
            from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, ResultReason
            
            speech_config = SpeechConfig(subscription=self.providers[VoiceProvider.AZURE], region="eastus")
            speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            
            synthesizer = SpeechSynthesizer(speech_config=speech_config)
            
            result = await asyncio.get_event_loop().run_in_executor(
                None, synthesizer.speak_text_sync, text
            )
            
            if result.reason == ResultReason.SynthesizingAudioCompleted:
                return result.audio_data
            else:
                raise Exception(f"Azure TTS failed: {result.reason}")
                
        except Exception as e:
            logger.error(f"Azure TTS error: {e}")
            raise e
    
    async def _synthesize_fallback(self, text: str) -> bytes:
        """Fallback TTS implementation"""
        logger.warning("Using fallback TTS - this is a placeholder implementation")
        # Placeholder - return empty audio
        return b""
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about available TTS providers"""
        return {
            "available_providers": [p.value for p in self.providers.keys()],
            "primary_provider": self.config.provider.value,
            "voice_id": self.config.voice_id,
            "model_id": self.config.model_id,
            "sample_rate": self.config.sample_rate
        }

class AIService:
    """AI service for generating responses"""
    
    def __init__(self, config: AIConfig = None):
        self.config = config or AIConfig()
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize AI client"""
        try:
            from groq import AsyncGroq
            groq_api_key = os.environ.get("GROQ_API_KEY")
            if not groq_api_key:
                raise Exception("GROQ_API_KEY not found")
            
            self.client = AsyncGroq(api_key=groq_api_key)
            logger.info("Groq AI client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize AI client: {e}")
            self.client = None
    
    async def generate_response(self, user_input: str, conversation_history: List[Dict] = None) -> str:
        """Generate AI response"""
        if not self.client:
            return "I'm sorry, the AI service is currently unavailable."
        
        try:
            # Build messages
            messages = []
            
            # Add system prompt
            messages.append({
                "role": "system",
                "content": self.config.system_prompt
            })
            
            # Add conversation history
            if conversation_history:
                messages.extend(conversation_history[-6:])  # Last 6 exchanges
            
            # Add current user input
            messages.append({
                "role": "user",
                "content": user_input
            })
            
            # Generate response
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=False
            )
            
            if response.choices and len(response.choices) > 0:
                return response.choices[0].message.content
            else:
                return "I'm sorry, I couldn't generate a response at the moment."
                
        except Exception as e:
            logger.error(f"AI service error: {e}")
            return "I apologize, but I'm experiencing technical difficulties. Please try again."

class STTService:
    """Speech-to-Text service"""
    
    def __init__(self, config: STTConfig = None):
        self.config = config or STTConfig()
        self._initialize_client()
        self.connection = None
    
    def _initialize_client(self):
        """Initialize STT client"""
        try:
            from deepgram import DeepgramClient, LiveOptions
            deepgram_api_key = os.environ.get("DEEPGRAM_API_KEY")
            if not deepgram_api_key:
                raise Exception("DEEPGRAM_API_KEY not found")
            
            self.client = DeepgramClient(deepgram_api_key)
            logger.info("Deepgram STT client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize STT client: {e}")
            self.client = None
    
    async def start_transcription(self, websocket: WebSocket, transcript_callback: Callable):
        """Start transcription service"""
        if not self.client:
            return None
        
        try:
            # Create connection
            self.connection = self.client.listen.asynclive.v("1")
            
            # Configure options
            options = LiveOptions(
                model=self.config.model,
                language=self.config.language,
                smart_format=True,
                encoding=self.config.encoding,
                sample_rate=self.config.sample_rate,
                interim_results=self.config.interim_results,
                endpointing=self.config.endpointing,
                punctuate=self.config.punctuate,
                diarize=self.config.diarize
            )
            
            # Start connection
            await self.connection.start(options)
            
            # Set up event handler
            from deepgram import LiveTranscriptionEvents
            self.connection.on(LiveTranscriptionEvents.Transcript, transcript_callback)
            
            logger.info("STT transcription started")
            return self.connection
            
        except Exception as e:
            logger.error(f"Failed to start transcription: {e}")
            return None
    
    async def send_audio(self, audio_data: bytes):
        """Send audio data to STT service"""
        if self.connection:
            await self.connection.send(audio_data)
    
    async def stop_transcription(self):
        """Stop transcription service"""
        if self.connection:
            await self.connection.finish()
            self.connection = None
            logger.info("STT transcription stopped")

class SessionManager:
    """Manages voice agent sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, SessionInfo] = {}
        self.voice_service = VoiceService()
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
        self.sessions[session_id] = session
        logger.info(f"Created session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """Get session by ID"""
        return self.sessions.get(session_id)
    
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
        """Close a session"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.connection_status = ConnectionStatus.DISCONNECTED
            session.total_duration = (datetime.utcnow() - session.start_time).total_seconds()
            logger.info(f"Closed session: {session_id}")
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions"""
        return len([s for s in self.sessions.values() 
                   if s.connection_status == ConnectionStatus.CONNECTED])
    
    def get_all_sessions(self) -> List[SessionInfo]:
        """Get all sessions"""
        return list(self.sessions.values()) 