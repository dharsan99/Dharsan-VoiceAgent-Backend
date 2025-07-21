# config/settings.py
# Configuration management for Voice AI Backend

import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings and configuration"""
    
    # API Keys (loaded from environment variables)
    deepgram_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    
    # Deepgram Configuration
    deepgram_model: str = "nova-2"
    deepgram_language: str = "en-US"
    deepgram_sample_rate: int = 16000
    deepgram_endpointing: int = 300  # milliseconds
    deepgram_interim_results: bool = False
    
    # Groq Configuration
    groq_model: str = "llama3-8b-8192"
    groq_temperature: float = 0.7
    groq_max_tokens: int = 150
    
    # ElevenLabs Configuration
    elevenlabs_voice: str = "Rachel"
    elevenlabs_model: str = "eleven_turbo_v2"
    
    # Conversation Settings
    max_conversation_history: int = 10
    context_exchanges: int = 3  # Number of recent exchanges to include in context
    
    # WebSocket Settings
    websocket_ping_interval: int = 20
    websocket_ping_timeout: int = 20
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def validate_api_keys(self) -> bool:
        """Validate that all required API keys are present"""
        required_keys = [
            self.deepgram_api_key,
            self.groq_api_key,
            self.elevenlabs_api_key
        ]
        return all(key is not None and key.strip() for key in required_keys)
    
    def get_missing_keys(self) -> list:
        """Get list of missing API keys"""
        missing = []
        if not self.deepgram_api_key:
            missing.append("DEEPGRAM_API_KEY")
        if not self.groq_api_key:
            missing.append("GROQ_API_KEY")
        if not self.elevenlabs_api_key:
            missing.append("ELEVENLABS_API_KEY")
        return missing

# Global settings instance
settings = Settings()

# Environment-specific configurations
def get_deepgram_config():
    """Get Deepgram configuration"""
    return {
        "model": settings.deepgram_model,
        "language": settings.deepgram_language,
        "smart_format": True,
        "encoding": "linear16",
        "sample_rate": settings.deepgram_sample_rate,
        "interim_results": settings.deepgram_interim_results,
        "endpointing": settings.deepgram_endpointing,
        "punctuate": True,
        "diarize": False,
        "utterances": False
    }

def get_groq_config():
    """Get Groq configuration"""
    return {
        "model": settings.groq_model,
        "temperature": settings.groq_temperature,
        "max_tokens": settings.groq_max_tokens,
        "stream": True
    }

def get_elevenlabs_config():
    """Get ElevenLabs configuration"""
    return {
        "voice": settings.elevenlabs_voice,
        "model": settings.elevenlabs_model,
        "stream": True
    } 