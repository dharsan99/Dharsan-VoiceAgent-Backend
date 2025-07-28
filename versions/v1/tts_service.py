"""
V1 TTS Service Module
Handles text-to-speech synthesis with multiple providers and fallback support.
"""

import asyncio
import io
import logging
from typing import Optional, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class TTSService:
    """Text-to-Speech service with multiple provider support and fallback"""
    
    def __init__(self, elevenlabs_client=None, azure_speech_key=None):
        self.elevenlabs_client = elevenlabs_client
        self.azure_speech_key = azure_speech_key
        self.voice_id = "21m00Tcm4TlvDq8ikWAM"  # Default ElevenLabs voice
        self.model_id = "eleven_turbo_v2"
        
        # Provider priority order
        self.providers = []
        if self.elevenlabs_client:
            self.providers.append("elevenlabs")
        if self.azure_speech_key:
            self.providers.append("azure")
        self.providers.append("fallback")  # Always available
    
    async def synthesize_speech(self, text: str, websocket: WebSocket, tts_client_queue: asyncio.Queue) -> Optional[bytes]:
        """Synthesize speech from text using available providers"""
        if not text or not text.strip():
            return None
        
        # Try providers in order
        for provider in self.providers:
            try:
                if provider == "elevenlabs":
                    audio_data = await self._synthesize_elevenlabs(text, websocket, tts_client_queue)
                elif provider == "azure":
                    audio_data = await self._synthesize_azure(text, websocket, tts_client_queue)
                elif provider == "fallback":
                    audio_data = await self._synthesize_fallback(text, websocket, tts_client_queue)
                else:
                    continue
                
                if audio_data:
                    logger.info(f"Successfully synthesized speech using {provider}")
                    return audio_data
                    
            except Exception as e:
                logger.warning(f"TTS provider {provider} failed: {e}")
                continue
        
        logger.error("All TTS providers failed")
        return None
    
    async def _synthesize_elevenlabs(self, text: str, websocket: WebSocket, tts_client_queue: asyncio.Queue) -> bytes:
        """Synthesize speech using ElevenLabs"""
        try:
            # Configure voice settings
            voice_settings = {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
            
            # Generate speech
            audio_stream = await self.elevenlabs_client.generate(
                text=text,
                voice_id=self.voice_id,
                model_id=self.model_id,
                voice_settings=voice_settings
            )
            
            # Convert to bytes
            audio_data = b""
            async for chunk in audio_stream:
                audio_data += chunk
            
            return audio_data
            
        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")
            raise e
    
    async def _synthesize_azure(self, text: str, websocket: WebSocket, tts_client_queue: asyncio.Queue) -> bytes:
        """Synthesize speech using Azure Speech Service"""
        try:
            from azure.cognitiveservices.speech import SpeechConfig, SpeechSynthesizer, AudioConfig, ResultReason
            
            # Configure Azure Speech
            speech_config = SpeechConfig(subscription=self.azure_speech_key, region="eastus")
            speech_config.speech_synthesis_voice_name = "en-US-JennyNeural"
            
            # Create synthesizer
            synthesizer = SpeechSynthesizer(speech_config=speech_config)
            
            # Synthesize speech
            result = await asyncio.get_event_loop().run_in_executor(
                None, synthesizer.speak_text_sync, text
            )
            
            if result.reason == ResultReason.SynthesizingAudioCompleted:
                # Get audio data
                audio_data = result.audio_data
                return audio_data
            else:
                logger.error(f"Azure TTS failed: {result.reason}")
                raise Exception(f"Azure TTS failed: {result.reason}")
                
        except Exception as e:
            logger.error(f"Azure TTS error: {e}")
            raise e
    
    async def _synthesize_fallback(self, text: str, websocket: WebSocket, tts_client_queue: asyncio.Queue) -> bytes:
        """Fallback TTS using basic text-to-speech (placeholder)"""
        try:
            # This is a placeholder implementation
            # In a real implementation, you might use:
            # - gTTS (Google Text-to-Speech)
            # - pyttsx3 (offline TTS)
            # - espeak
            # - or other open-source TTS engines
            
            logger.warning("Using fallback TTS - this is a placeholder implementation")
            
            # For now, return empty audio data
            # In a real implementation, you would generate actual audio
            return b""
            
        except Exception as e:
            logger.error(f"Fallback TTS error: {e}")
            raise e
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about available TTS providers"""
        return {
            "available_providers": self.providers,
            "primary_provider": self.providers[0] if self.providers else None,
            "elevenlabs_configured": self.elevenlabs_client is not None,
            "azure_configured": self.azure_speech_key is not None,
            "voice_id": self.voice_id,
            "model_id": self.model_id
        } 