"""
V3 Configuration Module
Contains configuration classes for V3 voice agent with WebRTC support.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Import V2 configs
from ..v2.config import VoiceConfig, VoiceProvider, AIConfig, STTConfig

class WebRTCMode(str, Enum):
    """WebRTC connection modes"""
    AUDIO_ONLY = "audio_only"
    AUDIO_VIDEO = "audio_video"
    DATA_CHANNEL = "data_channel"

@dataclass
class WebRTCConfig:
    """WebRTC configuration settings"""
    mode: WebRTCMode = WebRTCMode.AUDIO_ONLY
    ice_servers: list = None
    audio_codec: str = "opus"
    sample_rate: int = 48000
    channels: int = 1
    enable_dtls: bool = True
    enable_srtp: bool = True
    
    def __post_init__(self):
        if self.ice_servers is None:
            self.ice_servers = [
                {"urls": "stun:stun.l.google.com:19302"},
                {"urls": "stun:stun1.l.google.com:19302"}
            ]

@dataclass
class V3Config:
    """V3 complete configuration"""
    voice: VoiceConfig = None
    ai: AIConfig = None
    stt: STTConfig = None
    webrtc: WebRTCConfig = None
    
    def __post_init__(self):
        if self.voice is None:
            self.voice = VoiceConfig()
        if self.ai is None:
            self.ai = AIConfig()
        if self.stt is None:
            self.stt = STTConfig()
        if self.webrtc is None:
            self.webrtc = WebRTCConfig() 