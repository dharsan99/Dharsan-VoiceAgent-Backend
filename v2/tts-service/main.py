import subprocess
import tempfile
import os
import time
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import REGISTRY
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Prometheus metrics
synthesis_requests = Counter('tts_synthesis_requests_total', 'Total synthesis requests')
synthesis_errors = Counter('tts_synthesis_errors_total', 'Total synthesis errors')
synthesis_duration = Histogram('tts_synthesis_duration_seconds', 'Synthesis duration in seconds')
text_length = Histogram('tts_text_length_chars', 'Text length in characters')

app = FastAPI(
    title="TTS Service",
    description="Self-hosted Text-to-Speech service using Piper",
    version="1.0.0"
)

class SynthesisRequest(BaseModel):
    text: str
    voice: Optional[str] = "en_US-lessac-high"
    speed: Optional[float] = 1.0
    format: Optional[str] = "wav"

class SynthesisResponse(BaseModel):
    audio_size: int
    duration: float
    voice: str
    format: str
    processing_time: float

class HealthResponse(BaseModel):
    status: str
    voice_loaded: bool
    voice_size: str
    uptime: float

# Global variables
start_time = time.time()
piper_binary = "/app/piper/piper"
voice_model = "/app/en_US-lessac-high.onnx"
voice_config = "/app/en_US-lessac-high.onnx.json"

def check_voice_exists() -> bool:
    """Check if the voice model exists"""
    return os.path.exists(voice_model) and os.path.exists(voice_config)

def get_voice_size() -> str:
    """Get the size of the loaded voice model"""
    if os.path.exists(voice_model):
        size_bytes = os.path.getsize(voice_model)
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.1f}MB"
    return "Unknown"

def preprocess_text(text: str) -> str:
    """Preprocess text for TTS synthesis"""
    # Remove extra whitespace
    text = " ".join(text.split())
    
    # Basic text cleaning
    text = text.strip()
    
    # Limit text length to prevent abuse
    if len(text) > 1000:
        text = text[:1000] + "..."
    
    return text

@app.get("/health")
async def health_check() -> HealthResponse:
    """Health check endpoint"""
    uptime = time.time() - start_time
    voice_loaded = check_voice_exists()
    
    return HealthResponse(
        status="healthy" if voice_loaded else "unhealthy",
        voice_loaded=voice_loaded,
        voice_size=get_voice_size(),
        uptime=uptime
    )

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

@app.post("/synthesize", response_model=SynthesisResponse)
async def synthesize_speech(
    request: SynthesisRequest
) -> SynthesisResponse:
    """Synthesize speech using Piper"""
    
    synthesis_requests.inc()
    start_time = time.time()
    
    try:
        # Validate input
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Preprocess text
        text = preprocess_text(request.text)
        text_length.observe(len(text))
        
        # Validate voice
        if not check_voice_exists():
            raise HTTPException(status_code=500, detail="Voice model not available")
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode='w') as text_file, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            
            # Write text to file
            text_file.write(text)
            text_file.flush()
            
            # Execute Piper
            command = [
                piper_binary,
                "--model", voice_model,
                "--config", voice_config,
                "--output_file", audio_file.name,
                "--output_raw",  # Output raw audio
                "--length_scale", str(1.0 / request.speed),  # Speed control
                text_file.name
            ]
            
            logger.info("Starting synthesis", 
                       text_length=len(text),
                       voice=request.voice,
                       speed=request.speed)
            
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                timeout=30  # 30 second timeout
            )
            
            # Clean up text file
            os.unlink(text_file.name)
            
            if result.returncode != 0:
                logger.error("Piper synthesis failed", 
                           returncode=result.returncode,
                           stderr=result.stderr)
                synthesis_errors.inc()
                raise HTTPException(
                    status_code=500, 
                    detail=f"Synthesis failed: {result.stderr}"
                )
            
            # Read generated audio
            audio_file.flush()
            with open(audio_file.name, 'rb') as f:
                audio_data = f.read()
            
            # Clean up audio file
            os.unlink(audio_file.name)
            
            # Calculate duration (approximate)
            # Assuming 16kHz sample rate, 16-bit mono
            duration = len(audio_data) / (16000 * 2)  # 2 bytes per sample
            
            processing_time = time.time() - start_time
            synthesis_duration.observe(processing_time)
            
            logger.info("Synthesis completed", 
                       audio_size=len(audio_data),
                       duration=duration,
                       processing_time=processing_time)
            
            return SynthesisResponse(
                audio_size=len(audio_data),
                duration=duration,
                voice=request.voice,
                format=request.format,
                processing_time=processing_time
            )
            
    except subprocess.TimeoutExpired:
        synthesis_errors.inc()
        logger.error("Synthesis timeout")
        raise HTTPException(status_code=408, detail="Synthesis timeout")
        
    except Exception as e:
        synthesis_errors.inc()
        logger.error("Synthesis error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/synthesize")
