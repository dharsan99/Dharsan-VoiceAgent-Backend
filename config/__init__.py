# config/__init__.py
# Configuration package for Voice AI Backend

from .settings import settings, get_deepgram_config, get_groq_config, get_elevenlabs_config

__all__ = [
    "settings",
    "get_deepgram_config", 
    "get_groq_config",
    "get_elevenlabs_config"
] 