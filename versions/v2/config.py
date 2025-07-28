"""
V2 Configuration Module
Contains configuration classes for V2 voice agent.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

class VoiceProvider(str, Enum):
    """Available voice synthesis providers"""
    ELEVENLABS = "elevenlabs"
    AZURE = "azure"
    FALLBACK = "fallback"

@dataclass
class VoiceConfig:
    """Voice configuration settings"""
    provider: VoiceProvider = VoiceProvider.ELEVENLABS
    voice_id: str = "21m00Tcm4TlvDq8ikWAM"
    model_id: str = "eleven_turbo_v2"
    sample_rate: int = 44100
    output_format: str = "mp3_44100_128"
    stability: float = 0.5
    similarity_boost: float = 0.75
    style: float = 0.0
    use_speaker_boost: bool = True

@dataclass
class AIConfig:
    """AI service configuration"""
    model: str = "llama3-8b-8192"
    temperature: float = 0.7
    max_tokens: int = 150
    system_prompt: str = "You are a helpful AI assistant. Keep responses concise and natural for voice conversation."

@dataclass
class STTConfig:
    """Speech-to-Text configuration"""
    model: str = "nova-2"
    language: str = "en-US"
    sample_rate: int = 16000
    encoding: str = "linear16"
    interim_results: bool = True
    endpointing: int = 300
    punctuate: bool = True
    diarize: bool = False 