async def synthesize_speech_get(
    text: str = Query(..., description="Text to synthesize"),
    voice: str = Query("en_US-lessac-high", description="Voice model to use"),
    speed: float = Query(1.0, description="Speech speed multiplier"),
    format: str = Query("wav", description="Output format")
) -> Response:
    """Synthesize speech using GET request (for streaming)"""
    
    synthesis_requests.inc()
    start_time = time.time()
    
    try:
        # Validate input
        if not text or not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Preprocess text
        text = preprocess_text(text)
        text_length.observe(len(text))
        
        # Validate voice
        if not check_voice_exists():
            raise HTTPException(status_code=500, detail="Voice model not available")
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode='w') as text_file, \
             tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
            
            # Write text to file
            text_file.write(text)
            text_file.flush()
            
            # Execute Piper
            command = [
                piper_binary,
                "--model", voice_model,
                "--config", voice_config,
                "--output_file", audio_file.name,
                "--output_raw",  # Output raw audio
                "--length_scale", str(1.0 / speed),  # Speed control
                text_file.name
            ]
            
            logger.info("Starting synthesis", 
                       text_length=len(text),
                       voice=voice,
                       speed=speed)
            
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                timeout=30  # 30 second timeout
            )
            
            # Clean up text file
            os.unlink(text_file.name)
            
            if result.returncode != 0:
                logger.error("Piper synthesis failed", 
                           returncode=result.returncode,
                           stderr=result.stderr)
                synthesis_errors.inc()
                raise HTTPException(
                    status_code=500, 
                    detail=f"Synthesis failed: {result.stderr}"
                )
            
            # Read generated audio
            audio_file.flush()
            with open(audio_file.name, 'rb') as f:
                audio_data = f.read()
            
            # Clean up audio file
            os.unlink(audio_file.name)
            
            processing_time = time.time() - start_time
            synthesis_duration.observe(processing_time)
            
            logger.info("Synthesis completed", 
                       audio_size=len(audio_data),
                       processing_time=processing_time)
            
            # Return audio as streaming response
            return Response(
                content=audio_data,
                media_type="audio/wav",
                headers={
                    "Content-Disposition": f"attachment; filename=synthesis.wav",
                    "X-Processing-Time": str(processing_time),
                    "X-Audio-Size": str(len(audio_data))
                }
            )
            
    except subprocess.TimeoutExpired:
        synthesis_errors.inc()
        logger.error("Synthesis timeout")
        raise HTTPException(status_code=408, detail="Synthesis timeout")
        
    except Exception as e:
        synthesis_errors.inc()
        logger.error("Synthesis error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/voices")
async def list_voices() -> Dict[str, Any]:
    """List available voices"""
    voices = {
        "en_US-lessac-high": {
            "name": "Lessac High Quality",
            "language": "en-US",
            "gender": "female",
            "size": get_voice_size(),
            "description": "High-quality English voice with natural intonation"
        }
    }
    
    return {
        "voices": voices,
        "default": "en_US-lessac-high"
    }

@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Starting TTS Service")
    
    # Check if voice model exists
    if not check_voice_exists():
        logger.error("Voice model not found", voice_model=voice_model)
        raise RuntimeError(f"Voice model not found at {voice_model}")
    
    logger.info("TTS Service started successfully", 
               voice_model=voice_model,
               voice_size=get_voice_size())

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down TTS Service")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000) 